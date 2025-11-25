[Setup]
AppName=WhatsApp Bulk Sender
AppVersion=1.0
DefaultDirName={pf}\WhatsAppBulkSender
DefaultGroupName=WhatsApp Bulk Sender
OutputDir=installer
OutputBaseFilename=WhatsAppBulkSender_Setup
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\app.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\ms-playwright\*"; DestDir: "{app}\ms-playwright"; Flags: ignoreversion recursesubdirs
Source: "message.txt"; DestDir: "{app}"
Source: "image.jpg"; DestDir: "{app}"
Source: "icon.ico"; DestDir: "{app}"

[Icons]
Name: "{group}\WhatsApp Bulk Sender"; Filename: "{app}\app.exe"
Name: "{commondesktop}\WhatsApp Bulk Sender"; Filename: "{app}\app.exe"

[Run]
Filename: "{app}\app.exe"; Description: "Launch WhatsApp Bulk Sender"; Flags: nowait postinstall skipifsilent
