@echo off
echo ==========================================
echo  Batch Crawler Docker - Usa Container MCP
echo ==========================================
echo.

echo [1/4] Verificando Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Erro: Python nao encontrado
    pause
    exit /b 1
)
echo Python OK!

echo.
echo [2/4] Verificando requests...
python -c "import requests" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Instalando requests...
    pip install requests
    if %ERRORLEVEL% NEQ 0 (
        echo Erro ao instalar requests
        pause
        exit /b 1
    )
)
echo Requests OK!

echo.
echo [3/4] Verificando Docker...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo AVISO: Docker nao encontrado
    echo Este script precisa do Docker para funcionar corretamente
    echo.
    set /p continue="Continuar mesmo assim? [y/N]: "
    if /i not "%continue%"=="y" (
        echo Operacao cancelada
        pause
        exit /b 1
    )
) else (
    echo Docker OK!
)

echo.
echo [4/4] Verificando container MCP...
docker ps | findstr "mcp-crawl4ai-rag-mcp-server" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo AVISO: Container MCP nao esta rodando
    echo.
    echo Para iniciar o container:
    echo   docker-compose up -d
    echo.
    echo Ou para verificar containers:
    echo   docker ps
    echo.
    set /p continue="Continuar mesmo assim? [y/N]: "
    if /i not "%continue%"=="y" (
        echo Operacao cancelada
        echo.
        echo Dica: Execute 'docker-compose up -d' primeiro
        pause
        exit /b 1
    )
) else (
    echo Container MCP rodando!
)

echo.
echo ==========================================
echo  Iniciando Batch Crawler (Docker)
echo ==========================================
echo.
echo IMPORTANTE: Este metodo:
echo - Usa o container Docker que ja esta rodando
echo - Executa comandos dentro do container via 'docker exec'
echo - NAO precisa de dependencias Python locais
echo - Usa processamento MCP completo (embeddings, chunks, etc.)
echo.

python batch_crawler_docker.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ==========================================
    echo  ERRO na execucao
    echo ==========================================
    echo.
    echo Possiveis causas:
    echo 1. Container MCP nao esta rodando
    echo 2. Docker nao esta acessivel
    echo 3. Erro de rede ou timeout
    echo.
    echo Para resolver:
    echo   docker-compose up -d
    echo   docker ps  # verificar se container esta rodando
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  Crawling concluido!
echo ==========================================
pause