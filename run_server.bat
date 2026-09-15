@echo off
title AI Face Recognition Attendance System
echo ===================================================
echo   Starting AI Attendance Web Application...
echo ===================================================

cd /d "%~dp0"

set PYTHON_CMD=

if exist ".venv\Scripts\python.exe" (
    set PYTHON_CMD=".venv\Scripts\python.exe"
    goto found_python
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PYTHON_CMD=py
    goto found_python
)

if exist "C:\Python314\python.exe" (
    set PYTHON_CMD="C:\Python314\python.exe"
    goto found_python
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PYTHON_CMD=python
    goto found_python
)

echo [ERROR] No Python installation found! Please install Python 3.10+ or run with py launcher.
pause
exit /b 1

:found_python
echo [*] Using Python: %PYTHON_CMD%
echo [*] Launching FastAPI Web Application on http://localhost:8000 ...

start "" http://localhost:8000
%PYTHON_CMD% -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause

