@echo off
:: One-click launcher for Windows
:: Usage: double-click this file or run from cmd/powershell

cd /d %~dp0

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo Virtual environment not found. Run install_and_run.ps1 first to create .venv
)

python main.py
