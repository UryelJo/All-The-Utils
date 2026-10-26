; Script de criacao do instalador nativo do Windows para o All the Utils (WinToolbox)
; Utiliza Inno Setup 6 / 7

#define MyAppName "All the Utils"
#define MyAppExeName "WinToolbox.exe"
; Versao e pasta de origem vem do build.py (/DMyAppVersion=... /DSourceDir=...)
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "dist\WinToolbox"
#endif
#define MyAppPublisher "All the Utils Team"
#define MyAppURL "https://github.com/uryelde/WinToolbox"

[Setup]
AppId={{5A4F98E2-23BC-4D11-8C54-F4A3928E1099}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\AllTheUtils
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=WinToolbox_Setup
SetupIconFile=ui\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
; Windows 10 1809+ (o Qt 6 nao roda em versoes anteriores)
MinVersion=10.0.17763
; Detecta o app aberto (mutex criado em app.py) e pede para fecha-lo antes de instalar/desinstalar
AppMutex=AllTheUtilsWinToolboxRunning
CloseApplications=yes
VersionInfoVersion={#MyAppVersion}
DisableProgramGroupPage=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "contextmenu"; Description: "Adicionar 'Abrir com All the Utils' ao menu de contexto de arquivos e pastas"; GroupDescription: "Integração com o Windows Explorer:"

[Files]
; Copia todos os arquivos da pasta gerada pelo PyInstaller (onedir)
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"

[Registry]
; Menu de contexto para arquivos (*)
Root: HKA; Subkey: "Software\Classes\*\shell\AllTheUtils"; ValueType: string; ValueName: ""; ValueData: "Abrir com All the Utils"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\*\shell\AllTheUtils"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName},0"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\*\shell\AllTheUtils\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: contextmenu

; Menu de contexto para pastas (Directory)
Root: HKA; Subkey: "Software\Classes\Directory\shell\AllTheUtils"; ValueType: string; ValueName: ""; ValueData: "Abrir com All the Utils"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\AllTheUtils"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName},0"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\AllTheUtils\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: contextmenu

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Atalho do menu "Enviar para" criado pelo app (Configuracoes)
Type: files; Name: "{userappdata}\Microsoft\Windows\SendTo\All The Utils.cmd"
