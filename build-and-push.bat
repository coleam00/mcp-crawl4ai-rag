@echo off
echo ===============================================
echo MCP Crawl4AI RAG - Build and Push to Docker Hub
echo ===============================================
echo.
echo Target image: drnit29/mcp-crawl4ai-rag:latest
echo Registry: Docker Hub
echo.

echo [1/8] Stopping existing containers...
docker-compose down
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Error stopping containers, continuing...
)
echo.

echo [2/8] Building MCP server container with custom tag...
echo This may take several minutes due to dependencies...
docker build -t drnit29/mcp-crawl4ai-rag:latest --build-arg PORT=8051 .
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to build MCP server container
    pause
    exit /b 1
)
echo Build completed successfully!
echo.

echo [3/8] Verifying built image...
docker images | findstr "drnit29/mcp-crawl4ai-rag"
if %ERRORLEVEL% NEQ 0 (
    echo Error: Built image not found
    pause
    exit /b 1
)
echo Image verification successful!
echo.

echo [4/8] Testing built image locally...
echo Starting temporary container for testing...
docker run -d --name mcp-test-container -p 8052:8051 drnit29/mcp-crawl4ai-rag:latest
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to start test container
    pause
    exit /b 1
)

echo Waiting for container to start...
timeout /t 10 /nobreak >nul

echo Testing container health...
curl -f http://localhost:8052/health >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Test container not responding (may need more time)
    echo Continuing with push...
) else (
    echo Test container is healthy!
)

echo Stopping test container...
docker stop mcp-test-container >nul 2>&1
docker rm mcp-test-container >nul 2>&1
echo.

echo [5/8] Docker Hub login...
echo.
echo Please enter your Docker Hub credentials:
docker login
if %ERRORLEVEL% NEQ 0 (
    echo Error: Docker Hub login failed
    echo.
    echo Make sure you have a Docker Hub account and correct credentials
    echo Visit: https://hub.docker.com/signup
    pause
    exit /b 1
)
echo Docker Hub login successful!
echo.

echo [6/8] Pushing image to Docker Hub...
echo This may take several minutes depending on your upload speed...
echo.
docker push drnit29/mcp-crawl4ai-rag:latest
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to push image to Docker Hub
    echo.
    echo Possible causes:
    echo 1. Network connectivity issues
    echo 2. Docker Hub authentication expired
    echo 3. Repository permissions
    echo.
    pause
    exit /b 1
)
echo Image pushed successfully to Docker Hub!
echo.

echo [7/8] Creating additional tags...
echo Creating 'latest' tag confirmation...
docker tag drnit29/mcp-crawl4ai-rag:latest drnit29/mcp-crawl4ai-rag:v1.0
docker push drnit29/mcp-crawl4ai-rag:v1.0
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Failed to push v1.0 tag, but latest was successful
)
echo.

echo [8/8] Starting services with published image...
echo Stopping any existing containers first...
docker-compose down >nul 2>&1
docker-compose -f docker-compose.published.yml down >nul 2>&1

echo.
echo Starting services using published image configuration...
docker-compose -f docker-compose.published.yml up -d
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to start services with published image
    echo.
    echo Troubleshooting:
    echo 1. Check if published image is available: docker images | findstr drnit29/mcp-crawl4ai-rag
    echo 2. Verify network connectivity: docker network ls
    echo 3. Check logs: docker-compose -f docker-compose.published.yml logs
    echo.
    pause
    exit /b 1
)
echo.

echo Waiting for services to initialize...
timeout /t 15 /nobreak >nul
echo.

echo ===============================================
echo Build and Push completed successfully!
echo ===============================================
echo.
echo Docker Hub Repository: https://hub.docker.com/r/drnit29/mcp-crawl4ai-rag
echo Image Tags:
echo - drnit29/mcp-crawl4ai-rag:latest
echo - drnit29/mcp-crawl4ai-rag:v1.0
echo.

echo Services Status (using published image):
docker-compose -f docker-compose.published.yml ps
echo.

echo Testing service health...
timeout /t 5 /nobreak >nul
curl -f http://localhost:8051/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ MCP Server is healthy and responding!
    curl -f http://localhost:8051/health?format=json 2>nul
    echo.
) else (
    echo ⚠️  MCP Server is still starting up or having issues
    echo    Check status in a few moments: curl http://localhost:8051/health
    echo    View logs: docker-compose -f docker-compose.published.yml logs -f mcp-server
)
echo.

echo Available endpoints:
echo - MCP Server: http://localhost:8051
echo - Health Check: http://localhost:8051/health
echo - Health Check (JSON): http://localhost:8051/health?format=json
echo - Ollama: http://localhost:11434
echo.

echo Management commands:
echo - View logs: docker-compose -f docker-compose.published.yml logs -f
echo - Stop services: docker-compose -f docker-compose.published.yml down
echo - Restart services: docker-compose -f docker-compose.published.yml restart
echo.

echo Usage for others:
echo docker pull drnit29/mcp-crawl4ai-rag:latest
echo docker run -p 8051:8051 --env-file .env drnit29/mcp-crawl4ai-rag:latest
echo.

echo Services are now running with the published image! 🚀
pause