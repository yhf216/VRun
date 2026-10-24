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
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
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
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl,ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
english.BeveledLabel=VRun · iPhone virtual running

[CustomMessages]
english.InstallAppleDrivers=Download and configure Apple USB components (Internet and administrator access required)
chinesesimp.InstallAppleDrivers=下载并配置 Apple USB 驱动与通信组件（需要联网和管理员权限）
english.DesktopShortcut=Create a desktop shortcut
chinesesimp.DesktopShortcut=创建桌面快捷方式
english.LaunchVRun=Launch VRun
chinesesimp.LaunchVRun=启动 VRun
english.PreparingApple=Preparing Apple USB components. This may take a few minutes...
chinesesimp.PreparingApple=正在准备 Apple USB 驱动与通信组件，可能需要几分钟，请稍候…
english.AppleStartFailed=Apple components could not be started. Re-run setup to retry.
chinesesimp.AppleStartFailed=无法启动 Apple 驱动准备程序，请重新运行安装包后重试。
english.AppleIncomplete=Apple USB setup was not completed. VRun is installed; re-run setup to retry driver installation.
chinesesimp.AppleIncomplete=Apple 驱动准备未完成。VRun 已安装，可以稍后重新运行安装包准备驱动。

[Tasks]
Name: "appledrivers"; Description: "{cm:InstallAppleDrivers}"; Check: IsAdminInstallMode
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; Flags: unchecked

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
Filename: "{app}\VRun.exe"; Description: "{cm:LaunchVRun}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
var
  DriverRestart: Boolean;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('appledrivers') then
  begin
    WizardForm.StatusLabel.Caption := CustomMessage('PreparingApple');
    if not Exec(ExpandConstant('{app}\VRun.exe'), '--install-drivers', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      MsgBox(CustomMessage('AppleStartFailed'), mbError, MB_OK)
    else if ResultCode = 3010 then
      DriverRestart := True
    else if ResultCode <> 0 then
      MsgBox(CustomMessage('AppleIncomplete'), mbInformation, MB_OK);
  end;
end;

function NeedRestart(): Boolean;
begin
  Result := DriverRestart;
end;
