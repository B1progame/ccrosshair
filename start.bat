@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [start] Missing virtual environment. Running setup...
    call setup.bat
    if errorlevel 1 exit /b 1
)

echo [start] Launching Crosshair Overlay...
".venv\Scripts\pythonw.exe" main.py
exit /b %errorlevel%
