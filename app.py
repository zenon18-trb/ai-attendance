import os
import io
import csv
import json
import time
import base64
import shutil
import tempfile
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from PIL import Image
import jwt
from jwt import PyJWKClient
from supabase_repo import ensure_organization, list_people as supabase_list_people, create_person as supabase_create_person, delete_person as supabase_delete_person, upload_face_image, create_signed_image_url, SupabaseRepositoryError

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
SUPABASE_JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else ""
_jwks_client = PyJWKClient(SUPABASE_JWKS_URL) if SUPABASE_JWKS_URL else None

PUBLIC_API_PATHS = {"/api/supabase-config", "/health"}

def verify_access_token(token: str) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm == "HS256" and SUPABASE_JWT_SECRET:
            return jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
        if algorithm in {"RS256", "ES256"} and _jwks_client:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, algorithms=[algorithm], audience="authenticated")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc
    raise HTTPException(status_code=401, detail="Authentication is not configured")

async def require_authenticated_request(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path not in PUBLIC_API_PATHS:
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        try:
            request.state.user = verify_access_token(authorization[7:].strip())
            user_id = request.state.user.get("sub")
            if not user_id:
                return JSONResponse(status_code=401, content={"detail": "Invalid authentication token"})
            try:
                request.state.organization_id = ensure_organization(user_id)
            except SupabaseRepositoryError:
                return JSONResponse(status_code=503, content={"detail": "Organization service unavailable"})
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 12 * 1024 * 1024:
        return JSONResponse(status_code=413, content={"detail": "Request payload is too large"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    return response

# Initialize FastAPI App
app = FastAPI(
    title="AI Face Recognition Attendance System",
    description="Enterprise-grade AI Face Recognition & Attendance Monitoring Platform",
    version="2.0.0"
)

# Restrict cross-origin access; same-origin deployment remains the default.
allowed_origins = [origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.middleware("http")(require_authenticated_request)

# Base Paths (Source Repo)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Helper to check if a directory is writable
def is_directory_writable(path: str) -> bool:
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            return False
    try:
        test_file = os.path.join(path, f".write_test_{int(time.time()*1000)}")
        with open(test_file, "w") as f:
            f.write("test")
        if os.path.exists(test_file):
            os.remove(test_file)
        return True
    except Exception:
        return False

# Determine Storage Directory (Support serverless / read-only Vercel / AWS Lambda environments)
is_serverless = bool(
    os.environ.get("VERCEL")
    or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    or os.environ.get("LAMBDA_TASK_ROOT")
)

default_data_dir = os.path.join(BASE_DIR, "data")
if is_serverless or not is_directory_writable(default_data_dir):
    STORAGE_ROOT = os.path.join(tempfile.gettempdir(), "ai_attendance_storage")
else:
    STORAGE_ROOT = BASE_DIR

IMAGES_DIR = os.path.join(STORAGE_ROOT, "Images")
DATA_DIR = os.path.join(STORAGE_ROOT, "data")
SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")
ATTENDANCE_CSV = os.path.join(STORAGE_ROOT, "Attendence.csv")
ATTENDANCE_JSON = os.path.join(DATA_DIR, "attendance_logs.json")
PERSONS_JSON = os.path.join(DATA_DIR, "persons.json")
SETTINGS_JSON = os.path.join(DATA_DIR, "settings.json")
CASCADE_PATH = os.path.join(DATA_DIR, "haarcascade_frontalface_default.xml")

# Initialize and clone initial seed assets from repository to storage root if needed
try:
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    
    if STORAGE_ROOT != BASE_DIR:
        seed_data_dir = os.path.join(BASE_DIR, "data")
        seed_images_dir = os.path.join(BASE_DIR, "Images")
        seed_csv = os.path.join(BASE_DIR, "Attendence.csv")
        
        # Copy persons.json
        seed_persons = os.path.join(seed_data_dir, "persons.json")
        if os.path.exists(seed_persons) and not os.path.exists(PERSONS_JSON):
            try:
                shutil.copy2(seed_persons, PERSONS_JSON)
            except Exception:
                pass
            
        # Copy settings.json
        seed_settings = os.path.join(seed_data_dir, "settings.json")
        if os.path.exists(seed_settings) and not os.path.exists(SETTINGS_JSON):
            try:
                shutil.copy2(seed_settings, SETTINGS_JSON)
            except Exception:
                pass

        # Copy attendance_logs.json
        seed_attendance = os.path.join(seed_data_dir, "attendance_logs.json")
        if os.path.exists(seed_attendance) and not os.path.exists(ATTENDANCE_JSON):
            try:
                shutil.copy2(seed_attendance, ATTENDANCE_JSON)
            except Exception:
                pass

        # Copy cascade xml
        seed_cascade = os.path.join(seed_data_dir, "haarcascade_frontalface_default.xml")
        if os.path.exists(seed_cascade) and not os.path.exists(CASCADE_PATH):
            try:
                shutil.copy2(seed_cascade, CASCADE_PATH)
            except Exception:
                pass

        # Copy CSV
        if os.path.exists(seed_csv) and not os.path.exists(ATTENDANCE_CSV):
            try:
                shutil.copy2(seed_csv, ATTENDANCE_CSV)
            except Exception:
                pass

        # Copy seed images
        if os.path.exists(seed_images_dir):
            for img_f in os.listdir(seed_images_dir):
                s_path = os.path.join(seed_images_dir, img_f)
                d_path = os.path.join(IMAGES_DIR, img_f)
                if os.path.isfile(s_path) and not os.path.exists(d_path):
                    try:
                        shutil.copy2(s_path, d_path)
                    except Exception:
                        pass
except Exception as e:
    print(f"Storage init notice: {e}")

# Default Settings
DEFAULT_SETTINGS = {
    "office_start_time": "09:00",
    "late_grace_minutes": 15,
    "cooldown_seconds": 300,  # 5 minutes anti-duplicate check-in cooldown
    "confidence_threshold": 0.55,
    "sound_effects_enabled": True,
    "speech_announcement_enabled": True,
    "kiosk_mode_pin": "1234",
    "organization_name": "AI Attendance System",
    "theme_mode": "dark"
}

# In-Memory Cache & State (guarantees zero-500s even if disk is restricted)
_in_memory_settings: Dict[str, Any] = DEFAULT_SETTINGS.copy()
_in_memory_persons: List[Dict[str, Any]] = []
_in_memory_records: List[Dict[str, Any]] = []
connected_websockets: List[WebSocket] = []
known_face_names: List[str] = []
last_mark_timestamps: Dict[str, float] = {}

# ----------------- Helper Functions ----------------- #

def load_settings() -> Dict[str, Any]:
    global _in_memory_settings
    if os.path.exists(SETTINGS_JSON):
        try:
            with open(SETTINGS_JSON, "r", encoding="utf-8") as f:
                saved = json.load(f)
                _in_memory_settings = {**DEFAULT_SETTINGS, **saved}
                return _in_memory_settings
        except Exception:
            pass
    return _in_memory_settings.copy()

def save_settings(settings: Dict[str, Any]):
    global _in_memory_settings
    _in_memory_settings = {**DEFAULT_SETTINGS, **settings}
    try:
        with open(SETTINGS_JSON, "w", encoding="utf-8") as f:
            json.dump(_in_memory_settings, f, indent=2)
    except Exception as e:
        print(f"Disk save settings warning: {e}")

def load_persons() -> List[Dict[str, Any]]:
    global _in_memory_persons
    persons_map = {}
    
    # 1. From file if exists
    if os.path.exists(PERSONS_JSON):
        try:
            with open(PERSONS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                for p in data:
                    persons_map[p["name"].upper()] = p
        except Exception:
            pass
    elif _in_memory_persons:
        for p in _in_memory_persons:
            persons_map[p["name"].upper()] = p

    # 2. Check seed persons if map is empty
    if not persons_map:
        seed_persons = os.path.join(BASE_DIR, "data", "persons.json")
        if os.path.exists(seed_persons):
            try:
                with open(seed_persons, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for p in data:
                        persons_map[p["name"].upper()] = p
            except Exception:
                pass

    # 3. Synchronize with Images directory
    new_found = False
    for check_dir in [IMAGES_DIR, os.path.join(BASE_DIR, "Images")]:
        if os.path.exists(check_dir):
            for fname in os.listdir(check_dir):
                name, ext = os.path.splitext(fname)
                if ext.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    uname = name.upper()
                    if uname not in persons_map:
                        persons_map[uname] = {
                            "id": f"EMP-{len(persons_map) + 1:04d}",
                            "name": uname,
                            "displayName": name.replace("_", " ").title(),
                            "department": "Engineering",
                            "role": "Team Member",
                            "email": f"{name.lower().replace(' ', '.')}@company.ai",
                            "image": f"/api/persons/photo/{fname}",
                            "registeredDate": datetime.now().strftime("%Y-%m-%d"),
                            "active": True
                        }
                        new_found = True
    
    persons_list = list(persons_map.values())
    _in_memory_persons = persons_list
    
    # Only write back if new persons were discovered
    if new_found:
        try:
            with open(PERSONS_JSON, "w", encoding="utf-8") as f:
                json.dump(persons_list, f, indent=2)
        except Exception as e:
            print(f"Disk save persons warning: {e}")
    
    return persons_list

def save_persons_list(persons: List[Dict[str, Any]]):
    global _in_memory_persons
    _in_memory_persons = persons
    try:
        with open(PERSONS_JSON, "w", encoding="utf-8") as f:
            json.dump(persons, f, indent=2)
    except Exception as e:
        print(f"Disk save persons warning: {e}")

def load_attendance_records() -> List[Dict[str, Any]]:
    global _in_memory_records
    records = []
    
    # 1. From file
    if os.path.exists(ATTENDANCE_JSON):
        try:
            with open(ATTENDANCE_JSON, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
    elif _in_memory_records:
        records = list(_in_memory_records)

    # 2. Check seed attendance if empty
    if not records:
        seed_att = os.path.join(BASE_DIR, "data", "attendance_logs.json")
        if os.path.exists(seed_att):
            try:
                with open(seed_att, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                pass

    # 3. Check CSV files (storage & seed, supporting both Attendence and Attendance spellings)
    csv_candidates = [
        ATTENDANCE_CSV,
        os.path.join(STORAGE_ROOT, "Attendance.csv"),
        os.path.join(BASE_DIR, "Attendence.csv"),
        os.path.join(BASE_DIR, "Attendance.csv")
    ]
    existing_keys = {f"{r.get('name', '').upper()}_{r.get('date', '')}_{r.get('time', '')}" for r in records}
    
    for c_path in csv_candidates:
        if os.path.exists(c_path):
            try:
                with open(c_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    persons = {p["name"].upper(): p for p in load_persons()}
                    
                    for row in reader:
                        if not row or row[0].startswith("#") or len(row) < 3:
                            continue
                        name = row[0].strip().upper()
                        t_str = row[1].strip()
                        d_str = row[2].strip()
                        key = f"{name}_{d_str}_{t_str}"
                        
                        if key not in existing_keys:
                            p_info = persons.get(name, {})
                            status = "On Time"
                            try:
                                t_obj = datetime.strptime(t_str, "%H:%M:%S").time()
                                settings = load_settings()
                                start_t = datetime.strptime(settings.get("office_start_time", "09:00"), "%H:%M").time()
                                grace_min = settings.get("late_grace_minutes", 15)
                                late_limit = (datetime.combine(date.today(), start_t) + timedelta(minutes=grace_min)).time()
                                if t_obj > late_limit:
                                    status = "Late"
                            except Exception:
                                status = "Present"
                                
                            records.append({
                                "id": f"ATT-{int(time.time() * 1000)}-{len(records)}",
                                "name": name,
                                "displayName": p_info.get("displayName", name.replace("_", " ").title()),
                                "department": p_info.get("department", "General"),
                                "role": p_info.get("role", "Member"),
                                "time": t_str,
                                "date": d_str,
                                "status": status,
                                "confidence": 98.5,
                                "method": "AI Facial Recognition",
                                "snapshot": p_info.get("image", ""),
                                "timestamp": int(time.time() * 1000)
                            })
                            existing_keys.add(key)
            except Exception as e:
                print(f"Error reading CSV: {e}")

    records.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)
    _in_memory_records = records
    return records

def save_attendance_records(records: List[Dict[str, Any]]):
    global _in_memory_records
    _in_memory_records = records
    try:
        with open(ATTENDANCE_JSON, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    except Exception as e:
        print(f"Disk save attendance warning: {e}")

def append_to_csv(name: str, t_str: str, d_str: str):
    try:
        file_exists = os.path.exists(ATTENDANCE_CSV)
        has_content = file_exists and os.path.getsize(ATTENDANCE_CSV) > 0
        needs_newline = False
        if has_content:
            with open(ATTENDANCE_CSV, "rb") as f:
                f.seek(-1, os.SEEK_END)
                last_char = f.read(1)
                if last_char != b"\n":
                    needs_newline = True

        with open(ATTENDANCE_CSV, "a+", encoding="utf-8") as f:
            if not has_content:
                f.write("# Name,Time,Date\n")
            elif needs_newline:
                f.write("\n")
            f.write(f"{name},{t_str},{d_str}\n")
    except Exception as e:
        print(f"Disk append CSV warning: {e}")

# WebSocket Live Broadcast Helper
async def broadcast_event(event_type: str, data: Any):
    if not connected_websockets:
        return
    message = json.dumps({"type": event_type, "data": data, "timestamp": time.time()})
    dead_sockets = []
    for ws in connected_websockets:
        try:
            await ws.send_text(message)
        except Exception:
            dead_sockets.append(ws)
    for ws in dead_sockets:
        if ws in connected_websockets:
            connected_websockets.remove(ws)

# Models
class MarkAttendanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    confidence: Optional[float] = Field(default=96.0, ge=0, le=100)
    method: Optional[str] = Field(default="AI Facial Recognition", max_length=80)
    snapshot: Optional[str] = Field(default=None, max_length=8_000_000)
    deviceInfo: Optional[str] = Field(default="Front Door AI Kiosk", max_length=160)

class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    office_start_time: str = Field(min_length=5, max_length=5)
    late_grace_minutes: int = Field(ge=0, le=240)
    cooldown_seconds: int = Field(ge=0, le=86400)
    confidence_threshold: float = Field(ge=0, le=1)
    sound_effects_enabled: bool
    speech_announcement_enabled: bool
    organization_name: str = Field(min_length=1, max_length=120)
    theme_mode: Optional[str] = Field(default="dark", max_length=20)

class PersonCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    displayName: Optional[str] = Field(default=None, max_length=120)
    department: Optional[str] = Field(default="Engineering", max_length=120)
    role: Optional[str] = Field(default="Team Member", max_length=120)
    email: Optional[str] = Field(default=None, max_length=254)
    imageBase64: Optional[str] = Field(default=None, max_length=8_000_000)

class FrameRecognizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frameBase64: str = Field(min_length=20, max_length=8_000_000)

# ----------------- AI Vision & Recognition Engines ----------------- #
CASCADE_PATH = os.path.join(DATA_DIR, "haarcascade_frontalface_default.xml")
face_cascade = None
HAS_CV2 = False
HAS_FACE_RECOGNITION = False

try:
    import face_recognition
    HAS_FACE_RECOGNITION = True
except Exception as e:
    print(f"Notice: face_recognition unavailable ({e}). Deep neural matching disabled; using OpenCV/fallback.")

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
    for c_path in [CASCADE_PATH, os.path.join(BASE_DIR, "data", "haarcascade_frontalface_default.xml")]:
        if os.path.exists(c_path):
            try:
                face_cascade = cv2.CascadeClassifier(c_path)
                break
            except Exception:
                pass
except Exception as e:
    print(f"Notice: OpenCV / NumPy unavailable in this environment ({e}). Running in resilient fallback mode.")
    HAS_CV2 = False

# High-Performance In-Memory 128D Face Encodings Cache (Name -> np.ndarray)
known_face_encodings_cache: Dict[str, Any] = {}

def compute_face_encoding_from_file(img_path: str) -> Optional[Any]:
    """Safely compute 128-d face embedding from an image file on disk."""
    if not HAS_FACE_RECOGNITION or not os.path.exists(img_path):
        return None
    try:
        loaded_img = face_recognition.load_image_file(img_path)
        encs = face_recognition.face_encodings(loaded_img)
        if encs:
            return encs[0]
    except Exception as e:
        print(f"Encoding compute error on {img_path}: {e}")
    return None

def reload_face_encodings_cache():
    """Precompute and cache 128D face encodings for all enrolled staff."""
    global known_face_encodings_cache
    if not HAS_FACE_RECOGNITION:
        return
    cache = {}
    search_dirs = [IMAGES_DIR, os.path.join(BASE_DIR, "Images")]
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        for fname in os.listdir(d):
            name, ext = os.path.splitext(fname)
            if ext.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                uname = name.upper()
                if uname not in cache:
                    fpath = os.path.join(d, fname)
                    enc = compute_face_encoding_from_file(fpath)
                    if enc is not None:
                        cache[uname] = enc
    known_face_encodings_cache = cache
    print(f"AI Face Recognition Engine: Cached {len(known_face_encodings_cache)} staff facial embeddings.")

# Warm-up encoding cache on startup
try:
    reload_face_encodings_cache()
except Exception as e:
    print(f"Encoding cache warmup notice: {e}")

# ----------------- REST API Endpoints ----------------- #

@app.get("/api/supabase-config")
async def supabase_config():
    """Expose only the public Supabase client configuration to the browser."""
    url = os.environ.get("SUPABASE_URL", "")
    publishable_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
    return {"url": url, "publishableKey": publishable_key}

@app.get("/health")
async def health_check():
    """System Diagnostic and Production Health Check Endpoint"""
    engine_name = "face_recognition (dlib 128D ResNet)" if HAS_FACE_RECOGNITION else ("opencv-vision" if HAS_CV2 else "resilient-fallback")
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "engine": engine_name,
        "deepFaceRecognitionAvailable": HAS_FACE_RECOGNITION,
        "openCVAvailable": HAS_CV2,
        "cachedFaceEmbeddings": len(known_face_encodings_cache),
        "totalEnrolledStaff": len(load_persons()),
        "version": "2.0.0"
    }

@app.get("/api/status")
async def get_system_status():
    persons = load_persons()
    records = load_attendance_records()
    today_str = datetime.now().strftime("%d/%m/%Y")
    today_records = [r for r in records if r.get("date") == today_str]
    unique_present_today = len({r["name"].upper() for r in today_records})
    
    return {
        "status": "online",
        "systemTime": datetime.now().isoformat(),
        "totalRegistered": len(persons),
        "presentToday": unique_present_today,
        "totalLogsToday": len(today_records),
        "version": "2.0.0"
    }

@app.get("/api/attendance")
async def get_attendance(
    search: Optional[str] = None,
    date_filter: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    records = load_attendance_records()
    filtered = records

    if search:
        s = search.lower()
        filtered = [r for r in filtered if s in r.get("name", "").lower() or s in r.get("displayName", "").lower()]

    if date_filter:
        filtered = [r for r in filtered if r.get("date") == date_filter]

    if department and department != "All":
        filtered = [r for r in filtered if r.get("department", "").lower() == department.lower()]

    if status and status != "All":
        filtered = [r for r in filtered if r.get("status", "").lower() == status.lower()]

    total = len(filtered)
    paged = filtered[offset: offset + limit]

    return {
        "total": total,
        "records": paged,
        "limit": limit,
        "offset": offset
    }

@app.post("/api/attendance/mark")
async def mark_attendance(req: MarkAttendanceRequest):
    settings = load_settings()
    name_upper = req.name.strip().upper()
    now = datetime.now()
    t_str = now.strftime("%H:%M:%S")
    d_str = now.strftime("%d/%m/%Y")
    now_ts = time.time()

    # Check anti-duplicate cooldown
    cooldown = settings.get("cooldown_seconds", 300)
    last_time = last_mark_timestamps.get(name_upper, 0)
    time_since = now_ts - last_time

    if time_since < cooldown:
        remaining = int(cooldown - time_since)
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "alreadyMarked": True,
                "name": name_upper,
                "message": f"Attendance for {name_upper} already marked recently. Please wait {remaining}s.",
                "remainingCooldown": remaining
            }
        )

    # Save snapshot if provided
    snapshot_url = ""
    if req.snapshot and req.snapshot.startswith("data:image"):
        try:
            header, encoded = req.snapshot.split(",", 1)
            img_data = base64.b64decode(encoded)
            snap_filename = f"snap_{name_upper}_{int(now_ts)}.jpg"
            snap_path = os.path.join(SNAPSHOTS_DIR, snap_filename)
            with open(snap_path, "wb") as f:
                f.write(img_data)
            snapshot_url = f"/api/snapshots/{snap_filename}"
        except Exception as e:
            print(f"Snapshot save error: {e}")

    # Look up person info
    persons = {p["name"].upper(): p for p in load_persons()}
    p_info = persons.get(name_upper, {})
    if not snapshot_url:
        snapshot_url = p_info.get("image", "")

    # Calculate On-Time vs Late
    status = "On Time"
    try:
        start_t = datetime.strptime(settings["office_start_time"], "%H:%M").time()
        grace_min = settings["late_grace_minutes"]
        late_limit = (datetime.combine(date.today(), start_t) + timedelta(minutes=grace_min)).time()
        if now.time() > late_limit:
            status = "Late"
    except Exception:
        status = "Present"

    new_record = {
        "id": f"ATT-{int(now_ts * 1000)}",
        "name": name_upper,
        "displayName": p_info.get("displayName", name_upper.replace("_", " ").title()),
        "department": p_info.get("department", "General"),
        "role": p_info.get("role", "Team Member"),
        "time": t_str,
        "date": d_str,
        "status": status,
        "confidence": round(req.confidence or 98.0, 1),
        "method": req.method or "AI Facial Recognition",
        "snapshot": snapshot_url,
        "deviceInfo": req.deviceInfo,
        "timestamp": int(now_ts * 1000)
    }

    # Save to JSON & Append to CSV
    records = load_attendance_records()
    records.insert(0, new_record)
    save_attendance_records(records)
    append_to_csv(name_upper, t_str, d_str)

    # Update cooldown memory
    last_mark_timestamps[name_upper] = now_ts

    # Broadcast event via WebSockets
    await broadcast_event("NEW_ATTENDANCE", new_record)

    return {
        "success": True,
        "alreadyMarked": False,
        "record": new_record,
        "message": f"Welcome {new_record['displayName']}! Attendance marked as {status} at {t_str}."
    }

@app.post("/api/recognize_frame")
async def recognize_camera_frame(req: FrameRecognizeRequest):
    if not req.frameBase64 or not req.frameBase64.startswith("data:image"):
        raise HTTPException(status_code=400, detail="Invalid frame")
    
    persons = load_persons()
    if not persons:
        return {"matched": False, "message": "No enrolled staff available in directory"}

    try:
        header, encoded = req.frameBase64.split(",", 1)
        frame_bytes = base64.b64decode(encoded)
        
        best_name = None
        best_confidence = 0.0
        method_used = "AI Facial Recognition"
        
        # 1. Primary Engine: High-Precision 128D Deep Facial Recognition
        if HAS_FACE_RECOGNITION and known_face_encodings_cache:
            try:
                pil_img = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
                img_rgb = np.array(pil_img)
                
                # Fast downsample if frame is excessively large
                h, w, _ = img_rgb.shape
                if w > 640:
                    scale = 640.0 / w
                    small_w = int(w * scale)
                    small_h = int(h * scale)
                    pil_small = pil_img.resize((small_w, small_h), Image.Resampling.BILINEAR)
                    frame_for_detect = np.array(pil_small)
                else:
                    frame_for_detect = img_rgb

                # Detect face locations & compute 128D encodings
                face_locations = face_recognition.face_locations(frame_for_detect, model="hog")
                if face_locations:
                    face_encs = face_recognition.face_encodings(frame_for_detect, face_locations)
                    
                    if face_encs and known_face_encodings_cache:
                        known_names = list(known_face_encodings_cache.keys())
                        known_encs = [known_face_encodings_cache[k] for k in known_names]
                        
                        settings = load_settings()
                        threshold = float(settings.get("confidence_threshold", 0.55))

                        for face_enc in face_encs:
                            distances = face_recognition.face_distance(known_encs, face_enc)
                            if len(distances) > 0:
                                min_idx = int(np.argmin(distances))
                                min_dist = float(distances[min_idx])
                                
                                if min_dist <= threshold:
                                    best_name = known_names[min_idx]
                                    # Convert euclidean distance (0.0 to 0.6) to realistic match percentage
                                    calc_conf = round(max(80.0, min(99.6, (1.0 - (min_dist / 1.1)) * 100)), 1)
                                    best_confidence = calc_conf
                                    method_used = "AI Facial Recognition (128D Deep Net)"
                                    break
            except Exception as e_fr:
                print(f"Deep face_recognition error: {e_fr}")

        # 2. Resilient Tier 2 Fallback: OpenCV ORB / Histogram Matching
        if not best_name and HAS_CV2:
            try:
                nparr = np.frombuffer(frame_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    orb = cv2.ORB_create(nfeatures=600)
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                    
                    kp_frame, des_frame = orb.detectAndCompute(img, None)
                    img_flipped = cv2.flip(img, 1)
                    kp_flipped, des_flipped = orb.detectAndCompute(img_flipped, None)

                    if (des_frame is not None and len(des_frame) >= 5) or (des_flipped is not None and len(des_flipped) >= 5):
                        h_small = cv2.resize(img, (120, 120))
                        hist_frame = cv2.calcHist([h_small], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                        cv2.normalize(hist_frame, hist_frame, 0, 1, cv2.NORM_MINMAX)

                        best_composite = 0.0
                        for check_dir in [IMAGES_DIR, os.path.join(BASE_DIR, "Images")]:
                            if not os.path.exists(check_dir):
                                continue
                            for fname in os.listdir(check_dir):
                                if not fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                    continue
                                fpath = os.path.join(check_dir, fname)
                                ref_img = cv2.imread(fpath)
                                if ref_img is None:
                                    continue

                                kp_ref, des_ref = orb.detectAndCompute(ref_img, None)
                                if des_ref is None:
                                    continue

                                matches_orig = bf.match(des_ref, des_frame) if des_frame is not None else []
                                good_orig = [m for m in matches_orig if m.distance < 60]

                                matches_flip = bf.match(des_ref, des_flipped) if des_flipped is not None else []
                                good_flip = [m for m in matches_flip if m.distance < 60]

                                good_count = max(len(good_orig), len(good_flip))

                                ref_small = cv2.resize(ref_img, (120, 120))
                                hist_ref = cv2.calcHist([ref_small], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                                cv2.normalize(hist_ref, hist_ref, 0, 1, cv2.NORM_MINMAX)
                                hist_sim = max(0.0, cv2.compareHist(hist_frame, hist_ref, cv2.HISTCMP_CORREL))

                                match_ratio = good_count / max(len(des_ref), 1)
                                composite = (match_ratio * 0.65) + (hist_sim * 0.35)

                                if composite > best_composite and (good_count >= 12 or (good_count >= 8 and hist_sim > 0.4)):
                                    best_composite = composite
                                    best_name = os.path.splitext(fname)[0].upper()
                                    best_confidence = round(min(98.5, max(80.0, 75.0 + (composite * 25.0))), 1)
                                    method_used = "Computer Vision Feature Match"
            except Exception as e_cv:
                print(f"OpenCV fallback error: {e_cv}")

        if best_name:
            confidence = best_confidence or 98.0
            mark_res = await mark_attendance(MarkAttendanceRequest(
                name=best_name,
                confidence=confidence,
                method=method_used,
                snapshot=req.frameBase64
            ))
            
            if isinstance(mark_res, JSONResponse):
                res_dict = json.loads(mark_res.body.decode())
                return {
                    "matched": True,
                    "name": best_name,
                    "confidence": confidence,
                    "alreadyMarked": True,
                    "message": res_dict.get("message")
                }
            
            return {
                "matched": True,
                "name": best_name,
                "confidence": confidence,
                "record": mark_res.get("record"),
                "message": mark_res.get("message")
            }
        
        return {"matched": False, "message": "Face not recognized in staff directory"}
    except Exception as e:
        print(f"Recognition error: {e}")
        return {"matched": False, "error": str(e)}


@app.delete("/api/attendance/{record_id}")
async def delete_attendance_record(record_id: str):
    records = load_attendance_records()
    initial_len = len(records)
    records = [r for r in records if r.get("id") != record_id]
    if len(records) == initial_len:
        raise HTTPException(status_code=404, detail="Record not found")
    save_attendance_records(records)
    await broadcast_event("ATTENDANCE_DELETED", {"id": record_id})
    return {"success": True, "message": "Record deleted"}

@app.get("/api/attendance/export")
async def export_attendance(format: str = Query("csv")):
    records = load_attendance_records()
    if format.lower() == "json":
        return JSONResponse(content=records, headers={"Content-Disposition": "attachment; filename=attendance_export.json"})
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Display Name", "Department", "Role", "Date", "Time", "Status", "Confidence (%)", "Method"])
    for r in records:
        writer.writerow([
            r.get("id", ""),
            r.get("name", ""),
            r.get("displayName", ""),
            r.get("department", ""),
            r.get("role", ""),
            r.get("date", ""),
            r.get("time", ""),
            r.get("status", ""),
            r.get("confidence", ""),
            r.get("method", "")
        ])
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

# ----------------- Persons / Face Roster API ----------------- #

@app.get("/api/persons")
async def get_persons(request: Request):
    try:
        people_rows = supabase_list_people(request.state.organization_id)
        persons = [{
            "id": p["id"], "name": p["name"], "displayName": p["name"],
            "employeeId": p["employee_id"], "image": create_signed_image_url(p.get("image_path", "")),
            "registeredDate": p.get("created_at", "")[:10], "active": True,
        } for p in people_rows]
    except SupabaseRepositoryError:
        persons = load_persons()
    records = load_attendance_records()
    
    # Enrich with attendance stats
    for p in persons:
        uname = p["name"].upper()
        p_records = [r for r in records if r.get("name", "").upper() == uname]
        p["totalAttendance"] = len(p_records)
        p["lastSeen"] = p_records[0]["date"] + " " + p_records[0]["time"] if p_records else "Never"
    
    return persons

@app.post("/api/persons")
async def create_person(req: PersonCreateRequest, request: Request):
    uname = req.name.strip().upper()
    if not uname:
        raise HTTPException(status_code=400, detail="Person name is required")
    
    persons = load_persons()
    for p in persons:
        if p["name"].upper() == uname:
            raise HTTPException(status_code=400, detail=f"Person '{uname}' is already registered.")

    # Save image
    img_filename = f"{uname.lower().replace(' ', '_')}.jpg"
    img_path = os.path.join(IMAGES_DIR, img_filename)
    
    if req.imageBase64 and req.imageBase64.startswith("data:image"):
        try:
            header, encoded = req.imageBase64.split(",", 1)
            img_data = base64.b64decode(encoded)
            with open(img_path, "wb") as f:
                f.write(img_data)
        except Exception as e:
            print(f"Warning saving image: {e}")
    else:
        try:
            img = Image.new("RGB", (300, 300), color=(30, 41, 59))
            img.save(img_path)
        except Exception as e:
            print(f"Warning saving placeholder image: {e}")

    new_person = {
        "id": f"EMP-{len(persons) + 1:04d}",
        "name": uname,
        "displayName": req.displayName or uname.replace("_", " ").title(),
        "department": req.department or "Engineering",
        "role": req.role or "Team Member",
        "email": req.email or f"{uname.lower().replace(' ', '.')}@company.ai",
        "image": f"/api/persons/photo/{img_filename}",
        "registeredDate": datetime.now().strftime("%Y-%m-%d"),
        "active": True
    }

    try:
        image_path = ""
        if req.imageBase64 and req.imageBase64.startswith("data:image"):
            _, encoded = req.imageBase64.split(",", 1)
            image_path = upload_face_image(request.state.organization_id, img_filename, base64.b64decode(encoded))
        stored_person = supabase_create_person(request.state.organization_id, {
            "name": uname,
            "employee_id": new_person["id"],
            "image_path": image_path or None,
        })
        new_person["id"] = stored_person["id"]
        new_person["image"] = create_signed_image_url(image_path)
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=503, detail="Supabase enrollment service unavailable") from exc

    # Immediately compute and register face embedding in memory
    if HAS_FACE_RECOGNITION and os.path.exists(img_path):
        new_enc = compute_face_encoding_from_file(img_path)
        if new_enc is not None:
            known_face_encodings_cache[uname] = new_enc

    await broadcast_event("PERSON_REGISTERED", new_person)
    return {"success": True, "person": new_person, "message": f"Successfully enrolled {new_person['displayName']}."}

@app.delete("/api/persons/{name}")
async def delete_person(name: str, request: Request):
    uname = name.strip().upper()
    persons = load_persons()
    deleted_person = next((p for p in persons if p["name"].upper() == uname), None)
    initial_len = len(persons)
    persons = [p for p in persons if p["name"].upper() != uname]
    
    if len(persons) == initial_len:
        raise HTTPException(status_code=404, detail=f"Person '{uname}' not found")
    
    try:
        if deleted_person and deleted_person.get("id"):
            supabase_delete_person(request.state.organization_id, deleted_person["id"])
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=503, detail="Supabase deletion service unavailable") from exc

    # Evict from facial embedding cache
    known_face_encodings_cache.pop(uname, None)

    # Attempt to remove image file
    for check_dir in [IMAGES_DIR, os.path.join(BASE_DIR, "Images")]:
        if os.path.exists(check_dir):
            for fname in os.listdir(check_dir):
                if os.path.splitext(fname)[0].upper() == uname:
                    try:
                        os.remove(os.path.join(check_dir, fname))
                    except Exception:
                        pass

    await broadcast_event("PERSON_DELETED", {"name": uname})
    return {"success": True, "message": f"Person '{uname}' deleted."}

DEFAULT_AVATAR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>"""

@app.get("/api/persons/photo/{filename}")
async def get_person_photo(filename: str):
    for d in [IMAGES_DIR, os.path.join(BASE_DIR, "Images")]:
        path = os.path.join(d, filename)
        if os.path.exists(path) and os.path.isfile(path):
            return FileResponse(path)
    return Response(content=DEFAULT_AVATAR_SVG, media_type="image/svg+xml")

@app.get("/api/snapshots/{filename}")
async def get_snapshot_photo(filename: str):
    for d in [SNAPSHOTS_DIR, os.path.join(BASE_DIR, "data", "snapshots")]:
        path = os.path.join(d, filename)
        if os.path.exists(path) and os.path.isfile(path):
            return FileResponse(path)
    return Response(content=DEFAULT_AVATAR_SVG, media_type="image/svg+xml")

# ----------------- Analytics & Intelligence API ----------------- #

@app.get("/api/analytics")
async def get_analytics():
    persons = load_persons()
    records = load_attendance_records()
    total_persons = len(persons)
    
    today_str = datetime.now().strftime("%d/%m/%Y")
    today_records = [r for r in records if r.get("date") == today_str]
    
    unique_present_names = {r["name"].upper() for r in today_records}
    present_count = len(unique_present_names)
    absent_count = max(0, total_persons - present_count)
    
    on_time_count = sum(1 for r in today_records if r.get("status") == "On Time")
    late_count = sum(1 for r in today_records if r.get("status") == "Late")
    
    attendance_rate = round((present_count / total_persons * 100), 1) if total_persons > 0 else 0
    on_time_rate = round((on_time_count / present_count * 100), 1) if present_count > 0 else 100

    # Hourly check-in distribution (from 06:00 to 20:00)
    hourly_distribution = {f"{h:02d}:00": 0 for h in range(6, 21)}
    for r in today_records:
        try:
            t = datetime.strptime(r.get("time", ""), "%H:%M:%S")
            hour_key = f"{t.hour:02d}:00"
            if hour_key in hourly_distribution:
                hourly_distribution[hour_key] += 1
        except Exception:
            pass

    # Past 7 Days Trend
    trend_7days = []
    for i in range(6, -1, -1):
        target_date = datetime.now() - timedelta(days=i)
        d_str = target_date.strftime("%d/%m/%Y")
        label = target_date.strftime("%a %d")
        d_records = [r for r in records if r.get("date") == d_str]
        present_d = len({r["name"].upper() for r in d_records})
        late_d = sum(1 for r in d_records if r.get("status") == "Late")
        trend_7days.append({
            "date": d_str,
            "label": label,
            "present": present_d,
            "late": late_d,
            "total": total_persons
        })

    # Department Breakdown
    dept_map = {}
    for p in persons:
        dept = p.get("department", "Other")
        dept_map[dept] = dept_map.get(dept, 0) + 1
        
    dept_breakdown = [{"department": d, "count": c} for d, c in dept_map.items()]

    return {
        "summary": {
            "totalRegistered": total_persons,
            "presentToday": present_count,
            "absentToday": absent_count,
            "onTimeToday": on_time_count,
            "lateToday": late_count,
            "attendanceRate": attendance_rate,
            "onTimeRate": on_time_rate,
            "peakHour": max(hourly_distribution.items(), key=lambda x: x[1])[0] if any(hourly_distribution.values()) else "09:00"
        },
        "hourly": [{"hour": h, "count": c} for h, c in hourly_distribution.items()],
        "trend7Days": trend_7days,
        "departmentBreakdown": dept_breakdown,
        "recentLogs": records[:10]
    }

# ----------------- Settings API ----------------- #

@app.get("/api/settings")
async def get_settings():
    return load_settings()

@app.post("/api/settings")
async def update_settings(settings: SettingsModel):
    data = settings.model_dump()
    save_settings(data)
    await broadcast_event("SETTINGS_UPDATED", data)
    return {"success": True, "settings": data, "message": "Settings updated successfully."}

# ----------------- WebSocket Live Feed ----------------- #

@app.websocket("/ws/live")
async def websocket_live_feed(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    try:
        # Send initial handshake state
        await websocket.send_text(json.dumps({
            "type": "INIT_STATE",
            "data": {
                "serverTime": datetime.now().isoformat(),
                "connectedClients": len(connected_websockets)
            }
        }))
        while True:
            # Keep alive and receive client pings/messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)
    except Exception:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)

# Serve Frontend Static Assets and Main Index
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>AI Attendance System - Ready</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
