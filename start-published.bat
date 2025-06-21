@echo off
echo ===============================================
echo  MCP Crawl4AI RAG - Start Published Image
echo ===============================================
echo.
echo Using published Docker Hub image: drnit29/mcp-crawl4ai-rag:latest
echo Configuration: docker-compose.published.yml
echo.

echo [1/4] Stopping any existing containers...
docker-compose -f docker-compose.published.yml down >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Warning: No existing containers to stop
) else (
    echo ✅ Existing containers stopped
)
echo.

echo [2/4] Starting services with published image...
echo This will:
echo - Start MCP server using drnit29/mcp-crawl4ai-rag:latest
echo - Start Ollama with GPU support
echo - Download Qwen3-Embedding models automatically
echo.
docker-compose -f docker-compose.published.yml up -d
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Error: Failed to start services
    echo.
    echo Troubleshooting:
    echo 1. Check if .env file exists and is configured
    echo 2. Verify Docker is running
    echo 3. Check if ports 8051 and 11434 are available
    echo.
    pause
    exit /b 1
)
echo.

echo [3/4] Waiting for services to initialize...
echo Please wait while containers start and models download...
timeout /t 15 /nobreak >nul
echo.

echo [4/4] Checking service status...
docker-compose -f docker-compose.published.yml ps
echo.

echo ===============================================
echo  Services Started Successfully!
echo ===============================================
echo.
echo Available endpoints:
echo - MCP Server: http://localhost:8051
echo - Health Check: http://localhost:8051/health
echo - Health Check (JSON): http://localhost:8051/health?format=json
echo - Ollama: http://localhost:11434
echo.
echo Model download status:
echo - Qwen3-Embedding models are downloading in background
echo - Check logs: docker-compose -f docker-compose.published.yml logs -f ollama-init
echo.
echo Management commands:
echo - View logs: docker-compose -f docker-compose.published.yml logs -f
echo - Stop services: docker-compose -f docker-compose.published.yml down
echo - Restart: docker-compose -f docker-compose.published.yml restart
echo.
echo Testing MCP server health...
timeout /t 5 /nobreak >nul
curl -f http://localhost:8051/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ MCP Server is healthy and responding!
) else (
    echo ⚠️  MCP Server is still starting up
    echo    Check health in a few moments: curl http://localhost:8051/health
)
echo.
echo Ready to use! 🚀
pause