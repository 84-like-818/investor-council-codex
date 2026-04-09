param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$SkillsHome = '',
    [string]$ProductHome = '',
    [string]$DesktopPath = '',
    [switch]$InstallOnly,
    [switch]$SkipPip
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Fail([string]$Message) {
    throw $Message
}

function Load-JsonFile([string]$Path) {
    if (-not (Test-Path $Path)) {
        return @{}
    }
    try {
        return Get-Content -Path $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return @{}
    }
}

function Get-RequirementsHash([string]$Path) {
    if (-not (Test-Path $Path)) {
        return ''
    }
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash
}

function Find-HostPython([string]$BootstrapStatusPath) {
    $status = Load-JsonFile -Path $BootstrapStatusPath
    if ($status -and $status.python_executable -and (Test-Path $status.python_executable)) {
        return [string]$status.python_executable
    }

    try {
        $exe = (& py -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim()
        if ($exe) {
            return $exe
        }
    } catch {
    }

    foreach ($candidate in @('python', 'python3')) {
        try {
            $exe = (& $candidate -c "import sys; print(sys.executable)" 2>$null).Trim()
            if ($exe) {
                return $exe
            }
        } catch {
        }
    }

    return ''
}

$bootstrapScript = Join-Path $PSScriptRoot 'start_investor_council.ps1'
$productHome = if ($ProductHome) { $ProductHome } else { Join-Path $env:LOCALAPPDATA 'InvestorCouncilCodex' }
$bootstrapStatusPath = Join-Path $productHome 'status.json'
$shellStatusPath = Join-Path $productHome 'shell_status.json'
$requirementsPath = Join-Path $Root 'requirements.txt'
$venvPath = Join-Path $Root '.venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'

Write-Step '准备投资大师智能团环境'
$bootstrapArgs = @(
    '-Root', $Root,
    '-InstallOnly',
    '-SkipGuiLaunch',
    '-AllowNotLoggedIn'
)
if ($SkillsHome) {
    $bootstrapArgs += @('-SkillsHome', $SkillsHome)
}
if ($ProductHome) {
    $bootstrapArgs += @('-ProductHome', $ProductHome)
}
if ($DesktopPath) {
    $bootstrapArgs += @('-DesktopPath', $DesktopPath)
}
if ($SkipPip) {
    $bootstrapArgs += '-SkipPip'
}
& powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript @bootstrapArgs
if ($LASTEXITCODE -ne 0) {
    Fail '投资大师智能团的 Codex skill 预检查没有完成。'
}

$hostPython = Find-HostPython -BootstrapStatusPath $bootstrapStatusPath
if (-not $hostPython) {
    Fail '没有找到可用的 Python 3.11+ 运行时。'
}

if (-not (Test-Path $venvPython)) {
    Write-Step '创建本地壳应用运行环境'
    & $hostPython -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Fail '创建独立壳应用虚拟环境失败。'
    }
}

$shellStatus = Load-JsonFile -Path $shellStatusPath
$currentHash = Get-RequirementsHash -Path $requirementsPath
$installedHash = ''
if ($shellStatus) {
    $property = $shellStatus.PSObject.Properties['requirements_hash']
    if ($property) {
        $installedHash = [string]$property.Value
    }
}

if (-not $SkipPip -and $currentHash -ne $installedHash) {
    Write-Step '安装或更新壳应用依赖'
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Fail '升级壳应用 pip 失败。'
    }
    & $venvPython -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        Fail '安装壳应用依赖失败，请检查网络或 Python 环境。'
    }

    $payload = @{
        requirements_hash = $currentHash
        venv_python = $venvPython
        updated_at = (Get-Date).ToString('s')
    } | ConvertTo-Json -Depth 4
    [System.IO.Directory]::CreateDirectory($productHome) | Out-Null
    [System.IO.File]::WriteAllText($shellStatusPath, $payload, [System.Text.UTF8Encoding]::new($false))
}

if ($InstallOnly) {
    Write-Host ''
    Write-Host '投资大师智能团已准备完成。现在可以双击桌面图标打开独立窗口。' -ForegroundColor Green
    exit 0
}

Write-Step '启动投资大师智能团独立窗口'
& $venvPython -m investor_council_shell.launcher
if ($LASTEXITCODE -ne 0) {
    Fail '投资大师智能团窗口启动失败。'
}
