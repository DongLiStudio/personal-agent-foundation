[CmdletBinding()]
param(
    [string]$Python,
    [switch]$Repair
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:OS -ne 'Windows_NT') {
    throw 'This Skill supports Windows only.'
}

$skillRoot = Split-Path -Parent $PSScriptRoot
if ($skillRoot -match '[\\/]GLOBAL[\\/]\.agents[\\/]skills[\\/]') {
    throw 'Do not create runtime files in the GLOBAL source. Run this installer from the user-level installed Skill copy.'
}

$candidates = @()
if ($Python) {
    $candidates += [pscustomobject]@{ Command = $Python; Prefix = @() }
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    $candidates += [pscustomobject]@{ Command = (Get-Command py).Source; Prefix = @('-3') }
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    $candidates += [pscustomobject]@{ Command = (Get-Command python).Source; Prefix = @() }
}
$bundled = Get-ChildItem -Path (Join-Path $env:USERPROFILE '.cache\codex-runtimes') -Filter python.exe -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '[\\/]dependencies[\\/]python[\\/]python\.exe$' } |
    Sort-Object LastWriteTime -Descending
foreach ($item in $bundled) {
    $candidates += [pscustomobject]@{ Command = $item.FullName; Prefix = @() }
}

$pythonCommand = $null
$pythonPrefix = @()
$info = $null
foreach ($candidate in $candidates) {
    try {
        $probe = & $candidate.Command @($candidate.Prefix) -c "import json,platform,struct,sys; print(json.dumps({'version':list(sys.version_info[:3]),'bits':struct.calcsize('P')*8,'machine':platform.machine()}))" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $parsed = $probe | ConvertFrom-Json
            if ($parsed.bits -eq 64 -and $parsed.version[0] -eq 3 -and $parsed.version[1] -eq 12) {
                $pythonCommand = $candidate.Command
                $pythonPrefix = @($candidate.Prefix)
                $info = $parsed
                break
            }
        }
    } catch {
        continue
    }
}
if (-not $pythonCommand) {
    throw 'Python 3.12 x64 was not found. Install it or pass -Python with its executable path.'
}

$runtime = Join-Path $skillRoot '.runtime'
$source = Join-Path $skillRoot 'assets\wechat-cli'
$lock = Join-Path $skillRoot 'requirements.lock'
$wheelhouse = Join-Path $skillRoot 'wheelhouse'
if (-not (Test-Path -LiteralPath (Join-Path $source 'pyproject.toml'))) {
    throw 'Bundled hardened wechat-cli source is missing.'
}
if (-not (Test-Path -LiteralPath $lock)) {
    throw 'Dependency lock file is missing.'
}
if (-not (Test-Path -LiteralPath $wheelhouse)) {
    throw 'Offline dependency wheelhouse is missing.'
}
if ($Repair -and (Test-Path -LiteralPath $runtime)) {
    Remove-Item -LiteralPath $runtime -Recurse -Force
}
if (-not (Test-Path -LiteralPath (Join-Path $runtime 'Scripts\python.exe'))) {
    & $pythonCommand @pythonPrefix -m venv $runtime
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the private Python runtime.' }
}

$runtimePython = Join-Path $runtime 'Scripts\python.exe'
& $runtimePython -m pip install --disable-pip-version-check --no-index --only-binary=:all: --require-hashes --find-links $wheelhouse -r $lock
if ($LASTEXITCODE -ne 0) { throw 'Locked dependency installation failed.' }
& $runtimePython -m pip install --disable-pip-version-check --no-index --no-deps --no-build-isolation -e $source
if ($LASTEXITCODE -ne 0) { throw 'Bundled wechat-cli installation failed.' }
& $runtimePython -m compileall -q (Join-Path $skillRoot 'scripts') (Join-Path $source 'wechat_cli')
if ($LASTEXITCODE -ne 0) { throw 'Python source validation failed.' }

$selfTest = & $runtimePython (Join-Path $skillRoot 'scripts\profile_manager.py') self-test
if ($LASTEXITCODE -ne 0) { throw 'Windows DPAPI self-test failed.' }
$parsedSelfTest = $selfTest | ConvertFrom-Json
if (-not $parsedSelfTest.ok) { throw 'Windows DPAPI self-test returned an unhealthy result.' }

[pscustomobject]@{
    installed = $true
    python_version = ($info.version -join '.')
    python_bits = $info.bits
    dependencies_locked = $true
    source_commands = @('init', 'sessions', 'history', 'search', 'stats')
    profile_protection = $parsedSelfTest.protection
    modifies_wechat = $false
    reads_wechat_during_install = $false
} | ConvertTo-Json
