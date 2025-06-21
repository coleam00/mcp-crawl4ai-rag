@echo off
echo ==========================================
echo  Batch Crawler Working Fixed - MCP stdio
echo ==========================================
echo.

echo [1/3] Verificando Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Erro: Python nao encontrado
    pause
    exit /b 1
)
echo Python OK!

echo.
echo [2/3] Verificando dependencias Python...
echo Verificando modulos necessarios...
python -c "import asyncio, json, subprocess, pathlib" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Erro: Modulos Python necessarios nao encontrados
    pause
    exit /b 1
)
echo Modulos OK!

echo.
echo [3/3] Verificando servidor MCP...
if not exist "..\src\crawl4ai_mcp.py" (
    echo AVISO: Script do servidor MCP nao encontrado em ..\src\crawl4ai_mcp.py
    echo Certifique-se de que esta executando do diretorio batch_crawler
    echo e que o arquivo src/crawl4ai_mcp.py existe
)

echo.
echo ==========================================
echo  Iniciando Batch Crawler (MCP stdio)
echo ==========================================
echo.
echo IMPORTANTE: Este metodo:
echo - Executa o servidor MCP localmente via subprocess
echo - Usa comunicacao stdio + JSON-RPC 2.0
echo - NAO precisa do Docker rodando
echo - Precisa das dependencias Python instaladas localmente
echo.

python batch_crawler_working_fixed.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ==========================================
    echo  ERRO na execucao
    echo ==========================================
    echo.
    echo Possiveis causas:
    echo 1. Dependencias Python nao instaladas (veja requirements.txt)
    echo 2. Script do servidor nao encontrado
    echo 3. Erro de permissao ou arquivo bloqueado
    echo.
    echo Para usar o Docker em vez disso:
    echo   docker-compose up -d
    echo   python batch_crawler_simple.py
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  Crawling concluido!
echo ==========================================
pause