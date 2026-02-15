@echo off
echo Installing WOS Discord Bot as Windows Service...

REM Get the full path to Python
where python > python_path.txt
set /p PYTHON_PATH=<python_path.txt
del python_path.txt

REM Get the full path to app.py
set APP_PATH=%~dp0app.py

echo Python Path: %PYTHON_PATH%
echo App Path: %APP_PATH%

REM Download NSSM if not present
if not exist "nssm.exe" (
    echo Downloading NSSM...
    powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/ci/nssm-2.24-101-g897c7ad.zip' -OutFile 'nssm.zip'"
    powershell -Command "Expand-Archive -Path 'nssm.zip' -DestinationPath '.'"
    copy "nssm-2.24-101-g897c7ad\win64\nssm.exe" "nssm.exe"
    rmdir /s /q "nssm-2.24-101-g897c7ad"
    del "nssm.zip"
)

REM Install the service
echo Installing service...
nssm.exe install WOSBot "%PYTHON_PATH%" "%APP_PATH%"
nssm.exe set WOSBot AppDirectory "%~dp0"
nssm.exe set WOSBot DisplayName "WOS Discord Bot"
nssm.exe set WOSBot Description "Whiteout Survival Discord Bot - Auto Start"
nssm.exe set WOSBot Start SERVICE_AUTO_START

echo.
echo Service installed! Starting bot...
nssm.exe start WOSBot

echo.
echo ✅ Done! Bot is now running as a Windows service.
echo It will auto-start when your PC boots.
echo.
echo Commands:
echo   - Stop bot:    nssm.exe stop WOSBot
echo   - Start bot:   nssm.exe start WOSBot
echo   - Remove bot:  nssm.exe remove WOSBot confirm
echo.
pause
