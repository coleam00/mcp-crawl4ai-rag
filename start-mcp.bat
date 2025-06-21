@echo off
echo ===============================================
echo MCP Server Startup Script
echo ===============================================
echo.

echo [1/3] Checking Python and UV installation...
uv --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: UV not found. Please install UV first:
    echo curl -LsSf https://astral.sh/uv/install.ps1 ^| powershell
    pause
    exit /b 1
)
echo UV found!

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python not found. Please install Python 3.12+
    pause
    exit /b 1
)
echo Python found!
echo.

echo [2/3] Setting up virtual environment and dependencies...
if not exist ".venv" (
    echo Creating virtual environment...
    uv venv
    if %ERRORLEVEL% NEQ 0 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
)

echo Installing dependencies...
uv pip install -e .
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed!
echo.

echo [3/3] Starting MCP server...
echo.
echo Server configuration:
echo - Host: %HOST%
echo - Port: %PORT%
echo - Transport: %TRANSPORT%
echo - Embedding Model: %EMBEDDING_MODEL%
echo - Ollama API: %EMBEDDING_MODEL_API_BASE%
echo.
echo Starting server... (Press Ctrl+C to stop)
echo ===============================================
echo.

uv run src/crawl4ai_mcp.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error: MCP server failed to start
    echo Check the logs above for error details
    pause
    exit /b 1
)