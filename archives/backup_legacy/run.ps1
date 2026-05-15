<#
Run-DiscordBot - PowerShell helper to run the bot using the repository's Python 3.11 venv.
Usage (PowerShell):
  .\run.ps1
This script will dot-source the venv Activate.ps1 if present, otherwise it will call the venv python directly.
#>

Param()

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvActivate = Join-Path $scriptDir "..\.venv311\Scripts\Activate.ps1"
$venvPython = Join-Path $scriptDir "..\.venv311\Scripts\python.exe"

# ensure Python uses UTF-8 for stdout/stderr so logging doesn't raise UnicodeEncodeError on Windows
$env:PYTHONUTF8 = '1'

if (Test-Path $venvActivate) {
    Write-Host "Sourcing venv activate: $venvActivate"
    try {
        . $venvActivate
    } catch {
        Write-Warning "Failed to source Activate.ps1 ($_). Trying to call python directly."
    }
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "Using 'python' from: $(Get-Command python).Path"
    python "$scriptDir\app.py"
    exit $LASTEXITCODE
} elseif (Test-Path $venvPython) {
    Write-Host "Calling venv python: $venvPython"
    & $venvPython "$scriptDir\app.py"
    exit $LASTEXITCODE
} else {
    Write-Error "Could not find python to run the bot. Ensure .venv311 exists at repo root or activate your venv manually."
    exit 1
}
