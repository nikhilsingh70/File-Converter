@echo off
REM ---- Build SyntaxConverter.exe (run on Windows) ----
REM Uses a fresh virtual environment so the exe stays small and doesn't
REM pick up unrelated packages (TensorFlow, pandas, ...) from your system.
setlocal
cd /d "%~dp0"

if not exist .venv (
    py -3 -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-build.txt || goto :err

set ICON=
if exist app.ico set ICON=--icon app.ico --add-data "app.ico;."

pyinstaller --noconfirm --clean --windowed --onedir --name SyntaxConverter %ICON% ^
  --collect-all tkinterdnd2 --collect-all pdf2docx --collect-all fitz --collect-submodules reportlab ^
  main.py || goto :err

echo.
echo Done:  dist\SyntaxConverter\SyntaxConverter.exe
echo For a single file instead of a folder, change --onedir to --onefile.
pause
exit /b 0

:err
echo Build failed.
pause
exit /b 1
