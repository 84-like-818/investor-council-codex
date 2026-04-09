param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$SkillsHome = '',
    [string]$ProductHome = '',
    [string]$DesktopPath = '',
    [switch]$SkipPip,
    [switch]$SkipGuiLaunch,
    [switch]$SkipPythonInstall
)

& (Join-Path $PSScriptRoot 'start_investor_council.ps1') `
    -Root $Root `
    -SkillsHome $SkillsHome `
    -ProductHome $ProductHome `
    -DesktopPath $DesktopPath `
    -SkipPip:$SkipPip `
    -SkipGuiLaunch:$SkipGuiLaunch `
    -SkipPythonInstall:$SkipPythonInstall `
    -InstallOnly