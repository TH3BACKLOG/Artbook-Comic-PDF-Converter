@echo off
chcp 65001 >nul
title Artbook and Comic PDF Converter and Translator

cd /d "%~dp0"
if not exist "%~dp0logs" mkdir "%~dp0logs"

set "LOG_FILE=%~dp0logs\error.log"
set "STARTUP_LOG=%~dp0logs\startup.log"

echo ====================================================================== >> "%STARTUP_LOG%"
echo [%DATE% %TIME%] start.bat initiated. >> "%STARTUP_LOG%"

:: 1. Search for working Python
set "PY_CMD="

:: Check C:\Python314\python.exe directly
if exist "C:\Python314\python.exe" (
    "C:\Python314\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=C:\Python314\python.exe"
        goto :FOUND_PYTHON
    )
)

:: Check py launcher
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
    goto :FOUND_PYTHON
)

py -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py"
    goto :FOUND_PYTHON
)

:: Check python on PATH
python -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
    goto :FOUND_PYTHON
)

:: Check other Python versions in C:\
if exist "C:\Python313\python.exe" set "PY_CMD=C:\Python313\python.exe" & goto :FOUND_PYTHON
if exist "C:\Python312\python.exe" set "PY_CMD=C:\Python312\python.exe" & goto :FOUND_PYTHON
if exist "C:\Python311\python.exe" set "PY_CMD=C:\Python311\python.exe" & goto :FOUND_PYTHON
if exist "C:\Python310\python.exe" set "PY_CMD=C:\Python310\python.exe" & goto :FOUND_PYTHON

:: No Python found
echo [%DATE% %TIME%] ERROR: No working Python executable found on this computer. >> "%LOG_FILE%"
echo [%DATE% %TIME%] ERROR: No working Python executable found on this computer. >> "%STARTUP_LOG%"
echo.
echo ======================================================================
echo  [ERROR] Python is not installed or not working on your system PATH.
echo  Please install Python 3.10+ from https://python.org
echo.
echo  An error log has been written to:
echo  %LOG_FILE%
echo ======================================================================
echo.
pause
exit /b 1

:FOUND_PYTHON
echo [%DATE% %TIME%] Using Python interpreter: %PY_CMD% >> "%STARTUP_LOG%"

:: Check dependencies
%PY_CMD% -c "import PIL, pypdfium2" >nul 2>&1
if not errorlevel 1 goto :LAUNCH_GUI

echo [*] Installing missing packages (Pillow, pypdfium2)...
echo [%DATE% %TIME%] Installing Pillow and pypdfium2... >> "%STARTUP_LOG%"
%PY_CMD% -m pip install pillow pypdfium2 >> "%STARTUP_LOG%" 2>&1

:: Verify dependencies
%PY_CMD% -c "import PIL, pypdfium2" >nul 2>&1
if not errorlevel 1 goto :LAUNCH_GUI

echo [%DATE% %TIME%] ERROR: Dependencies Pillow or pypdfium2 failed to load. >> "%LOG_FILE%"
echo.
echo ======================================================================
echo  [ERROR] Required packages (Pillow, pypdfium2) failed to load.
echo  Check the error log for details:
echo  %LOG_FILE%
echo ======================================================================
echo.
pause
exit /b 1

:LAUNCH_GUI
echo [%DATE% %TIME%] Launching GUI application... >> "%STARTUP_LOG%"
%PY_CMD% "%~dp0gui.py" 2>> "%LOG_FILE%"
set "ERR_CODE=%ERRORLEVEL%"

if "%ERR_CODE%"=="0" (
    echo [%DATE% %TIME%] Application closed cleanly. >> "%STARTUP_LOG%"
    exit /b 0
)

echo [%DATE% %TIME%] Application exited with error code %ERR_CODE%. >> "%LOG_FILE%"
echo.
echo ======================================================================
echo  [!] The application encountered an error and closed (Exit Code: %ERR_CODE%).
echo  Details have been logged to:
echo  %LOG_FILE%
echo ======================================================================
echo.
pause
exit /b %ERR_CODE%
