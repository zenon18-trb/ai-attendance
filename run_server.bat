@echo off
title AI Face Recognition Attendance System
echo ===================================================
echo   Starting AI Attendance Web Application...
echo ===================================================

cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    start http://localhost:8000
    ".venv\Scripts\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
) else (
    start http://localhost:8000
    python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
)
pause
