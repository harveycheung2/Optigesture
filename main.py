import sys
import time
import cv2
import numpy as np

import config
from filters import AdaptiveEMAFilter, OneEuroFilter2D, PointerBallistics, LandmarkSmoother
from hand_tracker import HandTracker
from gesture_detector import GestureDetector, GestureMode
from mouse_controller import WindowsMouseController
from hud import HUDOverlay
from calibration import GestureCalibrator, CalibrationStep
from smart_target import SmartTargetAssistant
from head_tracker import HeadTracker


def map_coordinate(val: float, margin_low: float, margin_high: float, target_max: int) -> float:
    """Linearly maps a normalized coordinate within active box to screen coordinate range."""
    norm = (val - margin_low) / (margin_high - margin_low)
    clamped = max(0.0, min(1.0, norm))
    return clamped * target_max


def run():
    print("==================================================")
    print("           AIR GESTURE MOUSE CONTROLLER           ")
    print("==================================================")
    print("Connecting to webcam...")

    cap = cv2.VideoCapture(config.CAMERA_ID, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[Warning] Failed to open camera {config.CAMERA_ID} with DSHOW, trying default backend...")
        cap = cv2.VideoCapture(config.CAMERA_ID)

    if not cap.isOpened():
        print(f"[Error] Could not open webcam with ID {config.CAMERA_ID}.")
        print("Please check that your webcam is plugged in and not in use by another app.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Webcam initialized: {actual_w}x{actual_h}")

    # Initialize components
    mouse = WindowsMouseController()
    screen_w, screen_h = mouse.get_screen_size()
    print(f"Primary Display detected: {screen_w}x{screen_h}")

    tracker = HandTracker(
        max_hands=config.MAX_NUM_HANDS,
        detection_confidence=config.MIN_DETECTION_CONFIDENCE,
        tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
    )

    # Advanced Tracking & Motion Smoothing Filters
    use_one_euro = getattr(config, "USE_ONE_EURO_FILTER", True)
    one_euro_filter = OneEuroFilter2D(
        min_cutoff=getattr(config, "ONE_EURO_MIN_CUTOFF", 1.15),
        beta=getattr(config, "ONE_EURO_BETA", 0.045),
        d_cutoff=getattr(config, "ONE_EURO_D_CUTOFF", 1.0),
    )
    use_ballistics = getattr(config, "ENABLE_POINTER_BALLISTICS", True)
    ballistics = PointerBallistics(
        precision_speed_px_s=getattr(config, "POINTER_PRECISION_SPEED", 90.0),
        max_speed_px_s=getattr(config, "POINTER_MAX_SPEED", 550.0),
        max_gain=getattr(config, "POINTER_MAX_GAIN", 2.0),
    )
    use_landmark_prefilter = getattr(config, "USE_LANDMARK_PREFILTER", True)
    landmark_smoother = LandmarkSmoother(
        alpha=getattr(config, "LANDMARK_SMOOTH_ALPHA", 0.65)
    )

    # Legacy fallback filter
    filter_engine = AdaptiveEMAFilter(
        base_alpha=config.SMOOTHING_ALPHA,
        deadzone_px=config.DEADZONE_PIXELS,
    )

    detector = GestureDetector(
        pinch_click_threshold=config.PINCH_CLICK_THRESHOLD,
        pinch_release_threshold=config.PINCH_RELEASE_THRESHOLD,
        drag_hold_delay=config.DRAG_HOLD_DELAY_SEC,
        click_cooldown=config.CLICK_COOLDOWN_SEC,
        back_hold_sec=getattr(config, "BACK_OF_HAND_PAUSE_SEC", 5.0),
        palm_orientation_deadzone=getattr(config, "PALM_ORIENTATION_DEADZONE", 0.003),
        use_palm_scale=getattr(config, "USE_PALM_SCALE", True),
        palm_pinch_click_ratio=getattr(config, "PALM_PINCH_CLICK_RATIO", 0.28),
        palm_pinch_release_ratio=getattr(config, "PALM_PINCH_RELEASE_RATIO", 0.40),
        anchor_on_pinch=getattr(config, "ANCHOR_ON_PINCH", True),
        v_sign_hold_sec=getattr(config, "V_SIGN_TOGGLE_SEC", getattr(config, "OPEN_PALM_TOGGLE_SEC", 1.5)),
    )

    curr_margin_x = config.MARGIN_X
    curr_margin_y = config.MARGIN_Y
    audio_enabled = getattr(config, "AUDIO_FEEDBACK", True)

    hud = HUDOverlay(
        frame_width=actual_w,
        frame_height=actual_h,
        margin_x=curr_margin_x,
        margin_y=curr_margin_y,
    )

    # Initialize Smart Target Assistant (Tab-style focus & magnetic snapping)
    smart_assistant = SmartTargetAssistant(
        snap_radius=getattr(config, "SNAP_RADIUS_PX", 45.0),
        snap_strength=getattr(config, "SNAP_STRENGTH", 0.55),
        enable_snap=getattr(config, "ENABLE_SMART_SNAP", True),
        enable_overlay=getattr(config, "SHOW_DESKTOP_FOCUS_RING", True),
        spring_damping=getattr(config, "SPRING_SNAP_DAMPING", 1.0),
        spring_response=getattr(config, "SPRING_SNAP_RESPONSE", 0.35),
    )

    # Initialize Head Tracker for Head Nod Scrolling
    head_scroll_enabled = getattr(config, "ENABLE_HEAD_SCROLL", True)
    head_tracker = HeadTracker(
        pitch_threshold=getattr(config, "HEAD_SCROLL_PITCH_THRESHOLD", 8.5),
        return_deadzone=getattr(config, "HEAD_SCROLL_RETURN_DEADZONE", 3.5),
        recoil_window_sec=getattr(config, "HEAD_SCROLL_RECOIL_WINDOW_SEC", 0.60),
        cooldown_sec=getattr(config, "HEAD_SCROLL_COOLDOWN_SEC", 0.35),
        scroll_steps=getattr(config, "HEAD_SCROLL_STEPS", 4),
    )

    # Initialize Gesture Calibrator
    calibrator = GestureCalibrator()
    if getattr(config, "AUTO_CALIBRATE_ON_START", True):
        calibrator.start()
        print("[Calibration] 2-Step wizard started. Press [Space] to skip.")

    def play_click_sound():
        """Plays subtle click confirmation sound asynchronously."""
        if not audio_enabled:
            return
        import threading
        try:
            import winsound
            threading.Thread(target=lambda: winsound.Beep(1400, 25), daemon=True).start()
        except Exception:
            pass

    print("\n[Controls & Gestures]")
    print("  * Move Cursor : Point index finger inside active interaction zone")
    print("  * Left Click  : Pinch Thumb & Index (Zero-drift locked anchor)")
    print("  * Drag & Drop : Pinch and hold for > 0.35s, then move hand")
    print("  * Head Scroll : Nod head down & return = Scroll DOWN | Tilt up & return = Scroll UP")
    print("  * Tab Focus   : Nearby buttons/tabs are highlighted & magnetically snapped")
    print("  * Pause       : Hold Back of Hand continuously for 5.0s (or press [P])")
    print("  * Resume      : Press [P] or [Space] on keyboard (Button ONLY)")
    print("  * [N] Key     : Toggle Head Nod Scroll on/off (or hold V-Sign for 1.5s)")
    print("  * [C] Key     : Calibrate / center head neutral pitch")
    print("  * [K] Key     : Run interactive 2-step calibration wizard")
    print("  * [T] Key     : Toggle Tab-style magnetic snapping on/off")
    print("  * [ / ] Keys  : Adjust active reach zone margins on the fly")
    print("  * [A] Key     : Toggle audio feedback click sound")
    print("  * [Q] / Esc   : Quit application")
    print("\nStarting video stream...")

    prev_time = time.time()
    fps = 30.0
    current_screen_x, current_screen_y = screen_w // 2, screen_h // 2
    focused_target = None

    cv2.namedWindow("Air Gesture Mouse", cv2.WINDOW_AUTOSIZE)

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            # Mirror the frame horizontally so moving right moves right
            frame = cv2.flip(frame, 1)

            # Calculate FPS
            curr_time = time.time()
            dt = curr_time - prev_time
            if dt > 0:
                fps = (0.9 * fps) + (0.1 * (1.0 / dt))
            prev_time = curr_time

            # MediaPipe hand tracking with temporal video timestamp
            timestamp_ms = int(curr_time * 1000)
            results = tracker.process_frame(frame, timestamp_ms=timestamp_ms)
            landmarks = tracker.get_landmarks(results, frame.shape)
            finger_states = tracker.get_finger_states(landmarks) if landmarks else {}
            palm_scale = tracker.get_palm_scale(landmarks) if landmarks else 0.15

            # MediaPipe head tracking for Head Nod Scrolling
            head_info = None
            if head_scroll_enabled or getattr(config, "SHOW_HEAD_LANDMARKS", True):
                face_landmarks, matrix = head_tracker.process_frame(frame, timestamp_ms=timestamp_ms)
                if face_landmarks:
                    head_info = head_tracker.update(face_landmarks, matrix, curr_time=curr_time)
                    if getattr(config, "SHOW_HEAD_LANDMARKS", True):
                        head_tracker.draw_head_pose(frame, face_landmarks, head_info)

            # If Calibration is active, run wizard instead of moving mouse
            if calibrator.is_active:
                c_step, prog, msg = calibrator.update(landmarks, finger_states, palm_scale)
                tracker.draw_skeleton(frame, results)
                calibrator.render_overlay(frame, prog, msg)

                if c_step == CalibrationStep.COMPLETE:
                    detector.pinch_click_threshold = calibrator.calibrated_click_thresh
                    detector.pinch_release_threshold = calibrator.calibrated_release_thresh
                    detector.palm_pinch_click_ratio = calibrator.calibrated_click_thresh / calibrator.calibrated_palm_scale
                    detector.palm_pinch_release_ratio = calibrator.calibrated_release_thresh / calibrator.calibrated_palm_scale
                    play_click_sound()
                    print(f"[Calibration] Applied! Click: {calibrator.calibrated_click_thresh:.3f}, Palm: {calibrator.calibrated_palm_scale:.3f}")

                cv2.imshow("Air Gesture Mouse", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == 32:  # Space
                    calibrator.cancel()
                    print("[Calibration] Skipped by user.")
                elif key == ord('n') or key == ord('N'):
                    calibrator.cancel()
                    head_scroll_enabled = not head_scroll_enabled
                    print(f"[Calibration] Skipped. Head Scroll {'ENABLED' if head_scroll_enabled else 'DISABLED'}")
                elif key == 27 or key == ord('q'):
                    print("\nExiting...")
                    break
                continue

            # Normal Tracking Mode: Evaluate gestures with scale invariance
            handedness = tracker.get_handedness(results) if results else "Right"
            mode, info = detector.detect(landmarks, finger_states, palm_scale, handedness=handedness)

            # Handle Cursor Movement & Actions
            if mode in [GestureMode.MOVING, GestureMode.CLICK, GestureMode.DRAGGING]:
                if info["pointer_pos"]:
                    raw_nx, raw_ny = info["pointer_pos"]

                    # Pre-filter raw camera landmark to eliminate sensor quantization noise
                    if use_landmark_prefilter and not info.get("is_anchored"):
                        raw_nx, raw_ny = landmark_smoother.smooth(8, raw_nx, raw_ny)

                    # Map active box to full screen
                    target_screen_x = map_coordinate(raw_nx, curr_margin_x, 1.0 - curr_margin_x, screen_w)
                    target_screen_y = map_coordinate(raw_ny, curr_margin_y, 1.0 - curr_margin_y, screen_h)

                    # When anchored in CLICK mode, hold position rock-steady at anchor point
                    if info.get("is_anchored"):
                        smooth_x, smooth_y = float(current_screen_x), float(current_screen_y)
                    else:
                        # Non-linear pointer ballistics acceleration curve
                        if use_ballistics:
                            target_screen_x, target_screen_y = ballistics.accelerate(target_screen_x, target_screen_y, curr_time)
                            target_screen_x = max(0.0, min(screen_w - 1.0, target_screen_x))
                            target_screen_y = max(0.0, min(screen_h - 1.0, target_screen_y))

                        # 1€ Filter (ultra-smooth hovering + zero-lag swiping)
                        if use_one_euro:
                            smooth_x, smooth_y = one_euro_filter.filter(target_screen_x, target_screen_y, curr_time)
                        else:
                            smooth_x, smooth_y = filter_engine.filter(target_screen_x, target_screen_y)

                    # Apply Apple-Grade Spring Magnetic Snapping
                    snapped_x, snapped_y, focused_target = smart_assistant.apply_magnetic_snap(smooth_x, smooth_y, curr_time=curr_time)
                    if focused_target and focused_target.get("just_snapped") and audio_enabled:
                        import threading
                        try:
                            import winsound
                            threading.Thread(target=lambda: winsound.Beep(1800, 20), daemon=True).start()
                        except Exception:
                            pass
                    mouse.move_to(snapped_x, snapped_y)
                    current_screen_x, current_screen_y = int(snapped_x), int(snapped_y)

            elif mode in [GestureMode.IDLE, GestureMode.PAUSED]:
                filter_engine.reset()
                one_euro_filter.reset()
                ballistics.reset()
                landmark_smoother.reset()
                focused_target = None

            # Process Click & Drag Events
            if info.get("just_clicked"):
                mouse.left_click()
                play_click_sound()
                # Trigger click ripple at index finger location
                if landmarks and len(landmarks) > 8:
                    hud.trigger_click_ripple(landmarks[8]["px"], landmarks[8]["py"], color=(60, 220, 80))

            if mode == GestureMode.DRAGGING and not mouse.is_left_down:
                mouse.left_down()
                play_click_sound()
            elif mode != GestureMode.DRAGGING and mouse.is_left_down:
                mouse.left_up()

            # Process Scrolling (Head Nod)
            if mode != GestureMode.PAUSED and head_scroll_enabled and head_info:
                head_scroll = head_info.get("scroll_delta", 0)
                if head_scroll != 0:
                    mouse.scroll(head_scroll)

            # Process Back-of-Hand Pause Toggle
            if info.get("back_toggled"):
                print(f"\n[Status] Back of Hand held 5.0s -> Program PAUSED (Press [P] or [Space] to Resume)")
                if audio_enabled:
                    import threading
                    try:
                        import winsound
                        threading.Thread(target=lambda: winsound.Beep(600, 160), daemon=True).start()
                    except Exception:
                        pass

            # Process V-Sign 1.5s Hold (Toggle Head Scroll Feature)
            if info.get("v_sign_toggled") or info.get("open_palm_toggled"):
                head_scroll_enabled = not head_scroll_enabled
                mode_desc = "Head Scroll ENABLED" if head_scroll_enabled else "Head Scroll DISABLED"
                print(f"\n[Scroll Mode] V-Sign held 1.5s -> {mode_desc}")
                hud.set_alert(f"HEAD SCROLL: {'ON' if head_scroll_enabled else 'OFF'}")
                if audio_enabled:
                    import threading
                    try:
                        import winsound
                        tone1 = 800 if head_scroll_enabled else 1200
                        tone2 = 1200 if head_scroll_enabled else 800
                        def _play_toggle_chime(t1, t2):
                            winsound.Beep(t1, 90)
                            winsound.Beep(t2, 130)
                        threading.Thread(target=_play_toggle_chime, args=(tone1, tone2), daemon=True).start()
                    except Exception:
                        pass

            # Draw visual landmarks and HUD overlay
            tracker.draw_skeleton(frame, results)
            hud.render(
                frame=frame,
                fps=fps,
                mode=mode,
                info=info,
                landmarks=landmarks,
                click_threshold=info.get("effective_threshold", config.PINCH_CLICK_THRESHOLD),
                screen_coords=(current_screen_x, current_screen_y),
                screen_res=(screen_w, screen_h),
                focused_target=focused_target,
                head_scroll_enabled=head_scroll_enabled,
                head_info=head_info,
            )

            # Show window
            cv2.imshow("Air Gesture Mouse", frame)

            # Handle hotkeys
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # 'q' or Esc
                print("\nExiting...")
                break
            elif key == ord('n') or key == ord('N'):
                head_scroll_enabled = not head_scroll_enabled
                print(f"\n[Scroll Mode] Head Scroll {'ENABLED' if head_scroll_enabled else 'DISABLED'}")
                hud.set_alert(f"HEAD SCROLL: {'ON' if head_scroll_enabled else 'OFF'}")
            elif key == ord('c') or key == ord('C'):
                head_tracker.calibrate_neutral()
            elif key == ord('p') or key == ord('P') or key == 32:  # 'P' or Space
                is_paused = detector.toggle_pause()
                print(f"\n[Status] Keyboard button pressed -> Program {'PAUSED' if is_paused else 'RESUMED'}")
                if audio_enabled:
                    import threading
                    try:
                        import winsound
                        tone = 600 if is_paused else 1100
                        threading.Thread(target=lambda: winsound.Beep(tone, 150), daemon=True).start()
                    except Exception:
                        pass
            elif key == ord('k') or key == ord('K'):
                calibrator.start()
                print("[Calibration] Wizard restarted.")
            elif key == ord('t') or key == ord('T'):
                snap_on = smart_assistant.toggle_snap()
                print(f"[Smart Snap] Magnetic button snapping {'ENABLED' if snap_on else 'DISABLED'}")
            elif key == ord('a') or key == ord('A'):
                audio_enabled = not audio_enabled
                print(f"[Audio] Click sound feedback {'ENABLED' if audio_enabled else 'DISABLED'}")
            elif key == ord('['):
                curr_margin_x = min(0.35, curr_margin_x + 0.02)
                curr_margin_y = min(0.35, curr_margin_y + 0.02)
                hud.set_margins(curr_margin_x, curr_margin_y)
                print(f"[Reach] Zone margins increased to {int(curr_margin_x * 100)}%")
            elif key == ord(']'):
                curr_margin_x = max(0.06, curr_margin_x - 0.02)
                curr_margin_y = max(0.06, curr_margin_y - 0.02)
                hud.set_margins(curr_margin_x, curr_margin_y)
                print(f"[Reach] Zone margins decreased to {int(curr_margin_x * 100)}%")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        mouse.release_all()
        smart_assistant.close()
        cap.release()
        cv2.destroyAllWindows()
        print("Camera released. Goodbye!")


if __name__ == "__main__":
    run()
