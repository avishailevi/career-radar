@echo off
setlocal

cd /d "%~dp0"
set "APP_URL=http://127.0.0.1:8765/"
set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    )
)

if not defined PYTHON_EXE (
    echo Python was not found.
    echo Create the project environment with:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo Or install Python and make sure python is available from PATH.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Career Radar dependencies are missing.
    echo Run: "%PYTHON_EXE%" -m pip install -r requirements.txt
    pause
    exit /b 1
)

start "Career Radar Server" cmd /k "set CAREER_RADAR_NO_BROWSER=1&& ""%PYTHON_EXE%"" local_app.py"

echo Starting Career Radar...
for /l %%i in (1,1,30) do (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%APP_URL%' -TimeoutSec 1; if ($r.StatusCode -lt 500) { exit 0 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        start "" "%APP_URL%"
        echo Career Radar is open at %APP_URL%
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)

echo Career Radar did not start within 30 seconds.
echo Check the Career Radar Server window for details.
pause
exit /b 1
