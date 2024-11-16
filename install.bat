@echo off

python --version >nul 2>&1
if %errorlevel% neq 0 (
    if %PROCESSOR_ARCHITECTURE% == AMD64 (
        powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile python_installer.exe"
    ) else (
        powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.11.9/python-3.11.9.exe -OutFile python_installer.exe"
    )
    start /wait python_installer.exe /quiet InstallAllUsers=1 PrependPath=1
)

python -m pip install --upgrade pip

python -m pip install pybalt -U


pause

