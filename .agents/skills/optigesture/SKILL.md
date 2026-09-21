---
name: optigesture
description: Operational runbook, architecture cheatsheet, testing procedures, and engineering reference for the OptiGesture air gesture mouse system. Use whenever working on, debugging, configuring, or extending OptiGesture.
---

# OptiGesture Operational & Engineering Runbook

This skill provides the architecture reference, operational instructions, testing workflows, and customization guides for the OptiGesture spatial air gesture mouse system.

## Quick Reference Commands

### Running the Application
```powershell
python main.py
```

### Running the Automated Test Suite
```powershell
python -m unittest discover -s tests
```

### Installing Dependencies
```powershell
pip install -r requirements.txt
```

---

## Architectural Map

OptiGesture is structured into dedicated, decoupled modules:

- `main.py`: Entry point and main event loop. Connects OpenCV camera capture, runs the tracking pipeline, applies ballistics, dispatches Win32 mouse events, renders HUD, and handles keyboard hotkeys.
- `hand_tracker.py`: Wrapper for MediaPipe Hand Landmarker Task Vision API. Downloads/loads `hand_landmarker.task`, extracts 21 3D landmarks, calculates rotation-invariant finger extension, palm scale, and handedness.
- `gesture_detector.py`: Finite state machine for gesture recognition:
  - Mode transitions: `IDLE`, `MOVING`, `CLICK`, `DRAGGING`, `PAUSED`.
  - Zero-drift click anchoring: Locks pointer position when pinch touches.
  - V-sign hold: 1.5-second continuous hold to toggle head nod scrolling on/off.
  - Back-of-hand hold pause: 5.0-second continuous hold timer with HUD countdown. Unpause is button-only ([P] or [Space]).
- `head_tracker.py`: MediaPipe Face Landmarker integration tracking pitch orientation for head nod scrolling with return-to-neutral recoil suppression.
- `filters.py`: Signal processing engine:
  - `OneEuroFilter2D`: Adaptive low-pass filter (Casiez et al.) for tremor-free hovering and zero-lag flicks.
  - `PointerBallistics`: Non-linear velocity acceleration curve for multi-DPI reach.
  - `LandmarkSmoother`: Temporal pre-filter for normalized camera landmarks.
- `smart_target.py`: Windows UI Automation accessibility integration. Runs an asynchronous background thread to discover interactive buttons/tabs and applies magnetic snap attraction.
- `mouse_controller.py`: Direct Windows User32 hardware interface (`SetCursorPos`, `mouse_event`) with per-monitor DPI awareness.
- `hud.py`: Apple-grade OpenCV overlay rendering badges, reticles, pinch distance gauges, screen radar minimap, and animated progress countdowns.
- `calibration.py`: Interactive 2-step wizard to calibrate natural resting palm scale and pinch click distance.
- `config.py`: Centralized parameter configuration.

---

## Key Tuning & Customization Knobs (`config.py`)

- Interaction margins: `MARGIN_X`, `MARGIN_Y` (default: `0.20`).
- 1 Euro Filter: `ONE_EURO_MIN_CUTOFF = 1.15`, `ONE_EURO_BETA = 0.045`.
- Head nod scrolling: `ENABLE_HEAD_SCROLL = True`, `HEAD_SCROLL_PITCH_THRESHOLD = 8.5`, `HEAD_SCROLL_RETURN_DEADZONE = 3.5`, `HEAD_SCROLL_RECOIL_WINDOW_SEC = 0.60`, `V_SIGN_TOGGLE_SEC = 1.5`.
- Pause clutch: `BACK_OF_HAND_PAUSE_SEC = 5.0`, `PALM_ORIENTATION_DEADZONE = 0.003`.
- Smart magnetic snap: `SNAP_RADIUS_PX = 45.0`, `SNAP_STRENGTH = 0.55`.

---

## Verification & QA Checklist

When modifying any gesture or motion tracking logic:
1. Run all unit tests: `python -m unittest discover -s tests`.
2. Verify all test cases pass (100% pass rate).
3. Test finger rotation invariance across all 4 quadrants.
4. Verify that nodding down or tilting up does not trigger counter-scrolling upon returning to neutral position.
5. Verify that back-of-hand pause requires the full 5.0-second hold and can only be resumed via keyboard.
6. Verify that V-sign requires 1.5 seconds to toggle head scroll.
