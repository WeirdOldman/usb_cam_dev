@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

call "%SCRIPT_DIR%validate_packaged_runtime.bat" INVALID_CAMERA
exit /b %ERRORLEVEL%
