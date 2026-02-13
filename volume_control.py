import cv2
import mediapipe as mp
import time
import pyautogui
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# ================= AUDIO =================
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(
    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
)
volume = cast(interface, POINTER(IAudioEndpointVolume))
VOL_MIN, VOL_MAX = volume.GetVolumeRange()[:2]

# ================= CAMERA =================
cap = cv2.VideoCapture(0)
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)
draw = mp.solutions.drawing_utils

# ================= TIMING =================
VOL_STEP = (VOL_MAX - VOL_MIN) * 0.02
VOL_DELAY = 0.3
HOLD_TIME = 0.4

last_vol_time = time.time()
gesture_start = None
gesture_name = None
gesture_triggered = False

# ================= HELPERS =================
def finger_up(tip, pip):
    return tip.y < pip.y

# ================= LOOP =================
while True:
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    now = time.time()
    action_text = "No Hand Detected"
    detected = None

    if result.multi_hand_landmarks:
        action_text = "Waiting for Gesture..."
        for hand in result.multi_hand_landmarks:
            lm = hand.landmark

            # LandMark coordinate extraction for cleaner logic
            # Tip vs PIP Comparison (y-coordinate)
            f_up = [
                lm[8].y < lm[6].y,   # Index
                lm[12].y < lm[10].y, # Middle
                lm[16].y < lm[14].y, # Ring
                lm[20].y < lm[18].y  # Pinky
            ]
            
            # Thumb logic (horizontal check based on hand orientation)
            # lm[5] is index MCP, lm[17] is pinky MCP
            if lm[5].x < lm[17].x: # Right hand (palm to camera)
                thumb_up = lm[4].x < lm[3].x
            else: # Left hand or flipped right hand
                thumb_up = lm[4].x > lm[3].x

            current_vol = volume.GetMasterVolumeLevel()

            # ================= VOLUME UP (Thumb only) =================
            if thumb_up and not any(f_up):
                if now - last_vol_time > VOL_DELAY:
                    volume.SetMasterVolumeLevel(min(current_vol + VOL_STEP, 0.0), None)
                    last_vol_time = now
                action_text = "Volume UP"

            # ================= VOLUME DOWN (Fist) =================
            elif not thumb_up and not any(f_up):
                if now - last_vol_time > VOL_DELAY:
                    volume.SetMasterVolumeLevel(max(current_vol - VOL_STEP, VOL_MIN), None)
                    last_vol_time = now
                action_text = "Volume DOWN"

            # ================= PLAY / PAUSE (5 fingers) =================
            elif thumb_up and all(f_up):
                detected = "PLAY_PAUSE"
                action_text = "Hold: Play / Pause"

            # ================= NEXT TRACK (Index only) =================
            elif f_up[0] and not f_up[1] and not f_up[2] and not f_up[3] and not thumb_up:
                detected = "NEXT"
                action_text = "Hold: Next Track"

            # ================= PREVIOUS TRACK (Index + Middle) =================
            elif f_up[0] and f_up[1] and not f_up[2] and not f_up[3] and not thumb_up:
                detected = "PREVIOUS"
                action_text = "Hold: Previous Track"

            # ================= HOLD LOGIC =================
            if detected:
                if gesture_name != detected:
                    gesture_name = detected
                    gesture_start = now
                    gesture_triggered = False
                elif now - gesture_start >= HOLD_TIME and not gesture_triggered:
                    if detected == "PLAY_PAUSE":
                        pyautogui.press("playpause")
                    elif detected == "NEXT":
                        pyautogui.press("nexttrack")
                    elif detected == "PREVIOUS":
                        pyautogui.press("prevtrack")
                    
                    gesture_triggered = True
                    action_text = f"Action: {detected.replace('_', ' ')}"
            else:
                gesture_name = None
                gesture_start = None
                gesture_triggered = False

            draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

    cv2.rectangle(frame, (0, 0), (600, 60), (0, 0, 0), -1)
    cv2.putText(frame, action_text, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imshow("Gesture Music Controller", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
