param(
  [string]$Slug
)

if (-not $Slug) {
  Write-Host "用法: .\install_user_skill.ps1 -Slug livermore"
  exit 1
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repoRoot ".agents\skills\$Slug"
$dst = Join-Path $HOME ".agents\skills\$Slug"

if (!(Test-Path $src)) {
  Write-Host "找不到源 skill: $src"
  exit 1
}

New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
if (Test-Path $dst) {
  Remove-Item -Recurse -Force $dst
}
Copy-Item -Recurse -Force $src $dst
Write-Host "已安装到: $dst"
Write-Host "重启 Codex 后可用。"
