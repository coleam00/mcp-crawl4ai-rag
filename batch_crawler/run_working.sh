#!/bin/bash

echo "=========================================="
echo "  Batch Crawler Working Fixed - MCP stdio"
echo "=========================================="
echo ""

echo "[1/3] Verificando Python..."
if ! command -v python &> /dev/null; then
    echo "Erro: Python nao encontrado"
    read -p "Press any key to continue..."
    exit 1
fi
echo "Python OK!"

echo ""
echo "[2/3] Verificando dependencias Python..."
echo "Verificando modulos necessarios..."
python -c "import asyncio, json, subprocess, pathlib" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Erro: Modulos Python necessarios nao encontrados"
    read -p "Press any key to continue..."
    exit 1
fi
echo "Modulos OK!"

echo ""
echo "[3/3] Verificando servidor MCP..."
if [ ! -f "../src/crawl4ai_mcp.py" ]; then
    echo "AVISO: Script do servidor MCP nao encontrado em ../src/crawl4ai_mcp.py"
    echo "Certifique-se de que esta executando do diretorio batch_crawler"
    echo "e que o arquivo src/crawl4ai_mcp.py existe"
fi

echo ""
echo "=========================================="
echo "  Iniciando Batch Crawler (MCP stdio)"
echo "=========================================="
echo ""
echo "IMPORTANTE: Este metodo:"
echo "- Executa o servidor MCP localmente via subprocess"
echo "- Usa comunicacao stdio + JSON-RPC 2.0"
echo "- NAO precisa do Docker rodando"
echo "- Precisa das dependencias Python instaladas localmente"
echo ""

python batch_crawler_working_fixed.py "$@"

if [ $? -ne 0 ]; then
    echo ""
    echo "=========================================="
    echo "  ERRO na execucao"
    echo "=========================================="
    echo ""
    echo "Possiveis causas:"
    echo "1. Dependencias Python nao instaladas (veja requirements.txt)"
    echo "2. Script do servidor nao encontrado"
    echo "3. Erro de permissao ou arquivo bloqueado"
    echo ""
    echo "Para usar o Docker em vez disso:"
    echo "  docker-compose up -d"
    echo "  python batch_crawler_simple.py"
    echo ""
    read -p "Press any key to continue..."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Crawling concluido!"
echo "=========================================="
read -p "Press any key to continue..."