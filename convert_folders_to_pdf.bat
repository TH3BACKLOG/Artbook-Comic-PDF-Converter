@echo off
chcp 65001 >nul
title Folder to PDF Converter

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python is not found in your PATH.
    echo Please install Python 3 or add it to your system PATH.
    echo.
    pause
    exit /b 1
)

:: Run the script: passing any dragged-and-dropped folders (%*)
python "%~dp0folder_to_pdf.py" %*

echo.
pause
