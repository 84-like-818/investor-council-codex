param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$SkillsHome = '',
    [string]$ProductHome = '',
    [string]$DesktopPath = '',
    [switch]$SkipPip,
    [switch]$SkipGuiLaunch,
    [switch]$SkipPythonInstall,
    [switch]$InstallOnly,
    [switch]$AllowNotLoggedIn
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Info([string]$Message) {
    Write-Host $Message -ForegroundColor Gray
}

function Fail([string]$Message) {
    throw $Message
}

function Get-Registry {
    $path = Join-Path $Root 'config\mentor_registry.json'
    if (-not (Test-Path $path)) {
        Fail "找不到导师注册表：$path"
    }
    return Get-Content -Path $path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Ensure-WindowsEnvironment {
    $isWindowsHost = $true
    try {
        $isWindowsHost = [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT
    } catch {
        $isWindowsHost = $env:OS -eq 'Windows_NT'
    }
    if (-not $isWindowsHost) {
        Fail '当前版本仅支持 Windows。'
    }
}

function Get-CodexCommand {
    $cmd = Get-Command codex.cmd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd = Get-Command codex -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Test-CodexLoggedIn([string]$CodexCommand) {
    if ($CodexCommand) {
        try {
            $output = cmd /c ""$CodexCommand" login status" 2>&1 | Out-String
            if ($output -match 'Logged in' -or $output -match 'chatgpt' -or $output -match 'ChatGPT') {
                return $true
            }
        } catch {
        }
    }

    $authPath = Join-Path $env:USERPROFILE '.codex\auth.json'
    if (-not (Test-Path $authPath)) {
        return $false
    }

    try {
        $auth = Get-Content -Path $authPath -Raw -Encoding UTF8 | ConvertFrom-Json
        return [bool]($auth.tokens.refresh_token -or $auth.tokens.access_token -or $auth.auth_mode)
    } catch {
        return $false
    }
}

function Find-Python311 {
    $result = [ordered]@{
        Found = $false
        Executable = $null
        Version = $null
    }

    try {
        $exe = (& py -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim()
        $ver = (& py -3.11 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null).Trim()
        if ($exe -and $ver) {
            $result.Found = $true
            $result.Executable = $exe
            $result.Version = $ver
            return [pscustomobject]$result
        }
    } catch {
    }

    foreach ($candidate in @('python', 'python3')) {
        try {
            $exe = (& $candidate -c "import sys; print(sys.executable)" 2>$null).Trim()
            $ver = (& $candidate -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null).Trim()
            if ($exe -and $ver) {
                $versionObj = [version]$ver
                if ($versionObj -ge [version]'3.11.0') {
                    $result.Found = $true
                    $result.Executable = $exe
                    $result.Version = $ver
                    return [pscustomobject]$result
                }
            }
        } catch {
        }
    }

    return [pscustomobject]$result
}

function Install-Python311([string]$ProductHome) {
    if ($SkipPythonInstall) {
        Fail '未检测到 Python 3.11+，且当前设置为跳过自动安装。'
    }

    Write-Step '未检测到 Python 3.11+，开始自动安装'

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info '优先使用 winget 安装 Python 3.11（当前用户范围）。'
        & winget install --id Python.Python.3.11 -e --scope user --accept-package-agreements --accept-source-agreements
        return
    }

    Write-Info '当前机器未发现 winget，改用 python.org 官方安装包。'
    $downloadsDir = Join-Path $ProductHome 'downloads'
    New-Item -ItemType Directory -Force -Path $downloadsDir | Out-Null

    try {
        $page = Invoke-WebRequest -Uri 'https://www.python.org/downloads/windows/' -UseBasicParsing
    } catch {
        Fail "无法打开 Python 官方下载页：$($_.Exception.Message)"
    }

    $html = $page.Content
    $fullMatch = [regex]::Match($html, 'https://www\.python\.org/ftp/python/(?<ver>3\.11\.\d+)/python-(?<ver2>3\.11\.\d+)-amd64\.exe')
    if ($fullMatch.Success) {
        $downloadUrl = $fullMatch.Value
        $version = $fullMatch.Groups['ver'].Value
    } else {
        $nameMatch = [regex]::Match($html, 'python-(?<ver>3\.11\.\d+)-amd64\.exe')
        if (-not $nameMatch.Success) {
            Fail '未能从 Python 官方页面解析出 Python 3.11 x64 安装包链接。'
        }
        $version = $nameMatch.Groups['ver'].Value
        $downloadUrl = "https://www.python.org/ftp/python/$version/python-$version-amd64.exe"
    }

    $installerPath = Join-Path $downloadsDir "python-$version-amd64.exe"
    if (-not (Test-Path $installerPath)) {
        Write-Info "下载 Python 安装包：$downloadUrl"
        try {
            Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing
        } catch {
            Fail "下载 Python 安装包失败：$($_.Exception.Message)"
        }
    }

    Write-Info '执行 Python 静默安装。'
    $args = @('/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1')
    $proc = Start-Process -FilePath $installerPath -ArgumentList $args -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Fail "Python 安装器退出码异常：$($proc.ExitCode)"
    }
}

function Sync-RegistryMirror([string]$PythonExe) {
    $syncScript = Join-Path $Root 'scripts\sync_investor_council_registry.py'
    if (-not (Test-Path $syncScript)) {
        Fail "找不到导师注册表同步脚本：$syncScript"
    }
    & $PythonExe $syncScript
    if ($LASTEXITCODE -ne 0) {
        Fail '同步导师注册表失败，无法继续安装投资大师智能团 skill。'
    }
}

function Get-LaunchInfoFromCache([string]$StatusPath) {
    if (-not (Test-Path $StatusPath)) {
        return $null
    }
    try {
        $status = Get-Content -Path $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($status.codex_gui -and $status.codex_gui.launch_type -and $status.codex_gui.target) {
            if ($status.codex_gui.launch_type -eq 'exe' -and (Test-Path $status.codex_gui.target)) {
                return $status.codex_gui
            }
            if ($status.codex_gui.launch_type -ne 'exe') {
                return $status.codex_gui
            }
        }
    } catch {
    }
    return $null
}

function Resolve-CodexGuiLaunchInfo([string]$StatusPath) {
    $cached = Get-LaunchInfoFromCache -StatusPath $StatusPath
    if ($cached) {
        return $cached
    }

    try {
        $startApps = Get-StartApps | Where-Object { $_.Name -like '*Codex*' -or $_.AppID -like '*Codex*' }
        if ($startApps) {
            $app = $startApps | Select-Object -First 1
            return [pscustomobject]@{
                launch_type = 'appid'
                target = $app.AppID
                source = 'Get-StartApps'
            }
        }
    } catch {
    }

    try {
        $pkg = Get-AppxPackage | Where-Object { $_.PackageFamilyName -like 'OpenAI.Codex*' -or $_.Name -like '*Codex*' } | Select-Object -First 1
        if ($pkg -and $pkg.InstallLocation) {
            $guiExe = Join-Path $pkg.InstallLocation 'app\Codex.exe'
            if (Test-Path $guiExe) {
                return [pscustomobject]@{
                    launch_type = 'exe'
                    target = $guiExe
                    source = 'Get-AppxPackage'
                }
            }
        }
    } catch {
    }

    $localPackages = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Packages') -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'OpenAI.Codex_*' }
    foreach ($pkgDir in $localPackages) {
        $family = $pkgDir.Name
        $logsRoot = Join-Path $pkgDir.FullName 'LocalCache\Local\Codex\Logs'
        if (Test-Path $logsRoot) {
            $logFiles = Get-ChildItem -Path $logsRoot -Recurse -Filter '*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
            foreach ($logFile in $logFiles | Select-Object -First 30) {
                try {
                    $text = Get-Content -Path $logFile.FullName -Raw -Encoding UTF8
                } catch {
                    continue
                }
                $match = [regex]::Match($text, '([A-Z]:\\Program Files\\WindowsApps\\OpenAI\.Codex_[^\r\n]+\\app\\resources\\codex\.exe)')
                if ($match.Success) {
                    $candidate = $match.Groups[1].Value -replace '\\app\\resources\\codex\.exe$', '\\app\\Codex.exe'
                    if (Test-Path $candidate) {
                        return [pscustomobject]@{
                            launch_type = 'exe'
                            target = $candidate
                            source = 'CodexLogs'
                        }
                    }
                }
            }
        }

        foreach ($appId in @('App', 'Codex')) {
            $shellTarget = "shell:AppsFolder\$family!$appId"
            return [pscustomobject]@{
                launch_type = 'shell'
                target = $shellTarget
                source = 'PackageFamilyFallback'
            }
        }
    }

    Fail 'Codex 桌面 App 未检测到或无法启动。'
}

function Get-RequirementsHash([string]$Path) {
    if (-not (Test-Path $Path)) {
        return ''
    }
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash
}

function ConvertTo-HashtableValue($Value) {
    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [System.Collections.IDictionary]) {
        $table = @{}
        foreach ($key in $Value.Keys) {
            $table[$key] = ConvertTo-HashtableValue $Value[$key]
        }
        return $table
    }

    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        $table = @{}
        foreach ($property in $Value.PSObject.Properties) {
            $table[$property.Name] = ConvertTo-HashtableValue $property.Value
        }
        return $table
    }

    if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
        $items = New-Object System.Collections.ArrayList
        foreach ($item in $Value) {
            [void]$items.Add((ConvertTo-HashtableValue $item))
        }
        return ,$items.ToArray()
    }

    return $Value
}

function Load-Status([string]$StatusPath) {
    if (-not (Test-Path $StatusPath)) {
        return @{}
    }
    try {
        $status = Get-Content -Path $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
        return (ConvertTo-HashtableValue $status)
    } catch {
        return @{}
    }
}

function Save-Status([string]$StatusPath, [hashtable]$Payload) {
    $dir = Split-Path -Parent $StatusPath
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $json = $Payload | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($StatusPath, $json, [System.Text.UTF8Encoding]::new($false))
}

function Copy-SkillIncremental([string]$SourceDir, [string]$DestDir) {
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    & robocopy $SourceDir $DestDir /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS | Out-Null
    $exitCode = $LASTEXITCODE
    if ($exitCode -ge 8) {
        Fail "复制 skill 失败，robocopy 退出码：$exitCode"
    }
}

function Ensure-DesktopShortcut([string]$ShortcutPath, [string]$TargetPath, [string]$WorkingDir, [string]$Arguments, [string]$IconLocation) {
    $shortcutDir = Split-Path -Parent $ShortcutPath
    New-Item -ItemType Directory -Force -Path $shortcutDir | Out-Null

    $leafName = [System.IO.Path]::GetFileName($ShortcutPath)
    $invalidChars = [System.IO.Path]::GetInvalidFileNameChars()
    $needsFallback = [string]::IsNullOrWhiteSpace($leafName)
    foreach ($char in $invalidChars) {
        if ($leafName.Contains([string]$char)) {
            $needsFallback = $true
            break
        }
    }
    if ($leafName -match '^\?+$') {
        $needsFallback = $true
    }

    $finalShortcutPath = if ($needsFallback) {
        Join-Path $shortcutDir 'Investor Council.lnk'
    } else {
        $ShortcutPath
    }

    $shell = New-Object -ComObject WScript.Shell
    try {
        $shortcut = $shell.CreateShortcut($finalShortcutPath)
        $shortcut.TargetPath = $TargetPath
        $shortcut.Arguments = $Arguments
        $shortcut.WorkingDirectory = $WorkingDir
        if ($IconLocation) {
            $shortcut.IconLocation = $IconLocation
        }
        $shortcut.Save()
        return $finalShortcutPath
    } catch {
        $fallbackPath = Join-Path $shortcutDir 'Investor Council.lnk'
        $shortcut = $shell.CreateShortcut($fallbackPath)
        $shortcut.TargetPath = $TargetPath
        $shortcut.Arguments = $Arguments
        $shortcut.WorkingDirectory = $WorkingDir
        if ($IconLocation) {
            $shortcut.IconLocation = $IconLocation
        }
        $shortcut.Save()
        return $fallbackPath
    }
}

function Ensure-VenvAndDependencies([string]$PythonExe, [string]$SkillDest, [string]$RequirementsHash, [hashtable]$Status) {
    $requirementsPath = Join-Path $SkillDest 'requirements.txt'
    $venvPath = Join-Path $SkillDest '.venv'
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
    $needsPip = -not $SkipPip
    $installedRequirementsHash = ''
    $installedSkillPath = ''

    if ($Status -and $Status.ContainsKey('requirements_hash')) {
        $installedRequirementsHash = [string]$Status['requirements_hash']
    }
    if ($Status -and $Status.ContainsKey('installed_skill_path')) {
        $installedSkillPath = [string]$Status['installed_skill_path']
    }

    if (-not (Test-Path $venvPython)) {
        Write-Info '创建本地虚拟环境。'
        & $PythonExe -m venv $venvPath | Out-Null
    }

    if (-not $needsPip) {
        return $venvPython
    }

    if ((Test-Path $venvPython) -and $installedRequirementsHash -eq $RequirementsHash -and $installedSkillPath -eq $SkillDest) {
        Write-Info '依赖未变化，跳过 pip 安装。'
        return $venvPython
    }

    if (-not (Test-Path $requirementsPath)) {
        return $venvPython
    }

    Write-Info '安装或更新 skill 依赖。'
    try {
        & $venvPython -m pip install --upgrade pip | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Fail "安装 Python 依赖失败：无法升级 pip。"
        }

        & $venvPython -m pip install -r $requirementsPath | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Fail "安装 Python 依赖失败：requirements.txt 安装未完成。"
        }
    } catch {
        Fail "安装 Python 依赖失败：$($_.Exception.Message)"
    }
    return $venvPython
}

function Try-ActivateCodexWindow {
    try {
        $shell = New-Object -ComObject WScript.Shell
        return [bool]($shell.AppActivate('Codex'))
    } catch {
        return $false
    }
}

function Launch-CodexGui($LaunchInfo) {
    Write-Step '启动 Codex 桌面 App'
    if (Try-ActivateCodexWindow) {
        return
    }

    switch ($LaunchInfo.launch_type) {
        'exe' {
            Start-Process -FilePath $LaunchInfo.target | Out-Null
        }
        'appid' {
            Start-Process -FilePath 'explorer.exe' -ArgumentList "shell:AppsFolder\$($LaunchInfo.target)" | Out-Null
        }
        'shell' {
            Start-Process -FilePath 'explorer.exe' -ArgumentList $LaunchInfo.target | Out-Null
        }
        default {
            Fail 'Codex 桌面 App 未检测到或无法启动。'
        }
    }

    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        Start-Sleep -Milliseconds 400
        if (Try-ActivateCodexWindow) {
            return
        }
    }
}

Ensure-WindowsEnvironment
$registry = Get-Registry
$entrySkillName = [string]$registry.entry_skill_name
$bundleDisplayName = [string]$registry.bundle_display_name
if ([string]::IsNullOrWhiteSpace($bundleDisplayName) -or $bundleDisplayName -match '^\?+$') {
    $bundleDisplayName = 'Investor Council'
}
$bootstrapPrompt = [string]$registry.bootstrap_prompt
if (-not $bootstrapPrompt) {
    $bootstrapPrompt = 'Use $investor-council。请先用中文让我选择一个投资人物，再进入对应助手。'
}

if (-not $SkillsHome) {
    $SkillsHome = Join-Path $env:USERPROFILE '.codex\skills'
}
if (-not $ProductHome) {
    $ProductHome = Join-Path $env:LOCALAPPDATA 'InvestorCouncilCodex'
}
if (-not $DesktopPath) {
    $DesktopPath = Join-Path $env:USERPROFILE 'Desktop'
}

$skillSource = Join-Path $Root "codex-skills\$entrySkillName"
$skillDest = Join-Path $SkillsHome $entrySkillName
$statusPath = Join-Path $ProductHome 'status.json'
$shortcutPath = Join-Path $DesktopPath "$bundleDisplayName.lnk"
$startCmdPath = Join-Path $Root 'START_INVESTOR_COUNCIL.cmd'
$launcherVbsPath = Join-Path $Root 'scripts\launch_investor_council_shell.vbs'
$requirementsHash = Get-RequirementsHash -Path (Join-Path $skillSource 'requirements.txt')

Write-Step '检查 Codex 环境'
$codexCommand = Get-CodexCommand
$codexLoggedIn = Test-CodexLoggedIn -CodexCommand $codexCommand
if (-not $codexLoggedIn) {
    if (-not $AllowNotLoggedIn) {
        Fail '检测到 Codex 尚未登录，请先打开 Codex 完成登录后再重试。'
    }
    Write-Info 'Codex 尚未登录，继续完成本地壳应用与 skill 准备；开始对话前仍需要先登录。'
}

Write-Step '检查 Python 3.11+'
$pythonInfo = Find-Python311
if (-not $pythonInfo.Found) {
    Install-Python311 -ProductHome $ProductHome
    $pythonInfo = Find-Python311
}
if (-not $pythonInfo.Found) {
    Fail 'Python 3.11+ 自动安装后仍未检测成功，请检查系统安装状态。'
}
Write-Info "已检测到 Python：$($pythonInfo.Executable) ($($pythonInfo.Version))"

Write-Step '同步导师注册表'
Sync-RegistryMirror -PythonExe $pythonInfo.Executable

Write-Step '安装或更新投资大师智能团 skill'
if (-not (Test-Path $skillSource)) {
    Fail "找不到总入口 skill：$skillSource"
}
New-Item -ItemType Directory -Force -Path $SkillsHome | Out-Null
New-Item -ItemType Directory -Force -Path $ProductHome | Out-Null
Copy-SkillIncremental -SourceDir $skillSource -DestDir $skillDest
$status = Load-Status -StatusPath $statusPath
$venvPython = Ensure-VenvAndDependencies -PythonExe $pythonInfo.Executable -SkillDest $skillDest -RequirementsHash $requirementsHash -Status $status

Write-Step '创建桌面入口'
$launchInfo = $null
try {
    $launchInfo = Resolve-CodexGuiLaunchInfo -StatusPath $statusPath
} catch {
    if (-not $AllowNotLoggedIn) {
        throw
    }
    Write-Info '当前没有检测到 Codex GUI 入口，稍后仍可先打开独立壳应用。'
}
$wscriptExe = Join-Path $env:SystemRoot 'System32\wscript.exe'
if (-not (Test-Path $wscriptExe)) {
    $wscriptExe = 'wscript.exe'
}
$launcherArgs = '"' + $launcherVbsPath + '"'
$desktopIconPath = Join-Path $skillDest 'assets\investor-council-desktop.ico'
$iconLocation = $desktopIconPath
if (-not (Test-Path $iconLocation) -and $launchInfo) {
    $iconLocation = $launchInfo.target
}
if (((-not $launchInfo) -or ($launchInfo.launch_type -ne 'exe') -or -not (Test-Path $iconLocation)) -and -not (Test-Path $desktopIconPath)) {
    $iconLocation = "$env:SystemRoot\System32\shell32.dll,220"
}
$shortcutPath = Ensure-DesktopShortcut -ShortcutPath $shortcutPath -TargetPath $wscriptExe -WorkingDir $Root -Arguments $launcherArgs -IconLocation $iconLocation

$status = @{
    bundle_name = $registry.bundle_name
    bundle_display_name = $bundleDisplayName
    installed_skill_path = $skillDest
    desktop_shortcut = $shortcutPath
    desktop_target = $wscriptExe
    desktop_arguments = $launcherArgs
    prompt = $bootstrapPrompt
    python_executable = $pythonInfo.Executable
    python_version = $pythonInfo.Version
    requirements_hash = $requirementsHash
    venv_python = $venvPython
    codex_command = $codexCommand
    codex_gui = @{
        launch_type = $(if ($launchInfo) { $launchInfo.launch_type } else { '' })
        target = $(if ($launchInfo) { $launchInfo.target } else { '' })
        source = $(if ($launchInfo) { $launchInfo.source } else { '' })
    }
    updated_at = (Get-Date).ToString('s')
}
Save-Status -StatusPath $statusPath -Payload $status

Write-Step '复制总入口提示词'
Set-Clipboard -Value $bootstrapPrompt
Write-Info '总入口提示词已复制到剪贴板。'

if ($InstallOnly) {
    Write-Host ''
    if ($codexLoggedIn) {
        Write-Host '安装完成。现在可以双击桌面上的“投资大师智能团”图标。' -ForegroundColor Green
    } else {
        Write-Host '本地壳应用和 skill 已准备完成。请先登录 Codex，再通过桌面上的“投资大师智能团”开始对话。' -ForegroundColor Green
    }
    exit 0
}

if (-not $SkipGuiLaunch -and $codexLoggedIn -and $launchInfo) {
    Launch-CodexGui -LaunchInfo $launchInfo
    Write-Host ''
    Write-Host 'Codex GUI 已启动。进入后直接粘贴剪贴板内容即可进入总入口。' -ForegroundColor Green
} else {
    Write-Host ''
    if (-not $codexLoggedIn) {
        Write-Host '已完成配置，但 Codex 尚未登录，因此这次跳过 GUI 启动。' -ForegroundColor Green
    } elseif (-not $launchInfo) {
        Write-Host '已完成配置，但当前没有检测到 Codex GUI 入口，因此这次跳过 GUI 启动。' -ForegroundColor Green
    } else {
        Write-Host '已完成配置，并跳过 GUI 启动。' -ForegroundColor Green
    }
}

