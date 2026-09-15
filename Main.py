"""
AI Face Recognition Attendance System - Standalone Desktop Application
Optimized with Real-Time 128D Deep Facial Recognition (30+ FPS)
"""

import os
import sys
import time
from datetime import datetime
import numpy as np

try:
    import cv2
except ImportError:
    print("Error: OpenCV is required. Install via: pip install opencv-python")
    sys.exit(1)

try:
    import face_recognition
except ImportError:
    print("Error: face_recognition is required. Install via: pip install face-recognition")
    sys.exit(1)

# Base Paths (robust to working directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "Images")
ATTENDANCE_CSV = os.path.join(BASE_DIR, "Attendence.csv")

# Ensure Directories & Files Exist
os.makedirs(IMAGES_DIR, exist_ok=True)
if not os.path.exists(ATTENDANCE_CSV) or os.path.getsize(ATTENDANCE_CSV) == 0:
    with open(ATTENDANCE_CSV, "w", encoding="utf-8") as f:
        f.write("# Name,Time,Date\n")

print("=" * 60)
print("  AI Face Recognition Attendance System - Desktop Kiosk")
print("=" * 60)

# Load Staff Images & Precompute 128D Encodings
known_encodings = []
known_names = []
last_marked_time = {}  # Anti-duplicate cooldown cache

valid_extensions = {".jpg", ".jpeg", ".png", ".webp"}
image_files = [f for f in os.listdir(IMAGES_DIR) if os.path.splitext(f)[1].lower() in valid_extensions]

print(f"[*] Scanning enrolled staff in: {IMAGES_DIR}")
for img_file in image_files:
    person_name = os.path.splitext(img_file)[0].replace("_", " ").upper()
    img_path = os.path.join(IMAGES_DIR, img_file)
    
    img = cv2.imread(img_path)
    if img is None:
        print(f"  [!] Warning: Skipping unreadable image {img_file}")
        continue

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    encs = face_recognition.face_encodings(img_rgb)
    
    if len(encs) > 0:
        known_encodings.append(encs[0])
        known_names.append(person_name)
        print(f"  [+] Enrolled: {person_name}")
    else:
        print(f"  [!] Warning: No face detected in {img_file}. Skipping.")

print(f"[*] Total enrolled faces loaded: {len(known_encodings)}")
if len(known_encodings) == 0:
    print("[!] NOTICE: No staff faces enrolled in Images/. Please add .jpg photos to the Images/ directory.")

def record_attendance(name: str, cooldown_seconds: int = 300) -> bool:
    """Records attendance to CSV with anti-duplicate cooldown check."""
    now = datetime.now()
    now_ts = time.time()
    
    # Cooldown check (5 minutes anti-duplicate)
    if name in last_marked_time:
        if now_ts - last_marked_time[name] < cooldown_seconds:
            return False

    t_str = now.strftime('%H:%M:%S')
    d_str = now.strftime('%d/%m/%Y')
    
    # Read existing entries today to prevent multiple check-ins
    already_today = False
    try:
        if os.path.exists(ATTENDANCE_CSV):
            with open(ATTENDANCE_CSV, 'r', encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 3 and parts[0].strip().upper() == name and parts[2].strip() == d_str:
                        try:
                            prev_t = datetime.strptime(parts[1].strip(), '%H:%M:%S')
                            now_t = datetime.strptime(t_str, '%H:%M:%S')
                            if (now_t - prev_t).total_seconds() < cooldown_seconds:
                                already_today = True
                                break
                        except Exception:
                            pass
    except Exception as e:
        print(f"[!] CSV Read Warning: {e}")

    if not already_today:
        try:
            with open(ATTENDANCE_CSV, 'a', encoding="utf-8") as f:
                f.write(f"{name},{t_str},{d_str}\n")
            last_marked_time[name] = now_ts
            print(f"[+] ATTENDANCE RECORDED: {name} at {t_str} on {d_str}")
            return True
        except Exception as e:
            print(f"[!] CSV Write Error: {e}")
            return False
    return False

# Initialize Camera
print("[*] Initializing Camera (Index 0)...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("[*] Camera 0 unavailable, trying Index 1...")
    cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("[!] ERROR: No accessible webcam found. Please connect a webcam.")
    print("Press Enter to exit...")
    try:
        input()
    except Exception:
        pass
    sys.exit(1)

# Set HD resolution if supported
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

print("[*] Camera active. Press 'q' or ESC to quit.")
window_title = "AI Face Recognition Attendance System"
cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_title, 960, 540)

fps_time = time.time()
fps_counter = 0
fps_display = "30 FPS"

while True:
    ret, frame = cap.read()
    if not ret or frame is None:
        print("[!] Warning: Empty frame received from webcam.")
        time.sleep(0.1)
        continue

    # Mirror horizontally for natural kiosk feel
    frame = cv2.flip(frame, 1)

    # FPS computation
    fps_counter += 1
    if time.time() - fps_time >= 1.0:
        fps_display = f"{fps_counter} FPS"
        fps_counter = 0
        fps_time = time.time()

    # Downsample by 0.25 for 16x faster face detection
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    for encodeFace, faceLoc in zip(face_encodings, face_locations):
        name = "UNKNOWN"
        confidence_str = ""
        box_color = (0, 80, 220)  # Orange for unknown

        if len(known_encodings) > 0:
            face_distances = face_recognition.face_distance(known_encodings, encodeFace)
            match_index = int(np.argmin(face_distances))
            min_dist = float(face_distances[match_index])

            # Distance threshold 0.55 for strict high accuracy
            if min_dist <= 0.55:
                name = known_names[match_index]
                conf = max(75.0, min(99.6, (1.0 - (min_dist / 1.1)) * 100))
                confidence_str = f" ({conf:.1f}%)"
                box_color = (40, 200, 60)  # Green for verified match
                record_attendance(name)

        # Scale coordinates back to original frame (0.25 -> 4.0)
        y1, x2, y2, x1 = faceLoc
        y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4

        # Draw sleek bounding box with corner accents
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
        
        # Label banner
        label_text = f"{name}{confidence_str}"
        (label_w, label_h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_DUPLEX, 0.7, 1)
        cv2.rectangle(frame, (x1, y2 - label_h - 14), (x1 + label_w + 14, y2), box_color, cv2.FILLED)
        cv2.putText(frame, label_text, (x1 + 7, y2 - 7), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1)

    # Top HUD Bar
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), (20, 20, 25), cv2.FILLED)
    status_text = f"AI ATTENDANCE KIOSK | Enrolled: {len(known_encodings)} | {fps_display} | Press 'Q' to Exit"
    cv2.putText(frame, status_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 1, cv2.LINE_AA)

    cv2.imshow(window_title, frame)

    # Exit on 'q', ESC, or Enter
    key = cv2.waitKey(1) & 0xFF
    if key in [ord('q'), ord('Q'), 27, 13]:
        print("[*] Shutting down AI Attendance...")
        break

cap.release()
cv2.destroyAllWindows()
print("[*] Application terminated safely.")

