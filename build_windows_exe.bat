@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

REM ===== Check if Python is installed =====
echo Checking for Python installation...

set PYTHON_CMD=python
set USE_PY_LAUNCHER=0

where py >nul 2>nul
if %errorlevel%==0 (
    set USE_PY_LAUNCHER=1
    echo Python launcher found.
    goto python_ready
)

where python >nul 2>nul
if %errorlevel%==0 (
    echo Python found on PATH.
    goto python_ready
)

echo Python not found. Installing Python 3.14.7 automatically...

REM Download Python installer
set PYTHON_URL=https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe
set PYTHON_INSTALLER=python-3.14.7-amd64.exe

echo Downloading Python 3.14.7 installer...
powershell -Command "Try { (New-Object System.Net.WebClient).DownloadFile('%PYTHON_URL%', '%PYTHON_INSTALLER%') } Catch { Write-Host 'Download failed: ' + $_.Exception.Message; Exit 1 }"

if not exist "%PYTHON_INSTALLER%" (
    echo ERROR: Failed to download Python installer.
    echo Please install Python 3.14.7 manually from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing Python 3.14.7 silently (this may take a minute)...
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 InstallLauncher=1 Include_test=0 Include_venv=1

if !errorlevel! neq 0 (
    echo ERROR: Python installation failed.
    pause
    exit /b 1
)

echo Python installed successfully.

REM Clean up installer
del "%PYTHON_INSTALLER%"

REM Verify python is now available
where python >nul 2>nul
if !errorlevel! neq 0 (
    echo ERROR: Python still not found after installation.
    echo Please ensure Python 3.14.7 was installed correctly.
    pause
    exit /b 1
)

:python_ready

REM ===== Create virtual environment =====
echo.
echo Setting up build environment...

if not exist ".venv" (
    echo Creating virtual environment...
    if !USE_PY_LAUNCHER!==1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if !errorlevel! neq 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo Upgrading pip...
python -m pip install --upgrade pip
if !errorlevel! neq 0 (
    echo WARNING: Failed to upgrade pip. Continuing with existing version.
)

echo Installing build dependencies...
python -m pip install -r requirements-build.txt
if !errorlevel! neq 0 (
    echo ERROR: Failed to install build dependencies.
    pause
    exit /b 1
)

REM ===== Build executable =====
echo.
echo Building Windows executable...

pyinstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --icon=icon.png ^
    --name UserProductivityTool ^
    user_productivity_tool.py

if !errorlevel! neq 0 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo Build finished successfully.
echo The executable is: dist\UserProductivityTool.exe
echo.
echo The executable is portable and does not require Python or any
echo dependencies to be installed on the target machine.
pause