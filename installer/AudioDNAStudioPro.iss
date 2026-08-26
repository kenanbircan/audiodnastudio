#define MyAppName "Audio DNA Studio Pro"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Audio DNA Studio Pro"
#define MyAppExeName "AudioDNAStudioPro.exe"

[Setup]
AppId={{B4B2C834-8246-49F4-82F8-90510F447B66}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Audio DNA Studio Pro
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=AudioDNAStudioPro_Setup_1.1.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\AudioDNAStudioPro.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\AudioDNAStudioPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README_WINDOWS11.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\OPEN_SOURCE_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Audio DNA Studio Pro"; Flags: nowait postinstall skipifsilent
