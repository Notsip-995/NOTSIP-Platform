[Setup]
AppName=NOTSIP
AppVersion=0.9.0
DefaultDirName={localappdata}\NOTSIP
DefaultGroupName=NOTSIP
OutputBaseFilename=NOTSIP-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
Uninstallable=yes

[Files]
Source: "dist\NOTSIP.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "ui.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "setup.html"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\data"
Name: "{app}\updates"
Name: "{app}\runtime"

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "NOTSIP_DATA_DIR"; ValueData: "{app}\data"; Flags: uninsdeletevalue

[Icons]
Name: "{group}\NOTSIP"; Filename: "{app}\NOTSIP.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\NOTSIP"; Filename: "{app}\NOTSIP.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "startup"; Description: "Start NOTSIP when you sign in to Windows"; Flags: unchecked

[Icons]
Name: "{userstartup}\NOTSIP"; Filename: "{app}\NOTSIP.exe"; WorkingDir: "{app}"; Tasks: startup

[Run]
Filename: "{app}\NOTSIP.exe"; Description: "Start NOTSIP"; Flags: nowait postinstall skipifsilent
