<#
One-step installer & runner for the bot (Windows PowerShell)

Usage examples:
pwsh -NoProfile -ExecutionPolicy Bypass -File .\install_and_run.ps1

# Optional: run without auto-launch to only install dependencies:
pwsh -NoProfile -ExecutionPolicy Bypass -File .\install_and_run.ps1 -NoRun

You can also pass the bot token via environment variable to avoid interactive prompt:
pwsh -NoProfile -ExecutionPolicy Bypass -Command "$env:DISCORD_BOT_TOKEN='your_token'; & '.\\install_and_run.ps1'"
#>

param(
    [switch]$NoRun
)

$ErrorActionPreference = 'Stop'

# ensure script runs from its directory
if ($PSScriptRoot) { Set-Location $PSScriptRoot }

Write-Host "Starting one-step install in $(Get-Location)" -ForegroundColor Cyan

# Ensure python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Please install Python 3.10+ and ensure 'python' is in PATH." -ForegroundColor Yellow
    exit 1
}

$venvPath = Join-Path $PSScriptRoot '.venv'
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath" -ForegroundColor Green
    python -m venv $venvPath
} else {
    Write-Host "Using existing virtual environment at $venvPath" -ForegroundColor Green
}

# Activate the venv for the current session
$activate = Join-Path $venvPath 'Scripts\Activate.ps1'
if (-not (Test-Path $activate)) {
    Write-Host "Activation script not found at $activate" -ForegroundColor Red
    exit 1
}
. $activate

Write-Host "Upgrading pip and installing dependencies" -ForegroundColor Cyan
python -m pip install --upgrade pip setuptools wheel
if (Test-Path 'requirements.txt') {
    python -m pip install -r requirements.txt
} else {
    Write-Host "No requirements.txt found in $(Get-Location). If dependencies are elsewhere, install them manually." -ForegroundColor Yellow
}

# Ensure bot token exists (main.py expects bot_token.txt in this folder)
$tokenFile = Join-Path $PSScriptRoot 'bot_token.txt'
if (-not (Test-Path $tokenFile)) {
    if ($env:DISCORD_BOT_TOKEN) {
        Write-Host "Writing token from DISCORD_BOT_TOKEN environment variable to bot_token.txt" -ForegroundColor Green
        $env:DISCORD_BOT_TOKEN | Out-File -Encoding utf8 $tokenFile
    } else {
        # look for any other bot_token.txt inside repo
        $found = Get-ChildItem -Path $PSScriptRoot -Recurse -Filter bot_token.txt -File -ErrorAction SilentlyContinue | Where-Object { $_.DirectoryName -ne $PSScriptRoot } | Select-Object -First 1
        if ($found) {
            Copy-Item $found.FullName $tokenFile
            Write-Host "Copied existing token from $($found.FullName) to $tokenFile" -ForegroundColor Green
        } else {
            Write-Host "No existing token found. Please paste your bot token when prompted." -ForegroundColor Yellow
            $secure = Read-Host -AsSecureString "Bot token (input hidden)"
            $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            try {
                $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
                $plain | Out-File -Encoding utf8 $tokenFile
            } finally {
                if ($ptr) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
            }
            Write-Host "bot_token.txt created." -ForegroundColor Green
        }
    }
} else {
    Write-Host "Found existing bot_token.txt; using it." -ForegroundColor Green
}

if (-not $NoRun) {
    Write-Host "Launching bot (running main.py) — logs will appear here." -ForegroundColor Cyan
    python main.py
} else {
    Write-Host "Install-only mode complete. To run the bot, re-run this script without -NoRun." -ForegroundColor Cyan
}
