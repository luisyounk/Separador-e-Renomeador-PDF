[Setup]
AppName=Separador e Renomeador de Requisições
AppVersion=1.0
DefaultDirName={autopf}\Separador Requisicoes
DefaultGroupName=Separador Requisicoes
OutputDir=.\Instalador
OutputBaseFilename=Setup_Separador
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes

[Files]
Source: "dist\app.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Program Files\Tesseract-OCR\*"; DestDir: "{app}\Tesseract-OCR"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "tessdata\*"; DestDir: "{app}\Tesseract-OCR\tessdata"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Separador de Requisições"; Filename: "{app}\app.exe"
Name: "{autodesktop}\Separador de Requisições"; Filename: "{app}\app.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar um ícone na Área de Trabalho"; GroupDescription: "Ícones adicionais:"
