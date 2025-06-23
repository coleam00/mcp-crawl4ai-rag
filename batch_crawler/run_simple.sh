#!/bin/bash

echo "=========================================="
echo "  Batch Crawler Simple - FastMCP"
echo "=========================================="
echo ""

echo "Verificando Python..."
if ! command -v python &> /dev/null; then
    echo "Erro: Python nao encontrado"
    read -p "Press any key to continue..."
    exit 1
fi

echo "Verificando requests..."
python -c "import requests" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Instalando requests..."
    pip install requests
fi

echo ""
echo "Testando conexao com servidor MCP..."
python -c "import requests; print('OK' if requests.get('http://localhost:8051/health', timeout=5).status_code == 200 else 'ERRO')" 2>/dev/null
echo ""

echo "Iniciando crawler..."
echo "=========================================="
python batch_crawler_simple.py "$@"

read -p "Press any key to continue..."