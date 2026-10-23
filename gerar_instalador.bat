@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo       All the Utils (WinToolbox) - Criador de Instalador
echo ========================================================
echo.

:: Garante que diretorios do Python e Inno Setup estejam acessiveis
set "PATH=%APPDATA%\Python\Python312\Scripts;%APPDATA%\Python\Scripts;C:\Python312\Scripts;%LOCALAPPDATA%\Programs\Inno Setup 6;C:\Program Files (x86)\Inno Setup 6;C:\Program Files\Inno Setup 6;%PATH%"

echo [1/3] Verificando dependencias do Python...
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo [2/3] Compilando arquivos da aplicacao (PyInstaller)...
python -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "WinToolbox" ^
    --icon "ui/icon.ico" ^
    --add-data "ui/Icon.png;ui" ^
    --add-data "ui/icon.ico;ui" ^
    --add-data "src/wintoolbox/ui/icon.png;wintoolbox/ui" ^
    --add-data "src/wintoolbox/ui/icon.ico;wintoolbox/ui" ^
    --collect-submodules wintoolbox ^
    --paths src ^
    main.py

if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha ao compilar binarios com PyInstaller.
    pause
    exit /b 1
)

echo.
echo [3/3] Gerando o Instalador Windows (.exe) com Inno Setup...

:: Localiza o compilador ISCC.exe
set "ISCC_PATH="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"

if "%ISCC_PATH%"=="" (
    echo Inno Setup nao encontrado. Instalando automaticamente via winget...
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
    if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC_PATH%"=="" (
    echo [ERRO] Nao foi possivel localizar o ISCC.exe do Inno Setup.
    pause
    exit /b 1
)

"%ISCC_PATH%" installer.iss
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha ao compilar o instalador.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo           INSTALADOR GERADO COM SUCESSO!
echo ========================================================
echo Arquivo gerado: dist\WinToolbox_Setup.exe
echo.
echo Envie este arquivo para qualquer amigo instalar no Windows!
echo Ele criara atalhos no Menu Iniciar, Area de Trabalho e 
echo entrada de Desinstalacao oficial no Painel de Controle.
echo ========================================================
echo.
pause
