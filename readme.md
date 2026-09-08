# AI Face Recognition Attendance System

A state-of-the-art, production-ready AI Face Recognition Attendance System featuring a modern cyber-luxe web dashboard, live real-time camera scanning, staff face roster management, executive analytics, and instant multi-format reporting.

---

## Key Features

- **Live AI Scanner & Kiosk**:
  - High-FPS real-time webcam feed with cyber laser scanning HUD overlay.
  - Automatic face detection, reticle tracking, and verification against registered roster.
  - Multi-camera device switching (Front/Back/USB HD webcams) with mirroring toggle.
  - Dual audio feedback: Synthesized Web Audio chime + Web Speech voice greeting (*"Welcome, [Name]! Attendance registered."*).
  - Smart anti-duplicate check-in cooldown to prevent multi-logging.
  - Fullscreen Kiosk Mode for lobby tablets, check-in booths, and wall monitors.

- **Real-Time Attendance Audit & Logs**:
  - Live data table with instant search (by name, employee ID, role), date filtering, department filtering, and status (On Time / Late).
  - One-click CSV export, JSON export, and print-ready summary.
  - Manual check-in modal with audit trail.

- **Staff Face Roster Management**:
  - Visual roster directory with employee avatars, department badges, total days present, and last seen timestamps.
  - **Enroll New Staff**:
    - Mode 1: Live webcam snapshot capture with photo preview.
    - Mode 2: High-resolution image file upload.
  - Seamless two-way synchronization with the `Images/` folder and `Attendence.csv`.

- **Executive Analytics & Intelligence Hub**:
  - Real-time KPIs: Total Enrolled, Present Today, Attendance %, On-Time Arrival %, Peak Traffic Hour.
  - Glowing SVG Bar Chart for 24-hour check-in distribution.
  - Department breakdown distribution with live employee count.

- **System Configuration & Rules**:
  - Configurable official start time & late grace period.
  - Adjustable anti-duplicate cooldown slider.
  - Dark Cyber Mode and Crisp Light Enterprise Mode.

---

## Quick Start & Running Locally

### 1. Launch with One Click (Windows)
Double-click `run_server.bat` in the project root folder. It will start the server and open `http://localhost:8000` in your default browser.

### 2. Launch via Terminal
```bash
# Activate virtual environment
.\.venv\Scripts\activate

# Start the web server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Then visit [http://localhost:8000](http://localhost:8000) in your browser.

---

## Project Structure

```
AI_Attendence_Program/
├── app.py                  # FastAPI production backend & REST/WebSocket server
├── run_server.bat          # One-click Windows application launcher
├── Attendence.csv          # Attendance CSV log (automatically synchronized)
├── Main.py                 # Legacy OpenCV CLI script (preserved)
├── Images/                 # Enrolled personnel face images
│   └── elonmusk.jpg
├── data/
│   ├── attendance_logs.json# Enriched attendance database
│   ├── persons.json        # Staff roster metadata & face links
│   ├── settings.json       # System configurations
│   └── snapshots/          # Captured check-in photo snapshots
└── static/
    ├── index.html          # Main Single Page Application interface
    ├── css/
    │   └── style.css       # Cyber-luxe design system, glassmorphism & themes
    └── js/
        └── app.js          # WebRTC camera, AI HUD, WebSockets & UI logic
```
