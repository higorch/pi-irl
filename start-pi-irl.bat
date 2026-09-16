@echo off
REM Abre o Pi-IRL sem digitar o comando Python.
REM Duplo clique neste arquivo ou execute no terminal.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente .venv nao encontrado.
  echo Execute antes:
  echo   python -m venv .venv
  echo   .venv\Scripts\Activate.ps1
  echo   pip install -r requirements.txt
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m app.main
if errorlevel 1 pause
