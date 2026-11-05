<#
Uygulamalarım sitesine bir uygulama ekler ya da yeni sürümünü yayınlar.

  .\yayinla.ps1 -Id pc-turbo -Ad "PC Turbo" -Surum 1.0.1 -Dosya "C:\...\PC Turbo Kurulum.exe"

İlk yayında -Aciklama, -Ozellikler ve -Ikon da ver; sonraki sürümlerde verilmeyenler önceki kayıttan alınır.
Dosya GitHub Releases'e yüklenir (dosya başına 2 GB'a kadar), apps.json güncellenir ve site yayınlanır.
#>
param(
    [Parameter(Mandatory)] [string]$Id,
    [Parameter(Mandatory)] [string]$Ad,
    [Parameter(Mandatory)] [string]$Surum,
    [Parameter(Mandatory)] [string]$Dosya,
    [string]$Aciklama,
    [string[]]$Ozellikler,
    [string]$Ikon,
    [string]$Platform = "Windows"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$repo = "Yusufcihan1/uygulamalarim"

$src = Get-Item -LiteralPath $Dosya
$tag = "$Id-v$Surum"
$assetName = (($Ad -replace '[^\w\-]+', '-').Trim('-')) + "-$Surum" + $src.Extension
$tmp = Join-Path ([IO.Path]::GetTempPath()) $assetName
Copy-Item -LiteralPath $src.FullName $tmp -Force

# Önceki kayıt (varsa) açıklama/özellik/ikon için temel olur.
$apps = @()
if (Test-Path apps.json) {
    $parsed = [IO.File]::ReadAllText((Resolve-Path apps.json), [Text.Encoding]::UTF8) | ConvertFrom-Json
    $apps = @($parsed | ForEach-Object { $_ })
}
$old = $apps | Where-Object { $_.id -eq $Id } | Select-Object -First 1
if (-not $Aciklama) { $Aciklama = $old.description }
if (-not $Ozellikler) { $Ozellikler = @($old.features) }
if (-not $Aciklama) { throw "İlk yayında -Aciklama gerekli" }

if ($Ikon) {
    New-Item -ItemType Directory -Force icons | Out-Null
    Copy-Item -LiteralPath $Ikon "icons\$Id.png" -Force
}
if (-not (Test-Path "icons\$Id.png")) { throw "İkon yok: -Ikon ile bir PNG ver" }

Write-Host "Release yükleniyor: $tag / $assetName"
# PowerShell 5.1 "Stop" kipinde gh/git'in stderr'e yazdığı ilerleme satırlarını da hata sayar; buradan sonra
# yerel komutların sonucu çıkış koduyla denetlenir.
$ErrorActionPreference = "Continue"
gh release view $tag --repo $repo *> $null
if ($LASTEXITCODE -eq 0) {
    gh release upload $tag $tmp --repo $repo --clobber
} else {
    gh release create $tag $tmp --repo $repo --title "$Ad $Surum" --notes $Aciklama
}
if ($LASTEXITCODE) { throw "gh release başarısız" }
Remove-Item $tmp

$entry = [ordered]@{
    id          = $Id
    name        = $Ad
    version     = $Surum
    platform    = $Platform
    date        = (Get-Date).ToString("yyyy-MM-dd")
    description = $Aciklama
    features    = @($Ozellikler | Where-Object { $_ })
    icon        = "icons/$Id.png"
    size        = $src.Length
    sha256      = (Get-FileHash -LiteralPath $src.FullName -Algorithm SHA256).Hash.ToLower()
    download    = "https://github.com/$repo/releases/download/$tag/$assetName"
    release     = "https://github.com/$repo/releases?q=$Id"
}
$apps = @($apps | Where-Object { $_.id -ne $Id }) + [pscustomobject]$entry
$json = ConvertTo-Json -InputObject @($apps) -Depth 5
[IO.File]::WriteAllText((Join-Path $PSScriptRoot "apps.json"), $json, (New-Object Text.UTF8Encoding $false))

git add -A
git commit -q -m "$Ad $Surum yayınlandı"
git push -q
if ($LASTEXITCODE) { throw "git push başarısız" }
Write-Host "Yayında: https://yusufcihan1.github.io/uygulamalarim/ (Pages güncellemesi ~1 dk sürer)"
