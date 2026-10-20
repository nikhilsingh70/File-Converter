; Optional: turns dist\SyntaxConverter into a real Setup.exe with Inno Setup (jrsoftware.org/isinfo.php)
[Setup]
AppName=Syntax Converter
AppVersion=2.0
DefaultDirName={autopf}\Syntax Converter
DefaultGroupName=Syntax Converter
OutputBaseFilename=SyntaxConverter-Setup
Compression=lzma2
SolidCompression=yes
[Files]
Source: "dist\SyntaxConverter\*"; DestDir: "{app}"; Flags: recursesubdirs
[Icons]
Name: "{group}\Syntax Converter"; Filename: "{app}\SyntaxConverter.exe"
Name: "{autodesktop}\Syntax Converter"; Filename: "{app}\SyntaxConverter.exe"
