#ifndef AppName
  #define AppName "Crosshair Overlay"
#endif

#ifndef AppVersion
  #define AppVersion "1.5.2"
#endif

#ifndef AppPublisher
  #define AppPublisher "B1progame"
#endif

#ifndef AppPublisherURL
  #define AppPublisherURL "https://github.com/B1progame/ccrosshair"
#endif

#ifndef AppUpdatesURL
  #define AppUpdatesURL "https://github.com/B1progame/ccrosshair/releases/latest"
#endif

#ifndef AppExeName
  #define AppExeName "CrosshairOverlay.exe"
#endif

#ifndef RootDir
  #define RootDir AddBackslash(SourcePath) + ".."
#endif

#ifndef DistDir
  #define DistDir AddBackslash(RootDir) + "dist\\CrosshairOverlay"
#endif

#ifndef OutputDir
  #define OutputDir AddBackslash(RootDir) + "installer\\output"
#endif

#if FileExists(AddBackslash(RootDir) + "installer\\build\\CrosshairOverlay.ico")
  #define SetupIcon AddBackslash(RootDir) + "installer\\build\\CrosshairOverlay.ico"
#endif

#if !FileExists(AddBackslash(DistDir) + AppExeName)
  #error "Portable app build not found. Run build_installer.bat first."
#endif

[Setup]
AppId={{7A5D8182-0C3B-4F94-A22B-B267C5E33927}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppPublisherURL}
AppSupportURL={#AppPublisherURL}
AppUpdatesURL={#AppUpdatesURL}
DefaultDirName={localappdata}\Programs\Crosshair Overlay
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=CrosshairOverlay-Setup-{#AppVersion}
#ifdef SetupIcon
SetupIconFile={#SetupIcon}
#endif
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=no
CloseApplications=yes
CloseApplicationsFilter=CrosshairOverlay.exe
SetupLogging=yes
UsedUserAreasWarning=no
AppReadmeFile={app}\README.md
LicenseFile={#RootDir}\installer\license.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RootDir}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RootDir}\installer\license.txt"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Crosshair Overlay"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall Crosshair Overlay"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Crosshair Overlay"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Crosshair Overlay"; Flags: nowait postinstall skipifsilent
