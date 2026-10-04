@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [start] Missing virtual environment. Running setup...
    call setup.bat
    if errorlevel 1 exit /b 1
)

where npm >nul 2>nul
if not errorlevel 1 (
    if not exist "frontend\node_modules" (
        echo [start] Installing locked frontend dependencies...
        call npm ci --prefix frontend
        if errorlevel 1 exit /b 1
    )
    echo [start] Building current React control UI...
    call npm run --prefix frontend build
    if errorlevel 1 exit /b 1
) else (
    if not exist "src\crosshair_overlay\webui\dist\index.html" (
        echo [start] No bundled React UI is available and npm is unavailable.
    )
)

echo [start] Launching Crosshair Overlay...
".venv\Scripts\pythonw.exe" main.py
exit /b %errorlevel%
