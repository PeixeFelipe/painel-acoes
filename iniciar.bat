@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Instalando o que o app precisa (so na primeira vez demora)...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
  echo.
  echo Nao consegui instalar. Confira se o Python esta instalado e se ha internet.
  pause
  exit /b 1
)
python servidor.py
echo.
echo O app foi desligado.
pause
