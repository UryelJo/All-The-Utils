@echo off
cd /d "%~dp0"
echo Instalando dependencias e PyInstaller...
pip install -r requirements.txt
echo.
echo Gerando o executavel WinToolbox.exe...
pyinstaller --noconfirm --onedir --windowed --name "WinToolbox" --paths src main.py
echo.
echo Processo finalizado! O executavel foi gerado na pasta 'dist/WinToolbox'.
pause
