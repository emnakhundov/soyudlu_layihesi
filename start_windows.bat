@echo off
setlocal
title Soyudlu Layihesi
cd /d "%~dp0"

set "BASE_URL=https://raw.githubusercontent.com/emnakhundov/soyudlu_layihesi/main"

echo ============================================
echo   Soyudlu Layihesi - check, download, start
echo ============================================
echo.

rem ===== 0. Check GitHub connection =====
echo [..] Checking GitHub connection...
set "TESTURL=%BASE_URL%/config.py"
curl.exe -fsSL -o "%TEMP%\esd_test.tmp" "%TESTURL%" >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%TESTURL%' -OutFile '%TEMP%\esd_test.tmp' -UseBasicParsing -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
)
if errorlevel 1 (
  echo [ERROR] Cannot download from GitHub:
  echo         %TESTURL%
  echo Check internet connection. Open the link in a browser:
  echo - If it shows Python code, the link works.
  echo - If it shows 404, the files are not pushed to the repo yet.
  pause
  exit /b 1
)
echo [OK] GitHub reachable.
echo.

rem ===== 1. Check required files, download missing ones =====
set "MISSING=0"
for %%F in (
  "config.py" "run.py" "wsgi.py" "requirements.txt" ".env.example"
  "app\__init__.py" "app\extensions.py" "app\models.py" "app\security.py" "app\seed.py"
  "app\routes\__init__.py" "app\routes\auth.py" "app\routes\main.py"
  "app\routes\vehicles.py" "app\routes\repairs.py" "app\routes\admin.py"
  "app\templates\base.html" "app\templates\login.html"
  "app\templates\change_password.html" "app\templates\setup_2fa.html"
  "app\templates\verify_2fa.html" "app\templates\recovery_codes.html"
  "app\templates\dashboard\index.html"
  "app\templates\vehicles\index.html" "app\templates\vehicles\detail.html"
  "app\templates\repairs\index.html" "app\templates\repairs\detail.html"
  "app\templates\admin\users.html" "app\templates\admin\roles.html"
  "app\templates\admin\audit.html"
  "app\static\img\starmining_logo_blue.png"
) do call :ensure %%F

if "%MISSING%"=="1" (
  echo.
  echo [ERROR] Some files could not be downloaded. See messages above.
  pause
  exit /b 1
)
echo [OK] All project files are present.
echo.

rem ===== 2. Find Python =====
set "PY="
python -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
  py -3 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  echo [ERROR] Python not found. Install Python 3.10+ from python.org
  echo         and tick "Add python.exe to PATH" during setup.
  pause
  exit /b 1
)
echo [OK] Python: %PY%

rem ===== 3. Virtual environment =====
if not exist "venv\Scripts\python.exe" (
  echo [..] Creating virtual environment...
  %PY% -m venv venv
  if errorlevel 1 goto :fail
)
set "VPY=venv\Scripts\python.exe"

rem ===== 4. Dependencies =====
echo [..] Installing dependencies...
"%VPY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :fail
echo [OK] Dependencies ready.

rem ===== 5. Config and database =====
if not exist ".env" copy /y ".env.example" ".env" >nul
echo [..] Preparing database...
"%VPY%" run.py init-db
if errorlevel 1 goto :fail
echo [OK] Database ready.

echo.
echo ============================================
echo   Open in browser: http://127.0.0.1:8000/login
echo   First login: admin / Soyudlu@2026!Admin
echo   To stop the server press CTRL+C
echo ============================================
echo.
"%VPY%" run.py
echo.
echo Server stopped.
pause
exit /b 0

:fail
echo.
echo [ERROR] A step failed. Read the message above.
pause
exit /b 1

rem ===== Subroutine: download file if it does not exist =====
:ensure
set "REL=%~1"
if exist "%REL%" goto :eof
set "DIR=%~dp1"
if not exist "%DIR%" mkdir "%DIR%"
set "URLPATH=%REL:\=/%"
set "FULLURL=%BASE_URL%/%URLPATH%"
echo [DOWNLOAD] %REL%
curl.exe -fsSL -o "%REL%" "%FULLURL%"
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%FULLURL%' -OutFile '%REL%' -UseBasicParsing -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
)
if errorlevel 1 (
  echo [ERROR] Download failed: %REL%
  if exist "%REL%" del "%REL%"
  set "MISSING=1"
)
goto :eof