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
echo       All the Utils (WinToolbox) - Criador de Instalador
echo ========================================================

"%PY%" build.py --mode installer

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
