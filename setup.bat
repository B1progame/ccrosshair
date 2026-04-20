@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating virtual environment...
    python -m venv .venv
)

echo [setup] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo [setup] Dependency installation failed.
    exit /b 1
)

echo [setup] Setup complete.
exit /b 0
