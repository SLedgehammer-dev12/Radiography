@echo off
rem Radiography Web - Windows launcher (double-click).
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python 3 bulunamadi. https://www.python.org/downloads/ adresinden kurun.
  pause
  exit /b 1
)

%PY% serve.py %*
if errorlevel 1 pause
endlocal
