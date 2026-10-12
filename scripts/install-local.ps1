<#
.SYNOPSIS
    Install (or refresh) the local skillgendev clone as a global command, like `npm link`.

.DESCRIPTION
    Run it from anywhere, as often as you like. It:
      1. checks that uv is installed,
      2. uninstalls any previous global install and clears uv's cache for the package,
      3. removes old build output from the clone,
      4. installs this clone globally in editable mode, so the global command always
         runs your current code (edit, save, run; no reinstall needed for code changes),
      5. makes sure uv's tool folder is on PATH,
      6. verifies that the global command points at this clone,
      7. optionally downloads Chromium for the probe and runs the test suite.

    Rerun it after changing dependencies or pyproject.toml, or whenever the global
    command seems out of date.

.PARAMETER NoExtras
    Install without the optional probe extra (Playwright, for --xy).

.PARAMETER SkipChromium
    Do not download Chromium for the probe.

.PARAMETER RunTests
    Also run ruff, mypy and pytest in the clone after installing.

.PARAMETER Uninstall
    Remove the global command and the package's uv cache, then stop.

.EXAMPLE
    .\scripts\install-local.ps1
.EXAMPLE
    .\scripts\install-local.ps1 -RunTests
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\install-local.ps1
#>
[CmdletBinding()]
param(
    [switch]$NoExtras,
    [switch]$SkipChromium,
    [switch]$RunTests,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Write-Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "    $Message" -ForegroundColor Green }
function Write-Note([string]$Message) { Write-Host "    $Message" -ForegroundColor Yellow }

function Invoke-Checked([string]$What, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)." }
}

function Invoke-Quiet([scriptblock]$Command) {
    # Windows PowerShell 5.1 turns native stderr into a terminating error under 'Stop',
    # even when redirected, so relax it here for commands whose failure is expected.
    $ErrorActionPreference = 'Continue'
    & $Command 2>&1 | Out-Null
    return $LASTEXITCODE
}

function Get-PackageName {
    # The package name lives in pyproject.toml, so a rename needs no change here.
    $pyproject = Get-Content (Join-Path $RepoRoot 'pyproject.toml') -Raw
    $match = [regex]::Match($pyproject, '(?m)^name\s*=\s*"([^"]+)"')
    if (-not $match.Success) { throw 'Could not read the package name from pyproject.toml.' }
    return $match.Groups[1].Value
}

function Assert-Uv {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host 'uv is not installed. Install it, open a new terminal, and run this script again:' -ForegroundColor Red
        Write-Host '    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
        exit 1
    }
    Write-Ok "uv $((uv --version) -replace '^uv\s+', '')"
}

function Remove-OldInstall([string]$Name) {
    Write-Step "Removing any previous global $Name"
    $exitCode = Invoke-Quiet { uv tool uninstall $Name }
    if ($exitCode -eq 0) { Write-Ok 'previous install removed' } else { Write-Ok 'no previous install' }
    $global:LASTEXITCODE = 0
    Write-Step "Clearing uv's cache for $Name"
    Invoke-Checked 'uv cache clean' { uv cache clean $Name }
}

function Remove-BuildOutput {
    Write-Step 'Removing old build output from the clone'
    foreach ($relative in @('build', 'dist')) {
        $path = Join-Path $RepoRoot $relative
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Recurse -Force
            Write-Ok "removed $relative/"
        }
    }
    Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'src') -Directory -Filter '*.egg-info' -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force; Write-Ok "removed $($_.Name)" }
}

function Install-Editable([string]$Name) {
    $spec = if ($NoExtras) { '.' } else { '.[probe]' }
    Write-Step "Installing $Name globally from $RepoRoot ($spec, editable)"
    Push-Location $RepoRoot
    try {
        Invoke-Checked 'uv tool install' { uv tool install --editable $spec --force --reinstall }
    } finally {
        Pop-Location
    }
    Write-Step "Making sure uv's tool folder is on PATH"
    Invoke-Quiet { uv tool update-shell } | Out-Null
    $global:LASTEXITCODE = 0
    $binDir = (uv tool dir --bin).Trim()
    if (($env:PATH -split [IO.Path]::PathSeparator) -notcontains $binDir) {
        $env:PATH = "$binDir$([IO.Path]::PathSeparator)$env:PATH"
        Write-Note "added $binDir to PATH for this window; new terminals get it automatically"
    }
    return $binDir
}

function Test-Install([string]$Name) {
    Write-Step "Checking the global $Name"
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) { throw "$Name is not on PATH. Open a new terminal and run: $Name --version" }
    Write-Ok "command: $($command.Source)"
    Invoke-Checked "$Name --version" { & $Name --version }
    $doctor = & $Name doctor --json | ConvertFrom-Json
    $self = $doctor.checks | Where-Object { $_.name -eq $Name }
    $expected = (Resolve-Path (Join-Path $RepoRoot "src/$Name")).Path
    if ($self -and $self.detail -like "*$expected*") {
        Write-Ok "runs your local code: $expected"
    } else {
        Write-Note "the global command does not point at this clone ($($self.detail))"
    }
    foreach ($check in $doctor.checks) {
        $mark = if ($check.ok) { 'ok ' } elseif ($check.required) { 'ERR' } else { '-- ' }
        Write-Host ("    [{0}] {1,-10} {2}" -f $mark, $check.name, $check.detail)
    }
}

function Install-Chromium([string]$Name) {
    if ($NoExtras -or $SkipChromium) { return }
    Write-Step 'Downloading Chromium for the probe (first run only takes a while)'
    & $Name doctor --fix | Select-Object -Last 1 | ForEach-Object { Write-Ok $_ }
    $global:LASTEXITCODE = 0
}

function Invoke-Tests {
    Write-Step 'Running the checks in the clone'
    Push-Location $RepoRoot
    try {
        Invoke-Checked 'uv sync' { uv sync --all-extras }
        Invoke-Checked 'ruff check' { uv run ruff check . }
        Invoke-Checked 'ruff format' { uv run ruff format --check . }
        Invoke-Checked 'mypy' { uv run mypy }
        Invoke-Checked 'pytest' { uv run pytest }
    } finally {
        Pop-Location
    }
}

$name = Get-PackageName
Write-Host "Local install of $name from $RepoRoot" -ForegroundColor White
Assert-Uv
Remove-OldInstall $name
if ($Uninstall) {
    Write-Host "`n$name is uninstalled." -ForegroundColor Green
    exit 0
}
Remove-BuildOutput
Install-Editable $name | Out-Null
# skillgendev writes UTF-8 when piped; read it that way, then restore the window's setting.
$consoleEncoding = [Console]::OutputEncoding
[Console]::OutputEncoding = [Text.Encoding]::UTF8
try {
    Test-Install $name
    Install-Chromium $name
} finally {
    [Console]::OutputEncoding = $consoleEncoding
}
if ($RunTests) { Invoke-Tests }

Write-Host ''
Write-Host "Done. '$name' now runs the code in $RepoRoot from any folder." -ForegroundColor Green
Write-Host '  Code changes apply at once (editable install).'
Write-Host '  After changing dependencies or pyproject.toml, run this script again.'
Write-Host "  Try it:  cd C:\path\to\your-app; $name init; $name routes --all"
Write-Host "  Logs:    every run writes .$name\logs\*.log in your project; see them with '$name logs'"
