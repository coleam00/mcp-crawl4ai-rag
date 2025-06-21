@echo off
echo ===============================================
echo Health Check Test Script
echo ===============================================
echo.

echo Testing MCP Server endpoints...
echo.

echo [1] Basic Health Check:
echo GET http://localhost:8051/health
curl -f http://localhost:8051/health
echo.
echo Return code: %ERRORLEVEL%
echo.

echo [2] Detailed Health Check (JSON):
echo GET http://localhost:8051/health?format=json
curl -f http://localhost:8051/health?format=json | jq . 2>nul || curl -f http://localhost:8051/health?format=json
echo.
echo Return code: %ERRORLEVEL%
echo.

echo [3] Ollama Status:
echo GET http://localhost:11434/api/tags
curl -s http://localhost:11434/api/tags | jq ".models[].name" 2>nul || curl -s http://localhost:11434/api/tags
echo.

echo [4] Test Embedding Generation:
echo POST http://localhost:11434/api/embed
curl -X POST http://localhost:11434/api/embed ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"dengcao/Qwen3-Embedding-8B:Q4_K_M\",\"input\":\"Hello, this is a test embedding\"}" ^
  | jq ".embeddings[0][:5]" 2>nul || echo "Embedding generated (install jq for pretty output)"
echo.

echo [5] MCP Server Info:
echo.
netstat -an | findstr ":8051" && echo "✓ MCP Server listening on port 8051" || echo "✗ MCP Server not responding on port 8051"
netstat -an | findstr ":11434" && echo "✓ Ollama listening on port 11434" || echo "✗ Ollama not responding on port 11434"
echo.

echo ===============================================
echo Health check tests completed!
echo ===============================================
pause