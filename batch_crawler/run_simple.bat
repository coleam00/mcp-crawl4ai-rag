@echo off
echo ==========================================
echo  Batch Crawler Simple - FastMCP
echo ==========================================
echo.

echo Verificando Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Erro: Python nao encontrado
    pause
    exit /b 1
)

echo Verificando requests...
python -c "import requests" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Instalando requests...
    pip install requests
)

echo.
echo Testando conexao com servidor MCP...
python -c "import requests; print('OK' if requests.get('http://localhost:8051/health', timeout=5).status_code == 200 else 'ERRO')" 2>nul
echo.

echo Iniciando crawler...
echo ==========================================
python batch_crawler_simple.py %*

pause