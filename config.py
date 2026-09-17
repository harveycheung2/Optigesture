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

# Fist Scrolling (Knuckles to screen: Flick Up = Scroll Up, Flick Down = Scroll Down)
FIST_SCROLL_STEPS = 4                # Number of scroll wheel steps per flick impulse
FIST_SCROLL_FLICK_THRESHOLD = 0.011  # Normalized knuckle displacement to trigger a flick
FIST_SCROLL_RECOIL_WINDOW_SEC = 0.45 # Cooldown window to suppress opposite-direction return motion
FIST_SCROLL_COOLDOWN_SEC = 0.22      # Minimum debounce between consecutive flicks in same direction
FIST_SCROLL_DEADZONE = 0.003        # Motion deadzone to ignore camera landmark noise

# Interactive Calibration Wizard
AUTO_CALIBRATE_ON_START = True      # Run 2-step calibration wizard on startup (press Space to skip)

# Tab-Style Smart Button Focus & Magnetic Snapping
ENABLE_SMART_SNAP = True            # Magnetically snap to nearby buttons/tabs like Tab focus
SNAP_RADIUS_PX = 45.0               # Distance in screen pixels to trigger magnetic pull
SNAP_STRENGTH = 0.55                # Strength of magnetic attraction (0.0 - 1.0)
SHOW_DESKTOP_FOCUS_RING = True      # Display glowing Tab-style focus frame directly over Windows buttons


