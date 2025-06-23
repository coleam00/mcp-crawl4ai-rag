#!/bin/bash

echo "========================================"
echo "  Limpeza de Ambientes Virtuais"
echo "========================================"
echo ""

echo "Este script ira remover todos os ambientes virtuais existentes."
echo "Isso pode ajudar a resolver problemas de permissao."
echo ""

read -p "Deseja continuar? [S/n]: " confirm
if [[ "$confirm" == "n" || "$confirm" == "N" ]]; then
    echo ""
    exit 0
fi

echo ""
echo "Removendo ambientes virtuais..."

# Tentar fechar processos que podem estar usando arquivos
echo "Fechando possíveis processos Python..."
pkill -f python 2>/dev/null
pkill -f pythonw 2>/dev/null

sleep 2

# Remover pastas de ambiente virtual
if [ -d ".venv" ]; then
    echo "Removendo .venv..."
    rm -rf ".venv" 2>/dev/null
    if [ -d ".venv" ]; then
        echo "Tentando forcar remocao..."
        sudo rm -rf ".venv" 2>/dev/null
    fi
    if [ -d ".venv" ]; then
        echo "[AVISO] Nao foi possivel remover .venv completamente"
        echo "Tente executar com sudo ou reiniciar o computador"
    else
        echo "[OK] .venv removido"
    fi
fi

if [ -d ".venv-batch" ]; then
    echo "Removendo .venv-batch..."
    rm -rf ".venv-batch" 2>/dev/null
    if [ -d ".venv-batch" ]; then
        echo "Tentando forcar remocao..."
        sudo rm -rf ".venv-batch" 2>/dev/null
    fi
    if [ -d ".venv-batch" ]; then
        echo "[AVISO] Nao foi possivel remover .venv-batch completamente"
    else
        echo "[OK] .venv-batch removido"
    fi
fi

# Remover arquivos de log antigos
if ls crawler_*.log 1> /dev/null 2>&1; then
    echo "Removendo logs antigos..."
    rm crawler_*.log 2>/dev/null
    echo "[OK] Logs removidos"
fi

# Remover arquivos de resultados antigos (opcional)
read -p "Remover arquivos de resultados (*.json)? [s/N]: " remove_results
if [[ "$remove_results" == "s" || "$remove_results" == "S" ]]; then
    if ls *.json 1> /dev/null 2>&1; then
        rm *.json 2>/dev/null
        echo "[OK] Arquivos JSON removidos"
    fi
fi

echo ""
echo "========================================"
echo "  Limpeza concluida!"
echo "========================================"
echo ""
echo "Agora voce pode executar ./setup.sh novamente."
echo ""
read -p "Press any key to continue..."