@echo off
echo ==========================================
echo  Batch Crawler HTTP - MCP Crawl4AI RAG
echo ==========================================
echo.

echo [1/3] Verificando ambiente Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Erro: Python nao encontrado. Instale Python 3.8+ primeiro.
    pause
    exit /b 1
)
echo Python encontrado!

echo.
echo [2/3] Verificando dependencias...
python -c "import aiohttp, aiofiles" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Instalando dependencias necessarias...
    pip install aiohttp aiofiles
    if %ERRORLEVEL% NEQ 0 (
        echo Erro: Falha ao instalar dependencias
        pause
        exit /b 1
    )
)
echo Dependencias OK!

echo.
echo [3/3] Verificando conexao com servidor MCP...
python -c "import requests; requests.get('http://localhost:8051/health', timeout=5)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo AVISO: Servidor MCP nao esta respondendo em http://localhost:8051
    echo Certifique-se de que o Docker esta rodando:
    echo   docker-compose up -d
    echo.
    set /p continue="Continuar mesmo assim? [y/N]: "
    if /i not "%continue%"=="y" (
        echo Operacao cancelada.
        pause
        exit /b 1
    )
) else (
    echo Servidor MCP OK!
)

echo.
echo ==========================================
echo  Iniciando Batch Crawler HTTP
echo ==========================================
echo.

python batch_crawler_fixed.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Erro na execucao do crawler
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  Crawling concluido!
echo ==========================================
pause