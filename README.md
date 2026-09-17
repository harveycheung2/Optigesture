# 🖐️ OptiGesture — Next-Gen AI Spatial Air Gesture Mouse

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078d6.svg)](https://www.microsoft.com/windows)
[![MediaPipe 1.0+](https://img.shields.io/badge/MediaPipe-Task%20Vision-orange.svg)](https://developers.google.com/mediapipe)
[![Tests: 24 Passed](https://img.shields.io/badge/tests-24%2F24%20passed-brightgreen.svg)]()

**OptiGesture** turns any standard laptop or desktop webcam into a high-precision, low-latency spatial mouse controller for Windows 10 & 11. Built entirely on on-device machine vision and deterministic signal processing, OptiGesture enables seamless pointer control, zero-drift pinch clicks, hold-to-drag, Tab-style magnetic snapping to Windows buttons, flick scrolling with return-stroke suppression, and a continuous 5-second back-of-hand pause clutch.

**100% Offline & Private:** Zero video frames or telemetry ever leave your device.

---

## 🌟 Key Features

- **👆 Fluid Pointer Tracking & Non-Linear Ballistics**:
  - Gold-standard **$1€$ Filter** eliminates physiological hand tremors when aiming at small targets.
  - **Dynamic Pointer Ballistics** dynamically scales cursor velocity: slow movements offer 1:1 pixel precision, while swift motions span dual-monitor or 3K/4K setups with ease.
- **🤏 Zero-Drift Pinch Click & Hold-to-Drag**:
  - Pointer coordinates lock the millisecond a pinch touches, eliminating cursor drift during clicks.
  - Quick pinch triggers a left click; holding the pinch for $> 0.35\text{s}$ engages hold-and-drag.
- **👊 Fist Scroll with Kinematic Recoil Suppression**:
  - Curl all four fingers with knuckles facing the webcam to enter scrolling mode.
  - Flick your wrist/fist **UP** to scroll up; flick **DOWN** to scroll down.
  - Integrated **450ms refractory state machine** suppresses the natural return stroke back to neutral position, guaranteeing **strictly 1 scroll action per flick**.
- **🧲 Tab-Style Smart Magnetic Snapping**:
  - Interrogates the Windows UI Automation tree asynchronously in the background.
  - Magnetically pulls the pointer toward clickable buttons, tabs, and checkboxes when in proximity, highlighting targeted controls with an on-screen glowing focus ring.
- **✋ 5-Second Back-of-Hand Pause Clutch**:
  - Uses 2D cross-product vector geometry to calculate palm normal orientation.
  - Continuous 5.0-second countdown with visual progress bar prevents accidental pause triggers.
  - **Button-Only Unpause**: Once paused, hand gestures cannot accidentally resume tracking; unpausing is strictly locked to the keyboard (`[P]` or `[Space]`).
- **🎯 Interactive 2-Step Calibration Wizard**:
  - Runs automatically on startup (or via `[K]` key) to personalize resting hand scale and pinch thresholds to your hand size and distance from the camera.
- **🖥️ Cyberpunk HUD Overlay & Screen Radar Minimap**:
  - Displays real-time reticles, dynamic pinch gauges, mode badges, FPS meters, and a screen radar preview showing cursor coordinates and focused buttons.

---

## 🏗️ Architecture & Module Breakdown

Every component in OptiGesture is modular, strictly typed, and optimized for performance:

```
                              ┌────────────────────────┐
                              │   Webcam Video Stream  │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │     HandTracker        │ (MediaPipe Task Vision CNN)
                              └───────────┬────────────┘
                                          │
                ┌─────────────────────────┼─────────────────────────┐
                │                         │                         │
                ▼                         ▼                         ▼
     ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
     │   GestureDetector   │   │     Filters &       │   │ SmartTargetAssistant│
     │ - Pinch Click/Drag  │   │  Signal Processing  │   │ - Windows UIA Com   │
     │ - Fist Scroll State │   │ - 1€ Filter (Casiez)│   │ - Magnetic Snap     │
     │ - 5s Hold Pause     │   │ - Pointer Ballistics│   │ - Focus Ring Overlay│
     └──────────┬──────────┘   └──────────┬──────────┘   └──────────┬──────────┘
                │                         │                         │
                └─────────────────────────┼─────────────────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │ WindowsMouseController │ (User32 Hardware Events)
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │    HUDOverlay (OpenCV) │
                              └────────────────────────┘
```

### 📂 Program Files & Modules

| Module / Program | Path | Responsibility |
| :--- | :--- | :--- |
| **`main.py`** | `main.py` | Application orchestrator. Manages OpenCV camera capture loop, filter pipeline, input event dispatch, keyboard listeners, audio feedback, and window lifecycle. |
| **`hand_tracker.py`** | `hand_tracker.py` | MediaPipe Hand Landmarker integration (Task Vision API). Extracts 21 3D joint landmarks, computes rotation-invariant finger extension states, palm scale, and handedness. |
| **`gesture_detector.py`** | `gesture_detector.py` | Gesture classification state machine. Implements distance-invariant pinch detection, zero-drift anchoring, 4-knuckle centroid tracking, 450ms recoil suppression, and 5s back-of-hand hold pause timer. |
| **`filters.py`** | `filters.py` | Signal processing algorithms: `OneEuroFilter2D` (Casiez et al.), `PointerBallistics` (non-linear velocity acceleration), `LandmarkSmoother` (normalized pre-filter), and `AdaptiveEMAFilter`. |
| **`smart_target.py`** | `smart_target.py` | Windows UI Automation accessibility integration. Scans active window controls asynchronously in a background thread, computes magnetic pull vectors, and projects desktop focus rings. |
| **`mouse_controller.py`** | `mouse_controller.py` | Direct Windows OS mouse driver using `ctypes.windll.user32`. Supports Per-Monitor DPI Awareness, `SetCursorPos`, `mouse_event` (clicks, drags, and discrete `WHEEL_DELTA` scrolling). |
| **`hud.py`** | `hud.py` | Real-time heads-up display rendering. Draws stylized corner brackets, gesture badges, pinch distance gauges, click ripples, screen radar minimap, and the 5-second countdown charging bar. |
| **`calibration.py`** | `calibration.py` | Interactive 2-step calibration wizard. Guides the user through sampling natural resting palm width and pinch click distance, computing personalized thresholds dynamically. |
| **`config.py`** | `config.py` | Centralized configuration file. Contains all tunable parameters (thresholds, sensitivities, margins, filters, and audio settings). |
| **`tests/test_gestures.py`** | `tests/test_gestures.py` | Unit tests verifying pinch click/drag states, anchor stabilization, rotation invariance, fist flick scrolling, return recoil suppression, and 5-second pause latching. |
| **`tests/test_filters.py`** | `tests/test_filters.py` | Unit tests validating the 1€ Filter, pointer ballistics acceleration curve, landmark pre-filters, and deadzone math. |

---

## 📦 Technologies & Dependencies

OptiGesture relies on modern, industry-standard computer vision and Windows system libraries:

1. **[Google MediaPipe](https://developers.google.com/mediapipe)** (`mediapipe >= 0.10.0`):
   - Local on-device deep learning Convolutional Neural Network (CNN) running on TensorFlow Lite with the XNNPACK CPU delegate.
   - Detects 21 3D hand landmarks at up to 60 FPS without GPU requirements.
2. **[OpenCV](https://opencv.org/)** (`opencv-python >= 4.8.0`):
   - DirectShow camera video streaming backend (`CAP_DSHOW`), RGB conversions, and HUD matrix rendering.
3. **[NumPy](https://numpy.org/)** (`numpy >= 1.24.0`):
   - Vector geometry, Euclidean distance calculation, coordinate transformations, and matrix normalization.
4. **Windows User32 API (`ctypes.windll.user32`)**:
   - Zero-latency kernel-level mouse event generation and per-monitor DPI awareness.
5. **Windows UIAutomation (`uiautomation >= 2.0.18`)**:
   - Interacts with Microsoft UIAutomationCore COM server to discover interactive GUI elements across Win32, WPF, UWP, and Electron desktop applications.
6. **1€ Filter (Casiez, Roussel, Vogel - ACM CHI 2012)**:
   - Adaptive first-order low-pass filter specifically designed for human-computer interaction to eliminate jitter at low speeds and latency at high speeds.

---

## 🚀 Quick Start

### Prerequisites
- Windows 10 or Windows 11 (64-bit)
- Python 3.9 through 3.12
- Standard built-in or external USB webcam

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/harveycheung2/Optigesture.git
   cd Optigesture
   ```

2. **Create and activate a virtual environment (recommended)**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Launch OptiGesture**:
   ```powershell
   python main.py
   ```

---

## 🎮 Gesture Guide & Controls

| Gesture | Hand Posture | Action |
| :--- | :--- | :--- |
| **Move Cursor** | Point Index finger inside active zone | Moves Windows mouse cursor with 1€ smoothing & ballistics |
| **Left Click** | Quick pinch: Thumb + Index tip ($< 0.35\text{s}$) | Instant left click with zero-drift coordinate anchor |
| **Drag & Drop** | Hold pinch: Thumb + Index tip ($> 0.35\text{s}$) | Locks left button down; release pinch to drop |
| **Scroll UP** | Closed fist $\rightarrow$ Flick knuckles UP | Exactly 1 scroll up impulse; return recoil is suppressed |
| **Scroll DOWN** | Closed fist $\rightarrow$ Flick knuckles DOWN | Exactly 1 scroll down impulse; return recoil is suppressed |
| **Tab Smart Focus** | Hover near buttons / tabs / links | Magnetically snaps to button center + displays focus ring |
| **Pause Tracking** | Show Back of Hand steadily for **5.0s** | Freezes cursor with countdown bar; rest arm without moving cursor |
| **Resume Tracking** | Press `[P]` or `[Space]` on keyboard | **Button ONLY** resume prevents accidental gesture wake-up |

### Keyboard Shortcuts

| Key | Function |
| :--- | :--- |
| **`[P]`** or **`[Space]`** | Resume tracking from pause / Toggle pause manually |
| **`[K]`** | Rerun the 2-step interactive calibration wizard |
| **`[T]`** | Toggle Tab-style magnetic snapping and desktop focus rings on/off |
| **`[A]`** | Toggle click sound feedback |
| **`[`** / **`]`** | Decrease / Increase active reach interaction zone margins |
| **`[Q]`** or **`[Esc]`** | Quit OptiGesture safely and release webcam |

---

## 🧪 Automated Testing

OptiGesture includes comprehensive automated test coverage:

```powershell
python -m unittest discover -s tests
```

**Results:**
```
Ran 24 tests in 2.37s
OK (100% Pass Rate)
```
- ✅ Mathematical rotation-invariance of finger extension
- ✅ Zero-drift coordinate anchor locking
- ✅ Adaptive palm-scale distance normalization
- ✅ Flick UP & Flick DOWN discrete step calculation
- ✅ Opposite-direction return stroke recoil suppression
- ✅ 5.0-second continuous back-of-hand hold latching
- ✅ Early hand withdrawal timer cancellation
- ✅ Button-only unpause lockout

---

## ⚙️ Configuration (`config.py`)

Fine-tune any parameter in `config.py`:

```python
# Screen Interaction Box Margins (0.05 - 0.40)
MARGIN_X = 0.20                      # Inner active horizontal boundary
MARGIN_Y = 0.20                      # Inner active vertical boundary

# 1€ Filter & Motion Smoothing
USE_ONE_EURO_FILTER = True
ONE_EURO_MIN_CUTOFF = 1.15           # Lower = rock-steady hovering
ONE_EURO_BETA = 0.045                # Higher = zero-lag fast swipes

# Fist Scrolling & Recoil Window
FIST_SCROLL_STEPS = 4                # Number of scroll wheel steps per flick
FIST_SCROLL_FLICK_THRESHOLD = 0.011  # Flick velocity sensitivity
FIST_SCROLL_RECOIL_WINDOW_SEC = 0.45 # Recoil suppression duration (seconds)
FIST_SCROLL_COOLDOWN_SEC = 0.22      # Same-direction inter-flick debounce

# Back-of-Hand Pause Timer
BACK_OF_HAND_PAUSE_SEC = 5.0         # Continuous hold seconds required to pause
```

---

## 🔒 Privacy Guarantee

- **Zero Cloud Communication**: The computer vision model runs on your local CPU via TensorFlow Lite (`hand_landmarker.task`).
- **No Video Recording or Storage**: Frames captured from the webcam exist exclusively in ephemeral RAM during processing and are discarded immediately.
- **Works 100% Offline**: OptiGesture functions completely without an internet connection or in Airplane Mode.

---

## 📄 License

This project is licensed under the **MIT License**. Feel free to use, modify, and distribute for personal and commercial projects.
