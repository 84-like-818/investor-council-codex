param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms

try {
    & (Join-Path $PSScriptRoot 'start_investor_council.ps1') -Root $Root
} catch {
    $message = @(
        '投资大师智能团启动失败。'
        ''
        $_.Exception.Message
        ''
        '请先确认 Codex 已登录；如果问题还在，重新运行 START_INVESTOR_COUNCIL.cmd。'
    ) -join [Environment]::NewLine

    [System.Windows.Forms.MessageBox]::Show(
        $message,
        '投资大师智能团',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}
