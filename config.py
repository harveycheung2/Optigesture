"""
Configuration parameters for Air Gesture Mouse.
Tune these values to match your webcam, monitor setup, and personal preferences.
"""

# Camera settings
CAMERA_ID = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 30

# MediaPipe Hand Tracking parameters
MAX_NUM_HANDS = 1
MIN_DETECTION_CONFIDENCE = 0.75
MIN_TRACKING_CONFIDENCE = 0.75

# Screen Interaction Box Margins (0.0 - 0.4)
# Defining an active inner box so you don't have to reach the extreme edges of camera view
MARGIN_X = 0.20  # 20% margin left & right
MARGIN_Y = 0.20  # 20% margin top & bottom

# Advanced Motion Smoothing & Anti-Jitter (1€ Filter + Ballistics)
USE_ONE_EURO_FILTER = True          # Gold-standard 1€ Filter for jitter-free hovering + zero lag
ONE_EURO_MIN_CUTOFF = 1.15          # Min cutoff frequency (Hz). Lower = more stability when still
ONE_EURO_BETA = 0.045               # Speed coefficient. Higher = zero-lag response during swift flicks
ONE_EURO_D_CUTOFF = 1.0             # Derivative cutoff frequency

# Dual-Stage Filtering
USE_LANDMARK_PREFILTER = True       # Filter normalized camera landmarks before screen mapping
LANDMARK_SMOOTH_ALPHA = 0.65        # Landmark pre-filter smoothing factor (0.0 - 1.0)

# Pointer Ballistics & Non-Linear Gain (Mouse Acceleration)
ENABLE_POINTER_BALLISTICS = True    # Precision control for slow aiming + fast reach across 3K/4K displays
POINTER_PRECISION_SPEED = 90.0      # Speed threshold (px/s) for 1:1 precision aiming
POINTER_MAX_SPEED = 550.0           # Speed threshold (px/s) where max gain is reached
POINTER_MAX_GAIN = 2.0              # Max velocity acceleration factor (1.0 = linear, 2.0 = double reach)

# Legacy smoothing fallback
SMOOTHING_ALPHA = 0.65
DEADZONE_PIXELS = 3

# Gesture Distance Thresholds (normalized landmark coordinates [0.0 - 1.0])
PINCH_CLICK_THRESHOLD = 0.045       # Trigger left click when thumb & index distance < threshold
PINCH_RELEASE_THRESHOLD = 0.065     # Hysteresis buffer before releasing click/drag

# Palm-Scale Invariant Pinch Detection
USE_PALM_SCALE = True               # Scales pinch threshold with distance to webcam
PALM_PINCH_CLICK_RATIO = 0.28       # Pinch threshold relative to palm width (MCP 5 to MCP 17)
PALM_PINCH_RELEASE_RATIO = 0.40     # Release threshold relative to palm width

# Click Stabilization (Anti-Drift)
ANCHOR_ON_PINCH = True              # Lock pointer coordinates during pinch initiation to prevent click slip

# Audio Feedback
AUDIO_FEEDBACK = True               # Subtle audio chirp confirmation on click

# Gesture Timing
DRAG_HOLD_DELAY_SEC = 0.35          # Pinch held longer than this becomes a drag action
CLICK_COOLDOWN_SEC = 0.25           # Delay between single clicks to avoid accidental double clicks
# Back-of-Hand Pause (5-Second Timer)
BACK_OF_HAND_PAUSE_SEC = 5.0         # Must hold back of hand continuously for 5 seconds to pause
PALM_ORIENTATION_DEADZONE = 0.003   # Deadzone around edge-on orientation to prevent false triggers

# Interactive Calibration Wizard
AUTO_CALIBRATE_ON_START = True      # Run 2-step calibration wizard on startup (press Space to skip)

# Tab-Style Smart Button Focus & Magnetic Snapping
ENABLE_SMART_SNAP = True            # Magnetically snap to nearby buttons/tabs like Tab focus
SNAP_RADIUS_PX = 45.0               # Distance in screen pixels to trigger magnetic pull
SNAP_STRENGTH = 0.55                # Strength of magnetic attraction (0.0 - 1.0)
SHOW_DESKTOP_FOCUS_RING = True      # Display glowing Tab-style focus frame directly over Windows buttons

# Head Nod Scrolling (Nod head down & return = Scroll Down, Look up & return = Scroll Up)
ENABLE_HEAD_SCROLL = True               # Enable head nod scroll tracking by default
HEAD_SCROLL_PITCH_THRESHOLD = 8.5       # Degrees of tilt up/down to arm nod gesture
HEAD_SCROLL_RETURN_DEADZONE = 3.5       # Degrees to register return to neutral position
HEAD_SCROLL_RECOIL_WINDOW_SEC = 0.60    # Window to suppress opposite-direction recoil rebound
HEAD_SCROLL_COOLDOWN_SEC = 0.35         # Minimum debounce between consecutive same-direction nods
HEAD_SCROLL_STEPS = 4                   # Number of scroll wheel steps per nod
SHOW_HEAD_LANDMARKS = True              # Render head orientation reticle on camera preview
# V-Sign Gesture (1.5-Second Timer to Toggle Head Scroll)
V_SIGN_TOGGLE_SEC = 1.5              # Must hold V-sign (peace sign) continuously for 1.5 seconds to toggle head scroll
OPEN_PALM_TOGGLE_SEC = 1.5           # Fallback alias for backward compatibility

# Apple Fluid Spring Snapping & Rubber-Banding
SPRING_SNAP_DAMPING = 1.0            # Critically damped (1.0 = smooth settle, zero overshoot)
SPRING_SNAP_RESPONSE = 0.35          # Spring settle response in seconds
ENABLE_RUBBERBANDING = True          # Progressive elastic resistance at interaction box edges
RUBBERBAND_CONSTANT = 0.55           # Apple exponential resistance coefficient

