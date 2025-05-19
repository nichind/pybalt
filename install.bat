@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo pybalt Installation Script
echo ===================================================
echo This script will install Python 3.11.9 if needed
echo and then install or update the pybalt package.
echo ===================================================
echo.

:: Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script requires administrator privileges.
    echo Please right-click on the script and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

:: Check internet connection
ping 8.8.8.8 -n 1 -w 1000 >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: No internet connection detected.
    echo Please check your connection and try again.
    echo.
    pause
    exit /b 1
)

:: Check if Python is installed
echo Checking for Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing Python 3.11.9...
    
    set PYTHON_INSTALLER=python_installer.exe
    
    if %PROCESSOR_ARCHITECTURE% == AMD64 (
        echo Downloading 64-bit Python installer...
        powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile %PYTHON_INSTALLER%"
    ) else (
        echo Downloading 32-bit Python installer...
        powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.11.9/python-3.11.9.exe -OutFile %PYTHON_INSTALLER%"
    )
    
    if not exist %PYTHON_INSTALLER% (
        echo ERROR: Failed to download Python installer.
        pause
        exit /b 1
    )
    
    echo Installing Python...
    start /wait %PYTHON_INSTALLER% /quiet InstallAllUsers=1 PrependPath=1
    
    :: Clean up installer
    del %PYTHON_INSTALLER%
    
    :: Verify Python was installed correctly
    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Python installation failed.
        echo Please try installing Python manually from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo Python installed successfully.
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo Found !PYTHON_VERSION!
)

echo.
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing/upgrading pybalt...
python -m pip install pybalt -U

echo.
echo ===================================================
echo pybalt installation complete!
echo ===================================================
echo.

pause