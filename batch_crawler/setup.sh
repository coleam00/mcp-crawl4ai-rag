#!/bin/bash

echo "========================================"
echo "  Setup do Batch Crawler MCP"
echo "========================================"
echo ""

# Verificar se uv esta instalado
if ! command -v uv &> /dev/null; then
    echo "ERRO: uv nao esta instalado ou nao esta no PATH"
    echo ""
    echo "Para instalar o uv, execute:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  ou visite: https://docs.astral.sh/uv/getting-started/installation/"
    echo ""
    read -p "Press any key to continue..."
    exit 1
fi

echo "[OK] uv encontrado"
echo ""

# Remover ambiente virtual existente se houver
if [ -d ".venv" ]; then
    echo "Removendo ambiente virtual existente..."
    rm -rf ".venv" 2>/dev/null
    sleep 2
fi

# Criar ambiente virtual
echo "Criando ambiente virtual..."
uv venv .venv
if [ $? -ne 0 ]; then
    echo "ERRO: Falha ao criar ambiente virtual"
    echo ""
    echo "Possíveis soluções:"
    echo "  1. Execute com sudo se necessário"
    echo "  2. Certifique-se de que nenhum processo está usando a pasta .venv"
    echo "  3. Tente fechar IDEs/editores que possam estar usando arquivos da pasta"
    echo "  4. Use: rm -rf .venv para remover manualmente"
    echo ""
    echo "Tentando solução alternativa..."
    sleep 3
    
    # Tentar com nome alternativo
    echo "Tentando criar com nome alternativo..."
    uv venv .venv-batch
    if [ $? -ne 0 ]; then
        echo "ERRO: Ainda não foi possível criar ambiente virtual"
        echo "Tente executar com sudo ou feche todos os programas que possam estar usando a pasta"
        read -p "Press any key to continue..."
        exit 1
    fi
    
    # Usar ambiente alternativo
    VENV_PATH=".venv-batch"
    echo "[OK] Ambiente virtual criado em .venv-batch"
else
    VENV_PATH=".venv"
    echo "[OK] Ambiente virtual criado em .venv"
fi

echo ""

# Ativar ambiente virtual e instalar dependencias
echo "Ativando ambiente virtual e instalando dependencias..."
source $VENV_PATH/bin/activate

echo "Instalando dependencias do requirements.txt..."
uv pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERRO: Falha ao instalar dependencias"
    read -p "Press any key to continue..."
    exit 1
fi

echo ""
echo "[OK] Dependencias instaladas com sucesso!"
echo ""

# Verificar instalacoes
echo "Verificando instalacoes..."
python -c "import httpx, aiofiles; print('[OK] Todas as dependencias estao funcionando')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[AVISO] Algumas dependencias podem nao estar funcionando corretamente"
fi

echo ""
echo "========================================"
echo "  Setup concluido com sucesso!"
echo "========================================"
echo ""
echo "Para usar o batch crawler:"
echo "  1. Execute start.sh para iniciar o modo interativo"
echo "  2. Ou use: ./start.sh [arquivo_urls] [opcoes]"
echo ""
echo "Exemplos:"
echo "  ./start.sh"
echo "  ./start.sh example_urls.txt"
echo "  ./start.sh meus_urls.txt --output resultados.json"
echo ""
read -p "Press any key to continue..."