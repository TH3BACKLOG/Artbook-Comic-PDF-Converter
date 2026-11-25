@echo off
chcp 65001 >nul
title Artbook & Comic PDF Converter & Translator

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ==============================================================
    echo  [ERROR] Python is not installed or not in your system PATH.
    echo  Please install Python 3.10+ to run this application.
    echo ==============================================================
    echo.
    pause
    exit /b 1
)

:: Launch the Desktop GUI
start "" python "%~dp0gui.py"
