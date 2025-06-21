@echo off
echo ==========================================
echo  Container Status Check
echo ==========================================
echo.

echo [1] All running containers:
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"
echo.

echo [2] MCP Stack containers:
echo Checking for MCP stack containers...
docker ps | findstr "mcp-crawl4ai-rag" && echo "MCP stack is running" || echo "MCP stack is NOT running"
echo.

echo [3] Ollama containers:
echo Checking for Ollama containers...
docker ps | findstr "ollama" && echo "Ollama containers found" || echo "No Ollama containers running"
echo.

echo [4] Ollama standalone container:
echo Checking ollama-standalone specifically...
docker ps | findstr "ollama-standalone" && echo "✅ Ollama standalone is running" || echo "❌ Ollama standalone is NOT running"
echo.

echo [5] Port usage:
echo Checking port 11434 (Ollama)...
netstat -an | findstr ":11434" && echo "✅ Port 11434 is in use" || echo "❌ Port 11434 is available"

echo Checking port 8051 (MCP)...
netstat -an | findstr ":8051" && echo "✅ Port 8051 is in use" || echo "❌ Port 8051 is available"
echo.

echo [6] Networks:
echo Available Docker networks:
docker network ls | findstr "ollama\|mcp"
echo.

echo [7] Volumes:
echo Available Docker volumes:
docker volume ls | findstr "ollama"
echo.

echo ==========================================
echo  Summary
echo ==========================================
echo.
echo To run MCP stack with integrated Ollama:
echo   build.bat
echo.
echo To run Ollama standalone only:
echo   build-ollama.bat
echo.
echo To stop all containers:
echo   docker-compose down
echo   docker-compose -f docker-compose.ollama.yml down
echo.
pause