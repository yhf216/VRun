; SPDX-License-Identifier: MPL-2.0
#define AppVersion "0.1.0"
[Setup]
AppId={{BF65DE62-0A7C-48A4-B1E4-09B86F0B9457}
AppName=VRun
AppVersion={#AppVersion}
AppPublisher=VRun contributors
AppPublisherURL=https://github.com/yhf216/VRun
DefaultDirName={autopf}\VRun
DefaultGroupName=VRun
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir=..\release
OutputBaseFilename=VRun-{#AppVersion}-Setup-x64
SetupIconFile=..\assets\vrun.ico
UninstallDisplayIcon={app}\VRun.exe
LicenseFile=..\LICENSE
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
MinVersion=10.0
VersionInfoVersion=0.1.0.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
english.BeveledLabel=VRun · iPhone virtual running

[Tasks]
Name: "appledrivers"; Description: "Download and configure Apple USB components (Internet and administrator access required)"; Check: IsAdminInstallMode
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\VRun\*"; DestDir: "{app}"; Excludes: "routes\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\routes\*.txt"; DestDir: "{app}\routes"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\VRun"; Filename: "{app}\VRun.exe"; AppUserModelID: "VRun.Desktop"
Name: "{autodesktop}\VRun"; Filename: "{app}\VRun.exe"; AppUserModelID: "VRun.Desktop"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\AppUserModelId\VRun.Desktop"; ValueType: string; ValueName: "DisplayName"; ValueData: "VRun"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\AppUserModelId\VRun.Desktop"; ValueType: string; ValueName: "IconUri"; ValueData: "{app}\_internal\assets\vrun.ico"

[Run]
Filename: "{app}\VRun.exe"; Description: "Launch VRun"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
var
  DriverRestart: Boolean;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('appledrivers') then
  begin
    WizardForm.StatusLabel.Caption := 'Preparing Apple USB components. This may take a few minutes...';
    if not Exec(ExpandConstant('{app}\VRun.exe'), '--install-drivers', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      MsgBox('Apple components could not be started. Re-run setup to retry.', mbError, MB_OK)
    else if ResultCode = 3010 then
      DriverRestart := True
    else if ResultCode <> 0 then
      MsgBox('Apple USB setup was not completed. VRun is installed; re-run setup to retry driver installation.', mbInformation, MB_OK);
  end;
end;

function NeedRestart(): Boolean;
begin
  Result := DriverRestart;
end;
