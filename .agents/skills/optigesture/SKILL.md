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
  - Mode transitions: `IDLE`, `MOVING`, `CLICK`, `DRAGGING`, `SCROLLING`, `PAUSED`.
  - Zero-drift click anchoring: Locks pointer position when pinch touches.
  - Fist scrolling with recoil suppression: Tracks 4-knuckle centroid (MCPs 5, 9, 13, 17); fires discrete scroll steps on flick and suppresses opposite-direction return strokes for 450ms.
  - Back-of-hand hold pause: 5.0-second continuous hold timer with HUD countdown. Unpause is button-only ([P] or [Space]).
- `filters.py`: Signal processing engine:
  - `OneEuroFilter2D`: Adaptive low-pass filter (Casiez et al.) for tremor-free hovering and zero-lag flicks.
  - `PointerBallistics`: Non-linear velocity acceleration curve for multi-DPI reach.
  - `LandmarkSmoother`: Temporal pre-filter for normalized camera landmarks.
- `smart_target.py`: Windows UI Automation accessibility integration. Runs an asynchronous background thread to discover interactive buttons/tabs and applies magnetic snap attraction.
- `mouse_controller.py`: Direct Windows User32 hardware interface (`SetCursorPos`, `mouse_event`) with per-monitor DPI awareness.
- `hud.py`: Cyberpunk-style OpenCV overlay rendering badges, reticles, pinch distance gauges, screen radar minimap, and animated progress countdowns.
- `calibration.py`: Interactive 2-step wizard to calibrate natural resting palm scale and pinch click distance.
- `config.py`: Centralized parameter configuration.

---

## Key Tuning & Customization Knobs (`config.py`)

- Interaction margins: `MARGIN_X`, `MARGIN_Y` (default: `0.20`).
- 1 Euro Filter: `ONE_EURO_MIN_CUTOFF = 1.15`, `ONE_EURO_BETA = 0.045`.
- Fist scrolling: `FIST_SCROLL_STEPS = 4`, `FIST_SCROLL_FLICK_THRESHOLD = 0.011`, `FIST_SCROLL_RECOIL_WINDOW_SEC = 0.45`, `FIST_SCROLL_COOLDOWN_SEC = 0.22`.
- Pause clutch: `BACK_OF_HAND_PAUSE_SEC = 5.0`, `PALM_ORIENTATION_DEADZONE = 0.003`.
- Smart magnetic snap: `SNAP_RADIUS_PX = 45.0`, `SNAP_STRENGTH = 0.55`.

---

## Verification & QA Checklist

When modifying any gesture or motion tracking logic:
1. Run all unit tests: `python -m unittest discover -s tests`.
2. Verify all 24 test cases pass (100% pass rate).
3. Test finger rotation invariance across all 4 quadrants.
4. Verify that flicking UP does not trigger a downward scroll upon returning to neutral position.
5. Verify that back-of-hand pause requires the full 5.0-second hold and can only be resumed via keyboard.
