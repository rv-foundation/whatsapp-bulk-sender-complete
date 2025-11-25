; ---------------------------------------------------------------
; WhatsApp Bulk Sender - Inno Setup Installer
; Fully patched version for GitHub Actions pipeline
; ---------------------------------------------------------------

[Setup]
AppName=WhatsApp Bulk Sender
AppVersion=1.0
DefaultDirName={pf}\WhatsAppBulkSender
DefaultGroupName=WhatsApp Bulk Sender
OutputDir=installer
OutputBaseFilename=WhatsAppBulkSender_Setup
SetupIconFile=icon.ico
PrivilegesRequired=admin
Compression=lzma
SolidCompression=yes
DisableProgramGroupPage=yes

[Files]

; -----------------------------
; MAIN APPLICATION EXECUTABLE
; -----------------------------
Source: "dist\app.exe"; DestDir: "{app}"; Flags: ignoreversion

; -----------------------------
; PLAYWRIGHT BROWSER FOLDER
; Ensure Playwright Chromium is bundled
; -----------------------------
Source: "dist\ms-playwright\*"; DestDir: "{app}\ms-playwright"; Flags: ignoreversion recursesubdirs createallsubdirs

; -----------------------------
; RESOURCE FILES
; (Bundled message, image, icon)
; -----------------------------
Source: "message.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "image.jpg"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\WhatsApp Bulk Sender"; Filename: "{app}\app.exe"; WorkingDir: "{app}"
Name: "{commondesktop}\WhatsApp Bulk Sender"; Filename: "{app}\app.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\app.exe"; Description: "Launch WhatsApp Bulk Sender"; Flags: nowait postinstall skipifsilent