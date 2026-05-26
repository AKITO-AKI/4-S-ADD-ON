[Setup]
AppId={{F5EF95CE-3183-4963-933C-E0920EA2E9E9}
AppName=4-S-ADD-ON Blender Installer
AppVersion=1.0.0
DefaultDirName={code:GetDefaultAddonsDir}
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=4-S-ADD-ON-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Files]
Source: "..\..\__init__.py"; DestDir: "{app}\solo_studio_director"; Flags: ignoreversion
Source: "..\..\properties.py"; DestDir: "{app}\solo_studio_director"; Flags: ignoreversion
Source: "..\..\operators\*"; DestDir: "{app}\solo_studio_director\operators"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "..\..\panels\*"; DestDir: "{app}\solo_studio_director\panels"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "..\..\utils\*"; DestDir: "{app}\solo_studio_director\utils"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "..\..\four_s_addon\*"; DestDir: "{app}\four_s_addon"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\solo_studio_director"
Type: filesandordirs; Name: "{app}\four_s_addon"

[Code]
var
  BackupRoot: string;

function ParseVersionPart(const Version: string; const Index: Integer): Integer;
var
  Work: string;
  DotPos: Integer;
  I: Integer;
begin
  Work := Version;
  for I := 1 to Index do
  begin
    DotPos := Pos('.', Work);
    if I = Index then
    begin
      if DotPos > 0 then
        Result := StrToIntDef(Copy(Work, 1, DotPos - 1), 0)
      else
        Result := StrToIntDef(Work, 0);
      Exit;
    end;

    if DotPos > 0 then
      Delete(Work, 1, DotPos)
    else
    begin
      Result := 0;
      Exit;
    end;
  end;

  Result := 0;
end;

function CompareBlenderVersions(const Left, Right: string): Integer;
var
  I: Integer;
  LPart: Integer;
  RPart: Integer;
begin
  for I := 1 to 3 do
  begin
    LPart := ParseVersionPart(Left, I);
    RPart := ParseVersionPart(Right, I);
    if LPart > RPart then
    begin
      Result := 1;
      Exit;
    end;
    if LPart < RPart then
    begin
      Result := -1;
      Exit;
    end;
  end;

  Result := 0;
end;

function PickLatestBlenderVersion: string;
var
  SearchPath: string;
  FindRec: TFindRec;
  BestVersion: string;
begin
  Result := '4.0';
  SearchPath := ExpandConstant('{userappdata}\Blender Foundation\Blender\*');
  BestVersion := '';

  if FindFirst(SearchPath, FindRec) then
  begin
    try
      repeat
        if ((FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) and
           (FindRec.Name <> '.') and
           (FindRec.Name <> '..') and
           (Pos('.', FindRec.Name) > 0) then
        begin
          if (BestVersion = '') or (CompareBlenderVersions(FindRec.Name, BestVersion) > 0) then
            BestVersion := FindRec.Name;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;

  if BestVersion <> '' then
    Result := BestVersion;
end;

function GetDefaultAddonsDir(Param: string): string;
begin
  Result := ExpandConstant('{userappdata}\Blender Foundation\Blender\') +
            PickLatestBlenderVersion +
            '\scripts\addons';
end;

function BackupExistingAddon(const TargetDir: string): Boolean;
var
  BackupDir: string;
begin
  Result := True;
  if not DirExists(TargetDir) then
    Exit;

  if BackupRoot = '' then
  begin
    BackupRoot := AddBackslash(ExtractFileDir(TargetDir)) + 'addons_backup_' + GetDateTimeString('yyyymmdd_hhnnss', #0, #0);
    if not ForceDirectories(BackupRoot) then
    begin
      MsgBox('バックアップディレクトリを作成できませんでした: ' + BackupRoot, mbCriticalError, MB_OK);
      Result := False;
      Exit;
    end;
  end;

  BackupDir := AddBackslash(BackupRoot) + ExtractFileName(TargetDir);
  if DirExists(BackupDir) and not DelTree(BackupDir, True, True, True) then
  begin
    MsgBox('既存バックアップを削除できませんでした: ' + BackupDir, mbCriticalError, MB_OK);
    Result := False;
    Exit;
  end;

  if not RenameFile(TargetDir, BackupDir) then
  begin
    MsgBox('既存アドオンの退避に失敗しました: ' + TargetDir, mbCriticalError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AddonsDir: string;
begin
  if CurStep = ssInstall then
  begin
    AddonsDir := ExpandConstant('{app}');
    if not BackupExistingAddon(AddBackslash(AddonsDir) + 'solo_studio_director') then
      Abort;
    if not BackupExistingAddon(AddBackslash(AddonsDir) + 'four_s_addon') then
      Abort;
  end
  else if (CurStep = ssPostInstall) and (BackupRoot <> '') then
  begin
    MsgBox('既存アドオンを次の場所にバックアップしました:' + #13#10 + BackupRoot, mbInformation, MB_OK);
  end;
end;
