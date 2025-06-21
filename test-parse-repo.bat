@echo off
echo ==========================================
echo  Test Parse GitHub Repository Function
echo ==========================================
echo.

echo [1/3] Checking MCP server status...
curl -f http://localhost:8051/health >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: MCP server not responding
    echo.
    echo Make sure containers are running:
    echo   docker-compose up -d
    echo.
    echo Then check status:
    echo   curl http://localhost:8051/health?format=json
    echo.
    pause
    exit /b 1
)
echo MCP server is responding!

echo.
echo [2/3] Checking Knowledge Graph status...
curl -s "http://localhost:8051/health?format=json" | findstr "neo4j" >nul
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Could not verify Neo4j status
    echo Make sure USE_KNOWLEDGE_GRAPH=true in .env
)

echo.
echo [3/3] Starting test...
echo.
echo IMPORTANT NOTES:
echo - This test may take 10-30 minutes for large repositories
echo - The function was fixed to handle SSE communication errors
echo - Results are compacted to avoid response size issues
echo - Processing will continue even if SSE connection breaks
echo.

python test-parse-repo.py

echo.
echo ==========================================
echo Test completed!
echo ==========================================
echo.
echo If you encountered errors:
echo 1. Check Docker logs: docker-compose logs mcp-server
echo 2. Verify Neo4j connection: curl http://localhost:8051/health?format=json
echo 3. Check .env: USE_KNOWLEDGE_GRAPH=true
echo.
pause