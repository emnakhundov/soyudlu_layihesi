@echo off
setlocal EnableExtensions
title Soyudlu Layihesi
cd /d "%~dp0"

set "BASE_URL=https://raw.githubusercontent.com/emnakhundov/soyudlu_layihesi/main"
set "MISSING=0"
set "PY="

echo ============================================
echo   Soyudlu Layihesi - automatic setup and start
echo ============================================
echo.

rem ===== 1. Project files: download the ones that are missing =====
echo [1/5] Checking project files...
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

if "%MISSING%"=="1" goto :fail_files
echo [OK] Project files ready.
echo.

rem ===== 2. Python 3.10+: find it, or install it automatically =====
echo [2/5] Checking Python...
call :find_python
if not defined PY (
  echo [..] Python not found. Installing Python 3.12 for the current user...
  call :install_python
  call :find_python
)
if not defined PY goto :fail_python
echo [OK] Python: %PY%
echo.

rem ===== 3. Virtual environment =====
echo [3/5] Preparing virtual environment...
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" -c "import sys" >nul 2>&1
  if errorlevel 1 (
    echo [..] Existing virtual environment is broken. Recreating it...
    rmdir /s /q venv
  )
)
if not exist "venv\Scripts\python.exe" (
  "%PY%" -m venv venv
  if errorlevel 1 goto :fail_step
)
set "VPY=%CD%\venv\Scripts\python.exe"
echo [OK] Virtual environment ready.echo [4/5] Installing dependencies...
"%VPY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :fail_step
"%VPY%" -c "import waitress" >nul 2>&1
if errorlevel 1 "%VPY%" -m pip install --disable-pip-version-check -q waitress==3.0.0
if errorlevel 1 goto :fail_step
echo [OK] Dependencies ready.
echo.

rem ===== 5. Config, database, start =====
echo [5/5] Preparing configuration and database...
if not exist ".env" copy /y ".env.example" ".env" >nul
"%VPY%" run.py init-db
if errorlevel 1 goto :fail_step
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

:fail_files
echo.
echo [ERROR] Some project files could not be downloaded from GitHub.
echo Check the internet connection and that the repo is public and has all files.
pause
exit /b 1

:fail_python
echo.
echo [ERROR] Python could not be installed automatically.
echo Install Python 3.12 manually from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH", then run this file again.
pause
exit /b 1

:fail_step
echo.
echo [ERROR] A setup step failed. Read the messages above.
pause
exit /b 1

rem ===================== SUBROUTINES =====================

:find_python
set "PY="
call :try_py "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :try_py "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
call :try_py "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
call :try_py python
call :try_py py
goto :eof

:try_py
if defined PY goto :eof
"%~1" -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
goto :eof

:install_python
where winget >nul 2>&1
if not errorlevel 1 (
  winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements
)
call :find_python
if defined PY goto :eof

echo [..] Downloading Python installer from python.org...
set "PYINST=%TEMP%\python-3.12.7-amd64.exe"
curl.exe -fL --retry 3 -o "%PYINST%" "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
if errorlevel 1 goto :eof

echo [..] Running Python installer (this can take a minute)...
"%PYINST%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=0 Include_test=0
goto :eof

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