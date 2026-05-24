@echo off
setlocal EnableExtensions

REM USB_CAM Phase 4 portable packaging entry (Windows / PyInstaller --onedir)
REM Scope locked:
REM - onedir only
REM - no installer
REM - no onefile
REM - no PySide6 migration

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "APP_NAME=USB_Cam_4K25"
set "ENTRY_SCRIPT=usb_burst_cam_4k25_manual_v1_6_3.py"
set "DIST_DIR=dist"
set "BUILD_DIR=build"
set "OUTPUT_DIR=%DIST_DIR%\%APP_NAME%"
set "TOOLS_DIR=%OUTPUT_DIR%\tools"

echo [INFO] Workspace: %SCRIPT_DIR%
echo [INFO] Entry script: %ENTRY_SCRIPT%
echo [INFO] Output dir: %OUTPUT_DIR%

if not exist "%ENTRY_SCRIPT%" (
  echo [ERROR] Entry script not found: %ENTRY_SCRIPT%
  exit /b 1
)

set "PY_CMD="
python --version >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=python"
)

if not defined PY_CMD (
  py -3 --version >nul 2>nul
  if not errorlevel 1 (
    set "PY_CMD=py -3"
  )
)

if not defined PY_CMD (
  echo [ERROR] Python launcher not found. Install Python 3.10+ first.
  exit /b 1
)

echo [INFO] Python command: %PY_CMD%

%PY_CMD% -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] PyInstaller is not available in the selected Python environment.
  echo [HINT] Install it with: %PY_CMD% -m pip install pyinstaller
  exit /b 1
)

echo [INFO] Cleaning previous build artifacts...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

echo [INFO] Running PyInstaller --onedir build...
%PY_CMD% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onedir ^
  --name "%APP_NAME%" ^
  "%ENTRY_SCRIPT%"

if errorlevel 1 (
  echo [ERROR] PyInstaller build failed.
  exit /b 1
)

if not exist "%OUTPUT_DIR%" (
  echo [ERROR] Expected output directory not found: %OUTPUT_DIR%
  exit /b 1
)

if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%"

echo.
echo [OK] Build completed.
echo [NEXT] If you ship portable FFmpeg, place it at:
echo        %TOOLS_DIR%\ffmpeg.exe
echo [NEXT] Then validate with docs\USB_CAM_PACKAGING_VALIDATION_CHECKLIST.md
echo [NEXT] Minimum release target:
echo        %OUTPUT_DIR%
echo.
exit /b 0
