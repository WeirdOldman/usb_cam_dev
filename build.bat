@echo off
setlocal EnableExtensions

REM USB_CAM PySide6 portable packaging entry (Windows / PyInstaller --onedir)
REM Scope locked:
REM - onedir only
REM - package desktop/main.py as the desktop entry
REM - no web frontend build step

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "APP_NAME=USB_Cam_4K25"
set "ENTRY_SCRIPT=desktop\main.py"
set "DIST_DIR=dist"
set "BUILD_DIR=build"
set "OUTPUT_DIR=%DIST_DIR%\%APP_NAME%"
set "TOOLS_DIR=%OUTPUT_DIR%\tools"
set "SOURCE_FFMPEG=%SCRIPT_DIR%tools\ffmpeg.exe"

echo [INFO] Workspace: %SCRIPT_DIR%
echo [INFO] Entry script: %ENTRY_SCRIPT%
echo [INFO] Output dir: %OUTPUT_DIR%

if not exist "%ENTRY_SCRIPT%" (
  echo [ERROR] Entry script not found: %ENTRY_SCRIPT%
  exit /b 1
)

set "PY_CMD="
if not defined PY_CMD (
  if defined pythonLocation (
    if exist "%pythonLocation%\python.exe" (
      set "PY_CMD=%pythonLocation%\python.exe"
    )
  )
)

if not defined PY_CMD (
  if defined Python3_ROOT_DIR (
    if exist "%Python3_ROOT_DIR%\python.exe" (
      set "PY_CMD=%Python3_ROOT_DIR%\python.exe"
    )
  )
)

if not defined PY_CMD (
  if defined Python_ROOT_DIR (
    if exist "%Python_ROOT_DIR%\python.exe" (
      set "PY_CMD=%Python_ROOT_DIR%\python.exe"
    )
  )
)

if not defined PY_CMD (
  if exist "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" (
    set "PY_CMD=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
  )
)

if not defined PY_CMD (
  python --version >nul 2>nul
  if not errorlevel 1 (
    set "PY_CMD=python"
  )
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

tasklist /FI "IMAGENAME eq USB_Cam_4K25.exe" | find /I "USB_Cam_4K25.exe" >nul
if not errorlevel 1 (
  echo [ERROR] Running packaged process detected: USB_Cam_4K25.exe
  echo [HINT] Close any running USB_Cam_4K25.exe before building.
  exit /b 1
)

echo [INFO] Cleaning previous build artifacts...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%DIST_DIR%" (
  echo [ERROR] Failed to clean dist directory.
  echo [HINT] If dist cleanup fails, close any running USB_Cam_4K25.exe first.
  exit /b 1
)

echo [INFO] Running PyInstaller --onedir build...
%PY_CMD% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onedir ^
  --specpath "%BUILD_DIR%" ^
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

if exist "%SOURCE_FFMPEG%" (
  copy /y "%SOURCE_FFMPEG%" "%TOOLS_DIR%\ffmpeg.exe" >nul
  if errorlevel 1 (
    echo [ERROR] Failed to copy ffmpeg.exe into packaged tools directory.
    exit /b 1
  )
) else (
  echo [WARN] Portable ffmpeg.exe not found at:
  echo        %SOURCE_FFMPEG%
)

echo.
echo [OK] Build completed.
echo [NEXT] Validate packaged runtime with docs\requirements\PACKAGED_RUNTIME_QUICKSTART.md
echo [NEXT] Default packaged smoke report:
echo        outputs\packaged_runtime\packaged_runtime_smoke_report.json
echo [NEXT] Minimum release target:
echo        %OUTPUT_DIR%
echo.
exit /b 0
