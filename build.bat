@echo off
echo ===============================================
echo MCP Crawl4AI RAG - Build and Deploy Script
echo ===============================================
echo.

echo [1/5] Stopping existing containers...
docker-compose down
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Error stopping containers, continuing...
)
echo.

echo [2/5] Building MCP server container...
echo This may take several minutes due to CUDA dependencies...
docker-compose build mcp-server
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to build MCP server container
    pause
    exit /b 1
)
echo Build completed successfully!
echo.

echo [3/5] Starting Ollama service...
docker-compose up -d ollama
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to start Ollama service
    pause
    exit /b 1
)
echo.

echo [4/5] Waiting for Ollama to be healthy...
:check_ollama
timeout /t 5 /nobreak >nul
docker-compose ps ollama | findstr "healthy" >nul
if %ERRORLEVEL% NEQ 0 (
    echo Waiting for Ollama health check...
    goto check_ollama
)
echo Ollama is healthy!
echo.

echo [5/5] Starting all services...
docker-compose up -d
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to start all services
    pause
    exit /b 1
)
echo.

echo ===============================================
echo Deployment completed successfully!
echo ===============================================
echo.
echo Services Status:
docker-compose ps
echo.
echo Available endpoints:
echo - MCP Server: http://localhost:8051
echo - Health Check: http://localhost:8051/health
echo - Health Check (JSON): http://localhost:8051/health?format=json
echo - Ollama: http://localhost:11434
echo.
echo To view logs: docker-compose logs -f [service_name]
echo To stop all: docker-compose down
echo.
pause