; Inno Setup script - produces a full Windows installer (setup.exe) around
; the PyInstaller onedir build in dist/Free Claude Code/.
;
; Build with (Inno Setup 6.x, https://jrsoftware.org/isinfo.php):
;   ISCC.exe windows_tray\installer.iss
; (windows_tray\build.bat runs this automatically if ISCC.exe is found.)
;
; Produces: windows_tray\installer_output\FreeClaudeCodeSetup.exe

#define MyAppName "Free Claude Code"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Free Claude Code"
#define MyAppExeName "Free Claude Code.exe"
#define MyDistDir "..\dist\Free Claude Code"

[Setup]
AppId={{B6E6B1D2-6F4B-4B7B-9C7C-FCC0DE5C5A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=FreeClaudeCodeSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; No admin required: installs per-user by default so it works without UAC
; prompts on a locked-down machine. Switch to "admin" + {commonpf} above if
; you'd rather install for all users.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startupicon"; Description: "Start {#MyAppName} automatically when I sign in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Best-effort: ask a running instance to quit before files are removed, so
; Windows doesn't complain about an exe that's still in use mid-uninstall.
; Ignored if it's not running.
Filename: "{cmd}"; Parameters: "/C taskkill /IM ""{#MyAppExeName}"" /F"; Flags: runhidden skipifdoesntexist; RunOnceId: "KillFCCTray"
