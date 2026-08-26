@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo Audio DNA Studio Pro - Windows 11 Release Builder
echo ============================================================
echo.

where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python launcher not found. Install Python 3.11 or 3.12 x64.
  exit /b 1
)

if not exist ".buildvenv\Scripts\python.exe" (
  py -3.11 -m venv .buildvenv
  if errorlevel 1 py -3.12 -m venv .buildvenv
)
if not exist ".buildvenv\Scripts\python.exe" (
  echo ERROR: Could not create Python 3.11/3.12 build environment.
  exit /b 1
)

call ".buildvenv\Scripts\activate.bat"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Running source syntax checks...
python -m py_compile app.py engine.py
if errorlevel 1 exit /b 1

echo.
echo Building Windows EXE...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
python -m PyInstaller --noconfirm --clean AudioDNAStudioPro.spec
if errorlevel 1 exit /b 1

if not exist "dist\AudioDNAStudioPro\AudioDNAStudioPro.exe" (
  echo ERROR: EXE was not produced.
  exit /b 1
)

echo.
echo Running EXE self-check...
"dist\AudioDNAStudioPro\AudioDNAStudioPro.exe" --self-check
if errorlevel 1 (
  echo WARNING: self-check returned a non-zero exit code.
)

echo.
echo EXE created:
echo   dist\AudioDNAStudioPro\AudioDNAStudioPro.exe
echo.

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
  echo Building Windows installer...
  if not exist release mkdir release
  "%ISCC%" "installer\AudioDNAStudioPro.iss"
  if errorlevel 1 exit /b 1
  echo Installer created in release\
) else (
  echo Inno Setup 6 not found. EXE build is complete.
  echo Install Inno Setup 6 and rerun this script to also build Setup.exe.
)

echo.
echo BUILD COMPLETE.
pause
