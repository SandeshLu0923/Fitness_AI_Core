#define MyAppName "Fitness AI Desktop Tracker"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Fitness AI Core"
#define MyAppExeName "FitnessAI-Desktop-Tracker.exe"

[Setup]
AppId={{B5C723B2-9816-40E5-8E6A-61C27819A922}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Fitness AI Desktop Tracker
DefaultGroupName=Fitness AI Core
DisableProgramGroupPage=yes
OutputDir=..\release\installer
OutputBaseFilename=FitnessAI-Desktop-Tracker-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=..\fitness_121040.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\FitnessAI-Desktop-Tracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Fitness AI Desktop Tracker"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Fitness AI Desktop Tracker"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\fitnessai"; ValueType: string; ValueName: ""; ValueData: "URL:Fitness AI Desktop Tracker"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\fitnessai"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\fitnessai\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Fitness AI Desktop Tracker}"; Flags: nowait postinstall skipifsilent
