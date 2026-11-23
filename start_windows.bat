@echo off
setlocal
title Soyudlu ESD
cd /d "%~dp0"

echo ============================================
echo   Soyudlu ESD - qurasdirma ve ishe salma
echo ============================================
echo.

set "PY="
python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY (
    py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    echo [XETA] Python tapilmadi. python.org-dan quraşdırın ve "Add python.exe to PATH" qutusunu işarələyin.
    goto :fail
)
echo [OK] Python: %PY%

if not exist "venv\Scripts\python.exe" (
    echo [..] Virtual muhit yaradilir...
    %PY% -m venv venv || goto :fail
)

echo [..] Asililiqlar yoxlanilir...
"venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :fail
echo [OK] Asililiqlar hazirdir.

if not exist ".env" (
    copy /y ".env.example" ".env" >nul || goto :fail
)

echo [..] Verilenler bazasi hazirlanir...
"venv\Scripts\python.exe" run.py init-db || goto :fail
echo [OK] Baza hazirdir.

echo.
echo ============================================
echo   Brauzerde acin: http://127.0.0.1:8000/login
echo   Ilk giris: admin / Soyudlu@2026!Admin
echo ============================================
echo.

"venv\Scripts\python.exe" run.py
echo.
echo Server dayandi.
pause
exit /b 0

:fail
echo.
echo [XETA] Addim ugursuz oldu. Yuxaridaki mesaja baxin.
pause
exit /b 1