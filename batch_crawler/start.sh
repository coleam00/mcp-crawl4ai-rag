#!/bin/bash

echo "========================================"
echo "  Batch Crawler MCP - Modo Interativo"
echo "========================================"
echo ""

# Verificar se ambiente virtual existe
VENV_PATH=""
if [ -f ".venv/bin/activate" ]; then
    VENV_PATH=".venv"
elif [ -f ".venv-batch/bin/activate" ]; then
    VENV_PATH=".venv-batch"
    echo "Usando ambiente virtual alternativo: .venv-batch"
else
    echo "ERRO: Ambiente virtual não encontrado!"
    echo ""
    echo "Execute primeiro o setup.sh para criar o ambiente virtual:"
    echo "  ./setup.sh"
    echo ""
    read -p "Press any key to continue..."
    exit 1
fi

# Ativar ambiente virtual
source $VENV_PATH/bin/activate
if [ $? -ne 0 ]; then
    echo "ERRO: Falha ao ativar ambiente virtual"
    read -p "Press any key to continue..."
    exit 1
fi

echo "[OK] Ambiente virtual ativado"
echo ""

# Verificar se o servidor MCP esta rodando
echo "Verificando conexao com servidor MCP..."
python -c "import httpx, asyncio; import sys; resp = asyncio.run(httpx.AsyncClient().get('http://localhost:8051', timeout=5)); sys.exit(0 if resp.status_code in [200, 404, 405] else 1)" >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[OK] Servidor MCP esta respondendo em http://localhost:8051"
else
    echo "[AVISO] Nao foi possivel conectar ao servidor MCP em http://localhost:8051"
    echo "  Certifique-se de que o servidor esta rodando antes de continuar."
    echo "  Execute: uv run src/crawl4ai_mcp.py (no diretorio principal)"
fi
echo ""

# Se argumentos foram passados, usar modo direto
if [ $# -gt 0 ]; then
    echo "Executando em modo direto com argumentos: $*"
    echo ""
    python batch_crawler.py "$@"
    exit $?
fi

# Modo interativo
while true; do
    echo "========================================"
    echo "  Modo Interativo"
    echo "========================================"
    echo ""
    echo "Arquivos de URL disponiveis:"
    echo ""

    # Listar arquivos .txt no diretorio
    count=0
    declare -a files
    for file in *.txt; do
        if [ -f "$file" ]; then
            count=$((count + 1))
            files[$count]="$file"
            echo "  $count. $file"
        fi
    done

    if [ $count -eq 0 ]; then
        echo "  Nenhum arquivo .txt encontrado no diretorio atual."
        echo ""
    else
        echo ""
        echo "Opcoes:"
        echo "  1-$count. Selecionar arquivo listado acima"
    fi
    
    echo "  m. Digitar caminho manualmente"
    echo "  e. Usar example_urls.txt"
    echo "  q. Sair"
    echo ""

    while true; do
        read -p "Escolha uma opcao: " choice
        
        case $choice in
            q|Q)
                echo ""
                echo "Saindo..."
                echo ""
                exit 0
                ;;
            e|E)
                urls_file="example_urls.txt"
                break
                ;;
            m|M)
                echo ""
                read -p "Digite o caminho do arquivo com URLs: " urls_file
                if [ -z "$urls_file" ]; then
                    echo "Caminho invalido."
                    continue
                fi
                break
                ;;
            *)
                # Verificar se eh um numero valido
                if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "$count" ]; then
                    urls_file="${files[$choice]}"
                    break
                else
                    echo "Opcao invalida. Tente novamente."
                fi
                ;;
        esac
    done

    # Verificar se arquivo existe
    if [ ! -f "$urls_file" ]; then
        echo ""
        echo "ERRO: Arquivo '$urls_file' nao encontrado!"
        echo ""
        continue
    fi

    echo ""
    echo "[OK] Arquivo selecionado: $urls_file"
    echo ""

    # Opcoes avancadas
    echo "Configuracoes opcionais (pressione Enter para usar padrao):"
    echo ""

    read -p "Arquivo de saida [crawl_results.json]: " output_file
    output_file=${output_file:-crawl_results.json}

    read -p "Delay entre requisicoes em segundos [1]: " delay
    delay=${delay:-1}

    read -p "URL do servidor MCP [http://localhost:8051]: " server_url
    server_url=${server_url:-http://localhost:8051}

    echo ""
    echo "========================================"
    echo "  Configuracao Final"
    echo "========================================"
    echo ""
    echo "  Arquivo URLs: $urls_file"
    echo "  Arquivo saida: $output_file"
    echo "  Delay: $delay segundos"
    echo "  Servidor: $server_url"
    echo ""

    read -p "Confirmar e iniciar? [S/n]: " confirm
    if [[ "$confirm" == "n" || "$confirm" == "N" ]]; then
        continue
    fi

    echo ""
    echo "Iniciando crawling..."
    echo "========================================"
    echo ""

    # Executar o script que funciona de verdade
    python batch_crawler_working.py "$urls_file" --output "$output_file" --delay "$delay"

    echo ""
    echo "========================================"
    echo "  Crawling concluido!"
    echo "========================================"
    echo ""

    if [ -f "$output_file" ]; then
        echo "[OK] Resultados salvos em: $output_file"
        echo ""
        read -p "Abrir arquivo de resultados? [S/n]: " open_results
        if [[ "$open_results" != "n" && "$open_results" != "N" ]]; then
            if command -v xdg-open &> /dev/null; then
                xdg-open "$output_file"
            elif [[ "$OSTYPE" == "darwin"* ]]; then
                open "$output_file"
            else
                echo "Arquivo disponivel em: $output_file"
            fi
        fi
    fi

    echo ""
    read -p "Processar outro arquivo? [S/n]: " repeat
    if [[ "$repeat" == "n" || "$repeat" == "N" ]]; then
        break
    fi
done

echo ""
echo "Saindo..."
echo ""