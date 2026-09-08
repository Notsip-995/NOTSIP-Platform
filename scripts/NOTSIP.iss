[Setup]
AppName=NOTSIP
AppVersion=0.9.0
DefaultDirName={localappdata}\NOTSIP
DefaultGroupName=NOTSIP
OutputDir=..\Output
OutputBaseFilename=NOTSIP-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
Uninstallable=yes

[Files]
Source: "..\dist\NOTSIP.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\ui.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\setup.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\src\notsip\*"; DestDir: "{app}\source\notsip"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\tests\*"; DestDir: "{app}\source\tests"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\scripts\*.ps1"; DestDir: "{app}\source\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\pyproject.toml"; DestDir: "{app}\source"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\source"; Flags: ignoreversion
Source: "..\docs\*.md"; DestDir: "{app}\source\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\data"
Name: "{app}\updates"
Name: "{app}\runtime"
Name: "{app}\source"
Name: "{app}\source\tests"
Name: "{app}\source\scripts"
Name: "{app}\source\docs"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "startup"; Description: "Start NOTSIP when you sign in to Windows"; Flags: unchecked

[Icons]
Name: "{group}\NOTSIP"; Filename: "{app}\NOTSIP.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\NOTSIP"; Filename: "{app}\NOTSIP.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\NOTSIP"; Filename: "{app}\NOTSIP.exe"; WorkingDir: "{app}"; Tasks: startup

[Run]
Filename: "{app}\NOTSIP.exe"; Description: "Start NOTSIP"; Flags: nowait postinstall skipifsilent
