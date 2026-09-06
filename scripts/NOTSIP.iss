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

[Files]
Source: "dist\NOTSIP.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "ui.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "setup.html"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\NOTSIP"; Filename: "{app}\NOTSIP.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\NOTSIP"; Filename: "{app}\NOTSIP.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\NOTSIP.exe"; Description: "Start NOTSIP"; Flags: nowait postinstall skipifsilent
