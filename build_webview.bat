@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "UI_DIR=%ROOT_DIR%ui"
set "FRONTEND_OUT=%ROOT_DIR%ui_dist"
set "PACKAGED_BUILD_NAME=dist_packaged_runtime_%RANDOM%_%RANDOM%"
set "PACKAGED_BUILD_OUT=%UI_DIR%\%PACKAGED_BUILD_NAME%"

cd /d "%ROOT_DIR%"

if not exist "%UI_DIR%\package.json" (
  echo [ERROR] UI package.json not found: %UI_DIR%\package.json
  exit /b 1
)

if not exist "%UI_DIR%\src\main.tsx" (
  echo [ERROR] UI source entry not found: %UI_DIR%\src\main.tsx
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] node not found. Install Node.js first.
  exit /b 1
)

echo [INFO] Building frontend for packaged PyWebView runtime...
cd /d "%UI_DIR%"
if not exist "%UI_DIR%\node_modules" (
  if exist "%UI_DIR%\package-lock.json" (
    echo [INFO] Installing frontend dependencies with npm ci...
    call npm ci
    if errorlevel 1 (
      echo [ERROR] Frontend dependency installation failed.
      exit /b 1
    )
  ) else (
    echo [WARN] node_modules missing and package-lock.json not found. Skipping npm ci.
  )
)
if exist "%PACKAGED_BUILD_OUT%" rmdir /s /q "%PACKAGED_BUILD_OUT%"
mkdir "%PACKAGED_BUILD_OUT%"
call npm run build -- --outDir "%PACKAGED_BUILD_NAME%" --emptyOutDir false
if errorlevel 1 (
  echo [ERROR] Frontend build failed.
  exit /b 1
)

cd /d "%ROOT_DIR%"
if exist "%FRONTEND_OUT%" rmdir /s /q "%FRONTEND_OUT%"
mkdir "%FRONTEND_OUT%"
xcopy /e /i /y "%PACKAGED_BUILD_OUT%\*" "%FRONTEND_OUT%\" >nul
if errorlevel 1 (
  echo [ERROR] Failed to copy frontend dist into %FRONTEND_OUT%
  exit /b 1
)
if exist "%PACKAGED_BUILD_OUT%" rmdir /s /q "%PACKAGED_BUILD_OUT%"

echo [OK] Frontend packaged assets ready at %FRONTEND_OUT%
exit /b 0
