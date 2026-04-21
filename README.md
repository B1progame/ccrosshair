# Crosshair Overlay

Crosshair Overlay is a Windows desktop app for showing a customizable crosshair on top of your games and giving you a clean control center for your presets, imports, creator tools, and runtime automation.

It is built with `PySide6`, uses Windows-native overlay behavior, and stores your personal crosshair library in `%APPDATA%\CrosshairOverlay`.

**Highlights**
- Always-on-top crosshair overlay with live style updates
- Built-in crosshair library with preview, detail editing, favorites, and export
- Creator page for designing your own grid-based crosshairs
- Import and export support for `.xhair`, `.xpack`, and legacy `.chgrid` / `.chpack`
- Game automation with Steam and Epic library detection plus manual `.exe` imports
- Per-game crosshair profiles and optional fullscreen-only behavior
- System tray support so the app can stay running in the background
- Theme controls, accent color customization, and shared global size controls
- Experimental Beta Zoom page with hotkey-based live zoom preview

**Latest Update (1.2.0)**
- UI changes and bug fixes
- Full details: see `CHANGELOG.md`

**Platform**
- Windows 10 or Windows 11

**Screens And Core Areas**
- `Home`: quick enable/disable controls, current crosshair preview, and fast library access
- `Crosshairs`: browse built-ins, favorites, imports, and saved variants
- `Creator`: build your own crosshair visually and save it back into the library
- `Games`: open a game-specific menu, assign a crosshair, and enable auto-apply rules
- `Settings`: choose theme mode, accent color, storage location, and beta feature visibility
- `Beta`: experimental zoom overlay page that appears only when enabled in Settings

**Quick Start**
1. Run `setup.bat`
2. Run `start.bat`

That is the easiest source-based workflow for local use.

**Manual Run**
1. Create a virtual environment:

```powershell
python -m venv .venv
```

2. Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Launch the app:

```powershell
.\.venv\Scripts\pythonw.exe main.py
```

**Build A Normal Windows Installer**
This repository now includes a full Windows packaging path using `PyInstaller` plus `Inno Setup`.

**What You Need**
- Python 3.11 or newer available in `PATH`
- Inno Setup 6 installed locally

**One-Click Build**
1. Install Inno Setup 6
2. Run:

```powershell
build_installer.bat
```

The build script will:
- reuse or create the local virtual environment
- install runtime and build dependencies
- generate a Windows `.ico` from the app SVG logo
- build a portable app folder with `PyInstaller`
- compile an installer with `Inno Setup`

**Build Output**

| Output | Location |
| --- | --- |
| Portable app | `dist\CrosshairOverlay\CrosshairOverlay.exe` |
| Installer | `installer\output\CrosshairOverlay-Setup-<version>.exe` |

**Installer Behavior**
- installs per-user into `%LOCALAPPDATA%\Programs\Crosshair Overlay`
- creates Start Menu shortcuts
- can optionally create a Desktop shortcut
- adds normal uninstall support
- can launch the app directly after setup finishes

**First Launch Notes**
- The app stores settings in `%APPDATA%\CrosshairOverlay\settings.json`
- The default crosshair library is stored in `%APPDATA%\CrosshairOverlay\crosshairs`
- Imported packs, custom variants, creator saves, and exports are organized into their own folders automatically

**Game Detection**
The app can discover games from:
- Steam libraries
- Epic Games manifests
- manual `.exe` imports that you add yourself

You can open any detected game row in the `Games` page and choose:
- whether the game profile is enabled
- which crosshair should auto-apply for that game
- whether you want to jump straight into the library to choose a better preset

**Crosshair Formats**
The project supports multiple crosshair file formats:

| Format | Purpose |
| --- | --- |
| `.xhair` | Single crosshair definition |
| `.xpack` | Pack of multiple crosshairs |
| `.chgrid` | Creator/grid format |
| `.chpack` | Legacy import format |

**Research Files**
If you want to expand the built-in library, the current research references live in:
- `docs/crosshair_research.md`
- `docs/crosshair_reference_catalog.json`

**Project Layout**

| Path | Purpose |
| --- | --- |
| `main.py` | App entry point |
| `src/crosshair_overlay/app.py` | Main controller and runtime logic |
| `src/crosshair_overlay/ui/` | Main window, pages, sidebar, and shared UI components |
| `src/crosshair_overlay/crosshairs/` | Built-in presets, library management, and import/export logic |
| `src/crosshair_overlay/assets/` | App branding assets |
| `installer/` | Inno Setup files and Windows packaging helpers |

**Developer Workflow**
- `setup.bat` prepares the local virtual environment and runtime dependencies
- `start.bat` launches the app with `pythonw`
- `build_installer.bat` creates a distributable Windows installer

**Troubleshooting**
- If the overlay does not appear above a game, try borderless fullscreen instead of exclusive fullscreen.
- Some protected or anti-cheat-heavy titles may limit screen capture or overlay behavior.
- If a game is missing from the library, use the manual import option on the `Games` page and point it at the main `.exe`.
- If the Beta page is missing, enable `Show Beta Features in Sidebar` in `Settings`.
- If the installer build fails, make sure Inno Setup 6 is installed and available in one of its default Windows locations.

**For Contributors**
- Keep crosshair additions geometry-focused so similar presets stay grouped together.
- Reuse existing renderer families when a preset is only a style variation.
- Treat the Beta Zoom tools as experimental and expect iteration there.

**License**
A repository-level custom license is included in [LICENSE](/C:/Users/bslid.BENJI-PC/OneDrive/Dokumente/.CODES/verkaufen/flo/crosshair/v1/LICENSE). The installer uses the same license text so the GitHub project and Windows installer stay aligned.
