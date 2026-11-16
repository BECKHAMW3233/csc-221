@echo off
REM ==========================================================================
REM  M7Lab - build the Windows .exe with PyInstaller
REM  William Beckham - CSC-221
REM
REM  Double-click this file (or run it from Command Prompt in this folder).
REM  It does the same steps as docs\EXE_CONVERSION.md Part 3:
REM    1. create a virtual environment (venv)
REM    2. activate it
REM    3. install PyInstaller + the program's packages into it
REM    4. run the unit tests
REM    5. build dist\M7Lab_Launcher.exe
REM ==========================================================================
setlocal
cd /d "%~dp0"

echo.
echo === M7Lab: build the Windows .exe ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup, then run this again.
    goto :fail
)
python --version

echo.
echo [1/5] Creating the virtual environment (venv)...
if exist "venv\Scripts\python.exe" (
    echo       venv already exists - reusing it.
) else (
    python -m venv venv
    if errorlevel 1 goto :fail
)

echo.
echo [2/5] Activating the virtual environment...
call "venv\Scripts\activate.bat"
if errorlevel 1 goto :fail
where python

echo.
echo [3/5] Installing PyInstaller and the program's packages...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto :fail
pyinstaller --version

echo.
echo [4/5] Running the unit tests...
python -m unittest discover -s tests -v
if errorlevel 1 (
    echo Unit tests FAILED - not building the .exe.
    goto :fail
)

echo.
echo [5/5] Building dist\M7Lab_Launcher.exe with PyInstaller...
pyinstaller --onefile --console --clean --noconfirm --name M7Lab_Launcher ^
    --add-data "templates;templates" ^
    --add-data "vet_app\data;vet_app\data" ^
    --add-data "recipe_app\data;recipe_app\data" ^
    --add-data "rpg_app\game\data;rpg_app\game\data" ^
    --hidden-import openpyxl ^
    launcher.py
if errorlevel 1 goto :fail
if not exist "dist\M7Lab_Launcher.exe" goto :fail

echo.
echo ==========================================================
echo  BUILD SUCCEEDED:  %CD%\dist\M7Lab_Launcher.exe
echo  Next: double-click it to test, then run
echo        python make_submission_zip.py
echo ==========================================================
echo.
pause
exit /b 0

:fail
echo.
echo ==========================================================
echo  BUILD FAILED - read the messages above for the reason.
echo ==========================================================
echo.
pause
exit /b 1
