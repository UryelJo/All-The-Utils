@echo off
setlocal
cd /d "%~dp0"

:: Ambiente de build isolado: nao mistura com o Python global nem com ferramentas de teste
set "VENV=.venv-build"
if not exist "%VENV%\Scripts\python.exe" (
    echo Criando ambiente de build em %VENV%...
    py -3 -m venv "%VENV%" 2>nul || python -m venv "%VENV%"
    if errorlevel 1 goto ERRO
)
set "PY=%VENV%\Scripts\python.exe"
echo Atualizando dependencias do build...
"%PY%" -m pip install --disable-pip-version-check -q --upgrade pip
"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt -r requirements-dev.txt
if errorlevel 1 goto ERRO

echo ========================================================
echo       All the Utils (WinToolbox) - Gerador de Executavel
echo ========================================================
echo.
echo [1] Instalador do Windows (Setup.exe) [RECOMENDADO]
echo [2] Executavel portatil (.exe unico - inicia mais devagar)
echo [3] Pasta completa (sem instalador)
echo [4] Gerar tudo (instalador + portatil + zip)
echo.
set /p OPCAO="Opcao [1]: "
if "%OPCAO%"=="" set OPCAO=1
set "MODO=installer"
if "%OPCAO%"=="2" set "MODO=onefile"
if "%OPCAO%"=="3" set "MODO=onedir"
if "%OPCAO%"=="4" set "MODO=all"

set "FFMPEG="
set /p INCLUIR_FFMPEG="Incluir ffmpeg para as ferramentas de midia (+~150 MB)? [s/N]: "
if /i "%INCLUIR_FFMPEG%"=="s" (
    "%PY%" -m pip install --disable-pip-version-check -q static-ffmpeg
    set "FFMPEG=--with-ffmpeg"
)

"%PY%" build.py --mode %MODO% %FFMPEG%

if errorlevel 1 goto ERRO
echo.
echo Concluido. Arquivos gerados na pasta dist\
pause
exit /b 0

:ERRO
echo.
echo [ERRO] Falha durante o processo. Veja as mensagens acima.
pause
exit /b 1
