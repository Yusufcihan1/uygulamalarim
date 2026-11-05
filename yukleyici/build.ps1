# Uygulama Yükle: exe'yi derler, %LOCALAPPDATA%\Programs altına kopyalar ve masaüstüne kısayol koyar.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = ".\.venv\Scripts\python.exe"
$name = "Uygulama Yükle"

if (-not (Test-Path icon.ico)) { & $py make_icon.py }
& $py -m PyInstaller --noconfirm --clean --windowed --name $name --icon icon.ico --add-data "icon.ico;." `
    --collect-data customtkinter --collect-all tkinterdnd2 app.py
if ($LASTEXITCODE) { throw "PyInstaller başarısız" }

$target = Join-Path $env:LOCALAPPDATA "Programs\$name"
Get-Process | Where-Object { $_.Path -like "$target\*" } | Stop-Process -Force
if (Test-Path $target) { Remove-Item $target -Recurse -Force }
Copy-Item "dist\$name" $target -Recurse

$lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "$name.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = Join-Path $target "$name.exe"
$s.WorkingDirectory = $target
$s.IconLocation = Join-Path $target "$name.exe"
$s.Save()
Write-Host "Hazır: $lnk"
