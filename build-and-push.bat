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

echo [4/8] Starting container with built image for testing...
echo Stopping any existing containers first...
docker-compose down >nul 2>&1
docker-compose -f docker-compose.published.yml down >nul 2>&1

echo.
echo Starting services using new built image...
docker-compose -f docker-compose.published.yml up -d
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to start services with built image
    echo.
    echo Troubleshooting:
    echo 1. Check if image was built: docker images | findstr drnit29/mcp-crawl4ai-rag
    echo 2. Verify network connectivity: docker network ls
    echo 3. Check logs: docker-compose -f docker-compose.published.yml logs
    echo.
    pause
    exit /b 1
)

echo Waiting for services to initialize...
timeout /t 20 /nobreak >nul

echo Testing service health...
timeout /t 5 /nobreak >nul
curl -f http://localhost:8051/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ MCP Server is healthy and responding!
    echo ✅ Built image is working correctly
    echo.
) else (
    echo ⚠️  MCP Server is still starting up
    echo Waiting a bit more...
    timeout /t 10 /nobreak >nul
    curl -f http://localhost:8051/health >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo ✅ MCP Server is now healthy!
    ) else (
        echo ❌ MCP Server health check failed
        echo Container logs:
        docker-compose -f docker-compose.published.yml logs --tail=20 mcp-server
        pause
        exit /b 1
    )
)

echo Services Status:
docker-compose -f docker-compose.published.yml ps
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

echo [8/8] Finalizing deployment...
echo Services are already running with the newly built and pushed image.
echo Verifying final status...
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

echo Final Services Status:
docker-compose -f docker-compose.published.yml ps
echo.

echo Final health verification...
curl -f http://localhost:8051/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ MCP Server is healthy and ready for use!
    echo ✅ Image successfully built, tested, pushed, and deployed!
    curl -f http://localhost:8051/health?format=json 2>nul
    echo.
) else (
    echo ⚠️  Note: Service may still be initializing
    echo    Status check: curl http://localhost:8051/health
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