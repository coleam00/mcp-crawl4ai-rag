@echo off
echo ==========================================
echo  MCP Server + Ollama Standalone
echo ==========================================
echo.

echo [1/4] Verificando Ollama standalone...
docker ps | findstr "ollama-standalone" >nul
if %ERRORLEVEL% NEQ 0 (
    echo Ollama standalone nao esta rodando
    echo.
    echo Para iniciar Ollama standalone:
    echo   build-ollama.bat
    echo.
    echo Ou verificar containers:
    echo   docker ps
    echo.
    pause
    exit /b 1
)
echo ✅ Ollama standalone está rodando!

echo.
echo [2/4] Testando conectividade com Ollama...
curl -s http://localhost:11434/api/tags >nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Erro: Não consegue conectar ao Ollama em localhost:11434
    echo.
    echo Verifique se o container ollama-standalone está healthy:
    echo   docker ps
    echo.
    pause
    exit /b 1
)
echo ✅ Ollama está acessível!

echo.
echo [3/4] Verificando configuração...
findstr "localhost:11434" .env >nul
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️  ATENÇÃO: .env pode estar configurado para container-to-container
    echo Atualizando configuração para localhost...
    
    REM Backup do .env atual
    copy .env .env.backup >nul
    
    REM Substituir ollama:11434 por localhost:11434
    powershell -Command "(Get-Content .env) -replace 'http://ollama:11434/v1', 'http://localhost:11434/v1' | Set-Content .env"
    
    echo ✅ Configuração atualizada para localhost
) else (
    echo ✅ Configuração já usa localhost
)

echo.
echo [4/4] Iniciando MCP server localmente...
echo.
echo Configuração atual:
echo - Ollama: http://localhost:11434 (container ollama-standalone)
echo - MCP Server: http://localhost:8051 (local)
echo - Embedding Model: dengcao/Qwen3-Embedding-8B:Q4_K_M
echo.
echo Iniciando servidor... (Ctrl+C para parar)
echo ==========================================
echo.

REM Verificar se uv está disponível
uv --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Erro: UV não encontrado. Instalando...
    pip install uv
    if %ERRORLEVEL% NEQ 0 (
        echo Erro: Falha ao instalar UV
        pause
        exit /b 1
    )
)

REM Verificar se dependências estão instaladas
if not exist ".venv" (
    echo Criando ambiente virtual...
    uv venv
)

echo Instalando dependências...
uv pip install -e .

if %ERRORLEVEL% NEQ 0 (
    echo Erro: Falha ao instalar dependências
    echo.
    echo Tente manualmente:
    echo   uv venv
    echo   uv pip install -e .
    echo   crawl4ai-setup
    pause
    exit /b 1
)

echo Setup Crawl4AI...
crawl4ai-setup

REM Iniciar o servidor MCP
uv run src/crawl4ai_mcp.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Erro: MCP server falhou ao iniciar
    echo.
    echo Verifique:
    echo 1. Dependências instaladas: uv pip install -e .
    echo 2. Crawl4AI setup: crawl4ai-setup  
    echo 3. Configuração: cat .env
    echo.
    pause
    exit /b 1
)