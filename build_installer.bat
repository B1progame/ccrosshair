@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "ROOT=%cd%"
set "PYTHON=.venv\Scripts\python.exe"
set "ICON_SCRIPT=installer\make_windows_icon.py"
set "ICON_OUTPUT=installer\build\CrosshairOverlay.ico"
set "ISS_SCRIPT=installer\CrosshairOverlay.iss"
set "VERSION_FILE=src\crosshair_overlay\version.txt"
set "DIST_DIR=%ROOT%\dist\CrosshairOverlay"
set "OUTPUT_DIR=%ROOT%\installer\output"
set "ISCC="

if not exist "%PYTHON%" (
    echo [build] Missing virtual environment. Running setup...
) else (
    echo [build] Reusing existing virtual environment...
)

call setup.bat
if errorlevel 1 goto :error

echo [build] Installing build requirements...
"%PYTHON%" -m pip install -r requirements-build.txt
if errorlevel 1 goto :error

if not exist "installer\build" mkdir "installer\build"
if not exist "installer\output" mkdir "installer\output"

echo [build] Generating Windows icon from SVG...
"%PYTHON%" "%ICON_SCRIPT%" "src\crosshair_overlay\assets\logo.svg" "%ICON_OUTPUT%"
if errorlevel 1 (
    echo [build] Icon generation failed. The build will continue without a custom EXE icon.
    set "ICON_READY=0"
) else (
    set "ICON_READY=1"
)

echo [build] Building portable app with PyInstaller...
if "%ICON_READY%"=="1" (
    "%PYTHON%" -m PyInstaller --noconfirm --clean --onedir --windowed --name CrosshairOverlay --paths "%ROOT%\src" --collect-submodules crosshair_overlay --add-data "src\crosshair_overlay\assets;crosshair_overlay\assets" --add-data "src\crosshair_overlay\version.txt;crosshair_overlay" --icon "%ICON_OUTPUT%" main.py
) else (
    "%PYTHON%" -m PyInstaller --noconfirm --clean --onedir --windowed --name CrosshairOverlay --paths "%ROOT%\src" --collect-submodules crosshair_overlay --add-data "src\crosshair_overlay\assets;crosshair_overlay\assets" --add-data "src\crosshair_overlay\version.txt;crosshair_overlay" main.py
)
if errorlevel 1 goto :error

if not exist "%VERSION_FILE%" (
    echo [build] Version file not found: %VERSION_FILE%
    goto :error
)

set /p APP_VERSION=<"%VERSION_FILE%"
if "%APP_VERSION%"=="" (
    echo [build] Version file is empty: %VERSION_FILE%
    goto :error
)

call :find_iscc
if not defined ISCC (
    echo [build] Inno Setup 6 was not found.
    echo [build] Install it from https://jrsoftware.org/isinfo.php and run this script again.
    goto :error
)

echo [build] Compiling Windows installer...
"%ISCC%" "/DAppVersion=%APP_VERSION%" "/DRootDir=%ROOT%" "/DDistDir=%DIST_DIR%" "/DOutputDir=%OUTPUT_DIR%" "%ISS_SCRIPT%"
if errorlevel 1 goto :error

echo.
echo [build] Success.
echo [build] Portable app: %DIST_DIR%
echo [build] Installer output: %OUTPUT_DIR%
exit /b 0

:find_iscc
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
exit /b 0

:error
echo.
echo [build] Build failed.
exit /b 1
