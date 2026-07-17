#define MyAppName "OsuSayoHub"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "cavalinho-xdd"
#define MyAppURL "https://github.com/cavalinho-xdd/osusayohub"
#define MyAppExeName "OsuSayoHub.exe"

[Setup]
; App info
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Default install to user's local app data (per-user install, no admin rights required)
DefaultDirName={localappdata}\Programs\{#MyAppName}
; Set output dir and file name
OutputDir=..\dist
OutputBaseFilename=OsuSayoHub-Installer
; We don't want to ask for admin privileges
PrivilegesRequired=lowest
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\OsuSayoHub\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\OsuSayoHub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
