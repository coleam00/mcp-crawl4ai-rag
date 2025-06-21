@echo off
echo ===============================================
echo Ollama Standalone - Qwen3-Embedding Setup
echo ===============================================
echo.
echo This script builds Ollama ONLY (no MCP server)
echo Container name: ollama-standalone
echo Network: ollama-network (isolated from MCP)
echo.

echo [1/4] Stopping existing Ollama standalone containers...
docker-compose -f docker-compose.ollama.yml down
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Error stopping containers, continuing...
)
echo.

echo [2/4] Starting Ollama standalone service with GPU support...
docker-compose -f docker-compose.ollama.yml up -d ollama
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to start Ollama standalone service
    pause
    exit /b 1
)
echo.

echo [3/4] Waiting for Ollama standalone to be healthy...
:check_ollama
timeout /t 5 /nobreak >nul
docker-compose -f docker-compose.ollama.yml ps ollama | findstr "healthy" >nul
if %ERRORLEVEL% NEQ 0 (
    echo Waiting for Ollama standalone health check...
    goto check_ollama
)
echo Ollama standalone is healthy!
echo.

echo [4/4] Downloading Qwen3-Embedding models...
echo This will download ~5.4GB of models (0.6B + 8B variants)
docker-compose -f docker-compose.ollama.yml up ollama-init
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Model download may have failed, but Ollama is running
)
echo.

echo ===============================================
echo Ollama Standalone setup completed successfully!
echo ===============================================
echo.
echo Container Information:
echo - Container name: ollama-standalone
echo - Network: ollama-network (isolated)
echo - Volume: ollama_standalone_data
echo.
echo Service Status:
docker-compose -f docker-compose.ollama.yml ps
echo.
echo Container Details:
docker ps | findstr "ollama-standalone" || echo "Container not visible in docker ps"
echo.
echo GPU Status:
docker-compose -f docker-compose.ollama.yml logs ollama | findstr "GPU\|gpu\|CUDA\|cuda\|NVIDIA\|nvidia" | tail -3
echo.
echo Available Models:
curl -s http://localhost:11434/api/tags | jq ".models[].name" 2>nul || echo "Install jq for pretty JSON or check: http://localhost:11434/api/tags"
echo.
echo Available endpoints:
echo - Ollama API: http://localhost:11434
echo - List models: http://localhost:11434/api/tags
echo - Test embedding: curl -X POST http://localhost:11434/api/embed -d "{\"model\":\"dengcao/Qwen3-Embedding-8B:Q4_K_M\",\"input\":\"test\"}"
echo.
echo Management commands:
echo - View logs: docker-compose -f docker-compose.ollama.yml logs -f ollama
echo - Stop: docker-compose -f docker-compose.ollama.yml down
echo - Direct access: docker exec -it ollama-standalone /bin/bash
echo.
echo Next steps for MCP integration:
echo 1. Update .env: EMBEDDING_MODEL_API_BASE=http://localhost:11434/v1
echo 2. Start MCP server locally: uv run src/crawl4ai_mcp.py
echo 3. Test health check: curl http://localhost:8051/health?format=json
echo.
echo Note: This Ollama runs independently from the MCP stack!
pause