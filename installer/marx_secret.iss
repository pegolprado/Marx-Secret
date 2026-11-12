; =============================================================================
;  MARX SECRET Professional – Instalador Windows (Inno Setup 6)
;  Compilar:  ISCC.exe installer\marx_secret.iss
;  Pré-requisito: dist\MARX_SECRET\ gerado pelo PyInstaller (scripts\build_windows.ps1)
; =============================================================================

#define AppName "MARX SECRET"
#define AppFullName "MARX SECRET Professional"
#define AppVersion "1.0.0"
#define AppPublisher "MARX SECRET"
#define AppExe "MARX_SECRET.exe"
#define AppSlogan "PRIVACIDADE. SEGURANÇA. INTELIGÊNCIA."

[Setup]
AppId={{7E3B2C1A-5D44-4F6B-9A0E-6C2D8B1F4A90}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppFullName} {#AppVersion}
AppPublisher={#AppPublisher}
AppComments={#AppSlogan}
AppCopyright=© 2026 {#AppPublisher}
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalador do {#AppFullName}
VersionInfoProductName={#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
DisableDirPage=no
DisableProgramGroupPage=no
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\release
OutputBaseFilename=MARX_SECRET_Setup
SetupIconFile=..\marx_secret\assets\marx_secret.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppFullName}
WizardStyle=modern
WizardImageFile=wizard_large.bmp,wizard_large_2x.bmp
WizardSmallImageFile=wizard_small.bmp,wizard_small_2x.bmp
Compression=lzma2/ultra64
SolidCompression=yes
LicenseFile=..\docs\TERMOS_DE_USO.txt
AppMutex=MarxSecretProfessionalMutex
CloseApplications=yes
ShowLanguageDialog=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[CustomMessages]
brazilianportuguese.RemoveUserData=Deseja remover também o histórico, as configurações e o banco de dados local do MARX SECRET?%n%nArquivos que você criou (imagens, relatórios) NÃO serão apagados.
brazilianportuguese.ManualShortcut=Manual do MARX SECRET

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\MARX_SECRET\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\release\Manual_MARX_SECRET.pdf"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "{#AppSlogan}"
Name: "{group}\{cm:ManualShortcut}"; Filename: "{app}\Manual_MARX_SECRET.pdf"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon; Comment: "{#AppSlogan}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Purge: Boolean;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\{#AppName}');
    if not DirExists(DataDir) then
      Exit;
    if UninstallSilent then
      Purge := ExpandConstant('{param:PURGE|0}') = '1'
    else
      Purge := MsgBox(CustomMessage('RemoveUserData'), mbConfirmation, MB_YESNO) = IDYES;
    if Purge then
      DelTree(DataDir, True, True, True);
  end;
end;
