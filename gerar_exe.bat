@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo       All the Utils (WinToolbox) - Gerador de Executavel
echo ========================================================
echo.
echo Escolha o formato desejado:
echo.
echo [1] Instalador Oficial do Windows (Setup.exe) [RECOMENDADO]
echo     - Gera: dist\WinToolbox_Setup.exe
echo     - Assistente visual de instalacao (Avancar, Instalar, Concluir).
echo     - Cria atalhos no Menu Iniciar, Area de Trabalho e Desinstalador nativo.
echo.
echo [2] Executavel Portatil Standalone (.exe unico)
echo     - Gera: dist\WinToolbox_Portable.exe
echo.
echo [3] Pasta Completa + Pacote ZIP
echo     - Gera: dist\WinToolbox\ e dist\WinToolbox.zip
echo.
echo [4] Gerar Tudo (Instalador + Portatil + ZIP)
echo.
set /p OPCAO="Digite a opcao desejada (1, 2, 3 ou 4) [Padrao: 1]: "
if "%OPCAO%"=="" set OPCAO=1

:: Adiciona os diretorios de Scripts do Python e Inno Setup ao PATH da sessao
set "PATH=%APPDATA%\Python\Python312\Scripts;%APPDATA%\Python\Scripts;C:\Python312\Scripts;%LOCALAPPDATA%\Programs\Inno Setup 6;C:\Program Files (x86)\Inno Setup 6;C:\Program Files\Inno Setup 6;%PATH%"

echo.
echo [1/3] Verificando dependencias e PyInstaller...
python -m pip install -r requirements.txt
python -m pip install pyinstaller

if "%OPCAO%"=="1" goto BUILD_INSTALLER
if "%OPCAO%"=="2" goto BUILD_ONEFILE
if "%OPCAO%"=="3" goto BUILD_ONEDIR
if "%OPCAO%"=="4" goto BUILD_ALL

:BUILD_INSTALLER
echo.
echo [2/3] Compilando arquivos com PyInstaller...
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
if %ERRORLEVEL% NEQ 0 goto BUILD_ERROR

echo.
echo [3/3] Criando o Instalador Windows com Inno Setup...
call :FIND_ISCC
if "%ISCC_PATH%"=="" goto BUILD_ERROR

"%ISCC_PATH%" installer.iss
if %ERRORLEVEL% NEQ 0 goto BUILD_ERROR

echo.
echo ========================================================
echo           INSTALADOR GERADO COM SUCESSO!
echo ========================================================
echo Arquivo gerado: dist\WinToolbox_Setup.exe
echo Envie este arquivo para qualquer amigo instalar no Windows!
echo ========================================================
echo.
pause
exit /b 0

:BUILD_ONEFILE
echo.
echo [2/3] Gerando Executavel Portatil (OneFile)...
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "WinToolbox_Portable" ^
    --icon "ui/icon.ico" ^
    --add-data "ui/Icon.png;ui" ^
    --add-data "ui/icon.ico;ui" ^
    --add-data "src/wintoolbox/ui/icon.png;wintoolbox/ui" ^
    --add-data "src/wintoolbox/ui/icon.ico;wintoolbox/ui" ^
    --collect-submodules wintoolbox ^
    --paths src ^
    main.py
if %ERRORLEVEL% NEQ 0 goto BUILD_ERROR

echo.
echo [3/3] Concluido!
echo Executavel Portatil: dist\WinToolbox_Portable.exe
echo.
pause
exit /b 0

:BUILD_ONEDIR
echo.
echo [2/3] Gerando Pasta e ZIP...
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
if %ERRORLEVEL% NEQ 0 goto BUILD_ERROR

echo Compactando dist\WinToolbox em dist\WinToolbox.zip...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\WinToolbox\*' -DestinationPath 'dist\WinToolbox.zip' -Force"

echo.
echo [3/3] Concluido!
echo - Pasta: dist\WinToolbox\
echo - Pacote: dist\WinToolbox.zip
echo.
pause
exit /b 0

:BUILD_ALL
echo.
echo [2/3] Gerando Pasta completa e Instalador...
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
if %ERRORLEVEL% NEQ 0 goto BUILD_ERROR

echo Compactando dist\WinToolbox em dist\WinToolbox.zip...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\WinToolbox\*' -DestinationPath 'dist\WinToolbox.zip' -Force"

call :FIND_ISCC
if not "%ISCC_PATH%"=="" (
    "%ISCC_PATH%" installer.iss
)

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "WinToolbox_Portable" ^
    --icon "ui/icon.ico" ^
    --add-data "ui/Icon.png;ui" ^
    --add-data "ui/icon.ico;ui" ^
    --add-data "src/wintoolbox/ui/icon.png;wintoolbox/ui" ^
    --add-data "src/wintoolbox/ui/icon.ico;wintoolbox/ui" ^
    --collect-submodules wintoolbox ^
    --paths src ^
    main.py
if %ERRORLEVEL% NEQ 0 goto BUILD_ERROR

echo.
echo [3/3] Processo concluido!
echo - Instalador Windows: dist\WinToolbox_Setup.exe
echo - Executavel Portatil: dist\WinToolbox_Portable.exe
echo - Pacote ZIP: dist\WinToolbox.zip
echo.
pause
exit /b 0

:FIND_ISCC
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
exit /b 0

:BUILD_ERROR
echo.
echo [ERRO] Ocorreu uma falha durante o processo.
pause
exit /b 1
