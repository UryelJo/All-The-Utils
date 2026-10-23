@echo off
cd /d "%~dp0"
echo Instalando dependencias e PyInstaller...
pip install pyinstaller customtkinter pillow psutil
echo.
echo Gerando o executavel WinToolbox.exe...
pyinstaller --noconfirm --onedir --windowed --uac-admin --name "WinToolbox" --collect-all customtkinter main.py
echo.
echo Processo finalizado! O executavel foi gerado na pasta 'dist/WinToolbox'.
pause
