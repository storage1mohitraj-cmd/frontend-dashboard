@echo off
REM start.bat - convenient wrapper to run the bot using the project's Python 3.11 venv
REM Place this file in the same folder as app.py and run it (double-click or from CMD / PowerShell)

SETLOCAL
SET REPO_DIR=%~dp0
REM ensure Python runs with UTF-8 output to avoid logging UnicodeEncodeError on Windows
SET PYTHONUTF8=1
REM venv is created at the repo root: ..\.venv311
SET VENV_PY=%REPO_DIR%..\.venv311\Scripts\python.exe
SET VENV_ACT=%REPO_DIR%..\.venv311\Scripts\activate.bat

IF EXIST "%VENV_ACT%" (
    CALL "%VENV_ACT%"
    python "%REPO_DIR%app.py"
    EXIT /B %ERRORLEVEL%
)

IF EXIST "%VENV_PY%" (
    "%VENV_PY%" "%REPO_DIR%app.py"
    EXIT /B %ERRORLEVEL%
)

echo Could not find the venv at %REPO_DIR%..\.venv311\Scripts
echo Please create the venv or run app.py with the full python path.
EXIT /B 1
