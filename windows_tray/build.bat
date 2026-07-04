@echo off
REM One-command build: raw "Free Claude Code.exe" + full installer (setup.exe).
REM Run this from anywhere; it always resolves paths relative to itself.
REM
REM Requirements on this Windows machine before running:
REM   - Python 3.14+ on PATH (this project requires 3.14 - see pyproject.toml).
REM   - Optional: Inno Setup 6 (https://jrsoftware.org/isinfo.php) for the
REM     full setup.exe installer. Without it, you still get a working
REM     "dist\Free Claude Code\Free Claude Code.exe" - just no installer/
REM     shortcuts/uninstaller wrapped around it.

setlocal enabledelayedexpansion
cd /d "%~dp0\.."
set "REPO_ROOT=%CD%"
set "VENV_DIR=%REPO_ROOT%\windows_tray\build_venv"

echo ============================================================
echo  Free Claude Code - Windows tray app build
echo  Repo root: %REPO_ROOT%
echo ============================================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python not found on PATH. Install Python 3.14+ first: https://www.python.org/downloads/
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo Using Python %PYVER% (this project requires 3.14+; if pip installs below fail with odd errors, that's almost always why).

if not exist "%VENV_DIR%" (
    echo.
    echo [1/6] Creating build venv at %VENV_DIR% ...
    python -m venv "%VENV_DIR%" || goto :error
) else (
    echo.
    echo [1/6] Reusing existing build venv at %VENV_DIR%
)

call "%VENV_DIR%\Scripts\activate.bat" || goto :error

echo.
echo [2/6] Installing project dependencies (this can take a few minutes the first time) ...
python -m pip install --upgrade pip >nul || goto :error
python -m pip install -e "%REPO_ROOT%" || goto :error
python -m pip install pyinstaller pystray pillow || goto :error

echo.
echo [3/6] Generating app icon ...
python "%REPO_ROOT%\windows_tray\generate_icon.py" || goto :error

echo.
echo [4/6] Running PyInstaller ...
pyinstaller "%REPO_ROOT%\windows_tray\build.spec" --noconfirm --distpath "%REPO_ROOT%\dist" --workpath "%REPO_ROOT%\windows_tray\build_work" || goto :error

echo.
echo [5/6] Looking for Inno Setup (ISCC.exe) to build the full installer ...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC (
    echo Found Inno Setup: !ISCC!
    "!ISCC!" "%REPO_ROOT%\windows_tray\installer.iss" || goto :error
    echo.
    echo [6/6] Installer built.
) else (
    echo Inno Setup not found - skipping installer packaging.
    echo Install it from https://jrsoftware.org/isinfo.php and re-run this
    echo script to also get a proper setup.exe with shortcuts + uninstaller.
    echo.
    echo [6/6] Skipped installer step.
)

echo.
echo ============================================================
echo  Done.
echo  Raw app:   %REPO_ROOT%\dist\Free Claude Code\Free Claude Code.exe
if defined ISCC (
echo  Installer: %REPO_ROOT%\windows_tray\installer_output\FreeClaudeCodeSetup.exe
)
echo ============================================================
exit /b 0

:error
echo.
echo [FAILED] Build stopped - see the error above.
exit /b 1
