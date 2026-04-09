param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$SkillsHome = '',
    [string]$ProductHome = '',
    [string]$DesktopPath = '',
    [switch]$InstallOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$scriptPath = Join-Path $PSScriptRoot 'start_investor_council_shell.ps1'
$args = @('-Root', $Root)
if ($InstallOnly) {
    $args += '-InstallOnly'
}
if ($SkillsHome) {
    $args += @('-SkillsHome', $SkillsHome)
}
if ($ProductHome) {
    $args += @('-ProductHome', $ProductHome)
}
if ($DesktopPath) {
    $args += @('-DesktopPath', $DesktopPath)
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath @args
exit $LASTEXITCODE
