# OptiGesture - Engineering Skills and Technical Portfolio

This document outlines the software engineering competencies, architectural patterns, mathematical algorithms, and systems programming skills demonstrated in the OptiGesture project.

---

## Executive Summary

OptiGesture is a high-performance, real-time spatial interaction system that transforms standard webcam video feeds into a zero-latency, sub-millimeter accurate desktop mouse controller for Windows 10 and 11. The project combines edge computer vision, digital signal processing, low-level Windows kernel API integration, and asynchronous accessibility tree querying into a robust, 100% offline desktop application.

---

## Technical Competencies Demonstrated

### 1. Computer Vision and Edge Machine Learning
- **Edge Inference Pipeline**: Implemented Google MediaPipe's Task Vision pipeline via TensorFlow Lite with the XNNPACK CPU execution delegate, running real-time 3D skeletal landmark tracking at 30+ FPS without dedicated GPU hardware.
- **21-Point Skeletal Joint Extraction**: Real-time extraction and spatial normalization of 21 3D joint landmarks (wrist, metacarpophalangeal joints, interphalangeal joints, and fingertips).
- **Rotation-Invariant Kinematics**: Formulated rotation-independent finger extension algorithms using radial tip-to-wrist and tip-to-MCP geometric ratios, ensuring accurate finger classification regardless of hand tilt or orientation.
- **Scale Invariance**: Computed dynamic palm scale metrics (distance between Index MCP and Pinky MCP) to ensure pinch and drag thresholds automatically adapt to any hand size and camera distance.
- **Matrix Operations and HUD Rendering**: Leveraged OpenCV for DirectShow video capture, BGR/RGB color space transformations, alpha-blended Heads-Up Display (HUD) overlays, and screen radar minimap generation.

### 2. Digital Signal Processing and Motion Smoothing
- **Casiez 1 Euro Filter**: Implemented the ACM CHI 2012 gold-standard 1 Euro Filter algorithm, combining an adaptive low-pass filter with speed-dependent cutoff frequencies to eliminate physiological tremors during resting hover while ensuring zero lag during fast hand sweeps.
- **Non-Linear Pointer Ballistics**: Designed a sigmoid velocity acceleration transfer function (`PointerBallistics`) allowing 1:1 pixel precision for sub-millimeter targets at low speeds while doubling reach across dense multi-monitor or 3K/4K displays.
- **Dual-Stage Filtering**: Architected a dual-stage filter pipeline where raw camera landmarks are pre-filtered via Exponential Moving Averages (EMA) before entering the coordinate mapping engine, eliminating spatial quantization noise.
- **Vector Normal Estimation**: Applied 2D signed cross-product calculations on hand landmarks to derive real-time palm normal orientation vectors, reliably distinguishing front palm from the back of the hand.

### 3. Systems Programming and Windows OS Integration
- **Direct Kernel Event Injection**: Built a high-performance Windows mouse driver using `ctypes.windll.user32` to directly invoke native Win32 system APIs (`SetCursorPos`, `mouse_event`) with zero runtime overhead or third-party virtualization layers.
- **Per-Monitor DPI Awareness**: Programmed per-monitor DPI awareness calls (`SetProcessDpiAwareness`, `SetProcessDPIAware`) to guarantee native display resolution tracking across high-DPI scaling configurations.
- **Windows UI Automation (UIA) Integration**: Interfaced with Microsoft's `UIAutomationCore.dll` COM server to dynamically traverse the active desktop accessibility tree, identify clickable controls (buttons, tabs, links, checkboxes), and project desktop focus reticles.
- **Asynchronous Threading Architecture**: Offloaded UI Automation element queries to daemon background worker threads to guarantee that accessibility tree scanning never introduces jitter or frame drops to the primary 30 FPS video loop.

### 4. Finite State Machine (FSM) Design and Interaction Mechanics
- **Zero-Drift Coordinate Anchoring**: Developed coordinate latching logic that anchors cursor coordinates the millisecond a pinch is initiated, eliminating the "click slip" drift caused by physical finger impact.
- **Flick and Recoil Return Suppression**: Solved the two-phase kinematic wrist flick problem by designing a 450ms refractory state machine that swallows the hand's natural recoil return stroke, guaranteeing exactly 1 action per flick.
- **Hysteresis-Based Thresholding**: Applied dual-threshold hysteresis buffers to pinch click detection and release, preventing switch bounce and accidental double-clicks.
- **Continuous Hold Safety Clutch**: Engineered a 5.0-second continuous hold timer with real-time HUD progress feedback to ensure the pause clutch cannot be triggered by transient hand gestures.
- **Hardware Button-Only Lockout**: Enforced a strict safety boundary requiring physical keyboard input ([P] or [Space]) to resume tracking, preventing accidental gesture reactivation.

### 5. Software Architecture, Testing, and Quality Assurance
- **Modular Decoupled Design**: Separated concerns cleanly across dedicated modules: sensor capture (`hand_tracker.py`), gesture classification (`gesture_detector.py`), signal filtering (`filters.py`), accessibility snapping (`smart_target.py`), OS hardware control (`mouse_controller.py`), and visualization (`hud.py`).
- **Comprehensive Automated Unit Testing**: Built a 24-test unit suite (`unittest`) covering geometric rotation invariance, state machine transitions, ballistics transfer functions, recoil suppression, and timer latching with 100% pass rate.
- **Interactive Calibration System**: Designed an interactive 2-step calibration wizard (`calibration.py`) that samples resting palm width and pinch click distance to generate tailored configuration parameters on the fly.
- **Privacy-First Architecture**: Structured the entire application to operate 100% offline, processing frames solely within local ephemeral RAM with zero telemetry or network transmission.

---

## Technical Challenges and Solutions

### Challenge 1: Pointer Jitter vs. Input Latency Trade-Off
- **Problem**: Traditional moving averages smooth out hand tremors but introduce unacceptable cursor lag. Simple low-pass filters cause pointer overshooting during fast sweeps.
- **Solution**: Implemented the Casiez 1 Euro Filter with adaptive derivative cutoff frequencies (`d_cutoff = 1.0`, `min_cutoff = 1.15`, `beta = 0.045`). When the hand is stationary, cutoff frequency drops to filter high-frequency tremor. When speed increases, cutoff frequency increases dynamically to achieve zero latency.

### Challenge 2: Click Slip During Pinch Initiation
- **Problem**: When fingers touch to execute a click, the physical force causes the index fingertip to shift by 3 to 10 pixels, causing missed clicks on hyperlinks or buttons.
- **Solution**: Implemented instant coordinate anchoring. The exact cursor position is locked at the first detection of pinch threshold crossing and held rock-steady until either the click completes or a sustained drag (> 0.35s) is confirmed.

### Challenge 3: Wrist Flick Whiplash During Scrolling
- **Problem**: A wrist flick consists of an intentional upward flick followed by a natural downward return to neutral position. The return stroke was triggering an unwanted reverse scroll.
- **Solution**: Designed a discrete flick state machine with a 450ms recoil suppression window. Any motion in the opposing direction during the recovery window is strictly suppressed, while consecutive same-direction flicks are supported via a 220ms debounce.

### Challenge 4: Small Target Acquisition in Dense Desktop Environments
- **Problem**: Air gestures naturally lack the micro-friction of physical mouse pads, making targeting small 16x16 pixel UI buttons challenging.
- **Solution**: Built `SmartTargetAssistant` using Windows UI Automation. It scans active controls in a background thread and applies a soft magnetic attraction pull when the cursor approaches within 45 pixels of a button center, accompanied by an on-screen cyan focus ring.

---

## Technical Skills Summary Matrix

| Domain | Tools / Technologies | Specific Application in OptiGesture |
| :--- | :--- | :--- |
| **Edge AI & Computer Vision** | MediaPipe Task Vision, OpenCV, TFLite, XNNPACK | 21-point 3D hand tracking, DirectShow capture, HUD rendering |
| **Signal Processing & Math** | 1 Euro Filter, Linear Algebra, Vector Calculus | Anti-jitter filtering, pointer ballistics, palm normal estimation |
| **Systems & OS Interfacing** | Python ctypes, Windows User32, Win32 COM, DPI APIs | Native cursor control, mouse events, multi-DPI screen mapping |
| **Desktop Accessibility** | Windows UI Automation (`uiautomation`, COM) | Asynchronous button discovery, magnetic target snapping |
| **State Machine & Control** | Python OOP, Finite State Machines, Hysteresis | Zero-drift pinch locking, recoil suppression, hold timers |
| **Testing & Verification** | Python unittest, Mock sensor pipelines | 24 automated unit tests verifying kinematics and FSM behavior |
| **Performance Optimization** | Multi-threading, memory reuse, zero-copy buffers | 30+ FPS execution, < 150 MB RAM, 100% local edge privacy |
