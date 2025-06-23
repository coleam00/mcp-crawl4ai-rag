#!/bin/bash

set -e

# Cores para logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Carregar variáveis de ambiente
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

log "==============================================="
log "    Qwen3-Embedding Deploy Script"
log "==============================================="

# Função de ajuda
show_help() {
    echo "Uso: $0 [OPÇÃO]"
    echo ""
    echo "Opções:"
    echo "  --build      Construir imagem Docker"
    echo "  --start      Iniciar serviços"
    echo "  --stop       Parar serviços"
    echo "  --restart    Reiniciar serviços"
    echo "  --logs       Mostrar logs"
    echo "  --test       Executar testes"
    echo "  --clean      Limpar containers e imagens"
    echo "  --status     Mostrar status dos serviços"
    echo "  --help       Mostrar esta ajuda"
    echo ""
    echo "Exemplos:"
    echo "  $0 --build --test"
    echo "  $0 --start"
    echo "  $0 --restart --logs"
}

# Verificar dependências
check_dependencies() {
    log "Verificando dependências..."
    
    local missing_deps=()
    
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing_deps+=("docker-compose")
    fi
    
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        error "Dependências não encontradas: ${missing_deps[*]}"
        error "Por favor, instale as dependências necessárias"
        exit 1
    fi
    
    log "✓ Dependências verificadas"
}

# Verificar se Docker está rodando
check_docker() {
    if ! docker info &> /dev/null; then
        error "Docker não está rodando!"
        error "Por favor, inicie o Docker e tente novamente"
        exit 1
    fi
}

# Determinar comando do docker-compose
get_compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif docker compose version &> /dev/null; then
        echo "docker compose"
    else
        error "docker-compose não encontrado!"
        exit 1
    fi
}

# Construir imagem
build_image() {
    log "Construindo imagem Docker..."
    ./scripts/build.sh
}

# Iniciar serviços
start_services() {
    log "Iniciando serviços..."
    
    local compose_cmd=$(get_compose_cmd)
    
    # Criar diretórios necessários
    mkdir -p logs models
    
    # Verificar se .env existe
    if [ ! -f .env ]; then
        warn "Arquivo .env não encontrado, criando a partir do exemplo..."
        cp .env.example .env
        warn "Por favor, edite o arquivo .env com suas configurações"
    fi
    
    # Iniciar com docker-compose
    $compose_cmd up -d
    
    log "Aguardando serviços iniciarem..."
    sleep 10
    
    # Verificar se os serviços estão rodando
    if $compose_cmd ps | grep -q "Up"; then
        log "✓ Serviços iniciados com sucesso"
        
        # Mostrar status
        show_status
        
        # Aguardar API ficar pronta
        log "Aguardando API ficar pronta..."
        local max_attempts=30
        local attempt=1
        
        while [ $attempt -le $max_attempts ]; do
            if curl -s -f http://localhost:${HOST_PORT:-8000}/health > /dev/null 2>&1; then
                log "✓ API está pronta!"
                log "🎉 Deploy concluído com sucesso!"
                log ""
                log "Acesse a API em: http://localhost:${HOST_PORT:-8000}"
                log "Documentação: http://localhost:${HOST_PORT:-8000}/docs"
                return 0
            fi
            
            log "Tentativa $attempt/$max_attempts - Aguardando 10s..."
            sleep 10
            ((attempt++))
        done
        
        warn "API demorou para ficar pronta, mas os serviços estão rodando"
        warn "Verifique os logs com: $0 --logs"
    else
        error "✗ Falha ao iniciar serviços"
        show_logs
        exit 1
    fi
}

# Parar serviços
stop_services() {
    log "Parando serviços..."
    
    local compose_cmd=$(get_compose_cmd)
    $compose_cmd down
    
    log "✓ Serviços parados"
}

# Reiniciar serviços
restart_services() {
    log "Reiniciando serviços..."
    stop_services
    sleep 5
    start_services
}

# Mostrar logs
show_logs() {
    local compose_cmd=$(get_compose_cmd)
    
    if [ "$1" = "--follow" ] || [ "$1" = "-f" ]; then
        log "Seguindo logs (Ctrl+C para sair)..."
        $compose_cmd logs -f
    else
        log "Últimos logs:"
        $compose_cmd logs --tail=50
    fi
}

# Executar testes
run_tests() {
    log "Executando testes..."
    
    # Verificar se a API está rodando
    if ! curl -s -f http://localhost:${HOST_PORT:-8000}/health > /dev/null 2>&1; then
        warn "API não está rodando, iniciando serviços..."
        start_services
    fi
    
    # Executar testes
    ./scripts/test.sh --wait
}

# Limpar containers e imagens
clean_all() {
    log "Limpando containers e imagens..."
    
    local compose_cmd=$(get_compose_cmd)
    
    # Parar e remover containers
    $compose_cmd down -v --remove-orphans
    
    # Remover imagens
    if docker images | grep -q "qwen3-embedding"; then
        docker rmi $(docker images | grep "qwen3-embedding" | awk '{print $3}') || true
    fi
    
    # Limpar volumes não utilizados
    docker volume prune -f || true
    
    # Limpar redes não utilizadas
    docker network prune -f || true
    
    log "✓ Limpeza concluída"
}

# Mostrar status dos serviços
show_status() {
    local compose_cmd=$(get_compose_cmd)
    
    log "Status dos serviços:"
    $compose_cmd ps
    
    echo ""
    log "Uso de recursos:"
    if docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | grep -q qwen3; then
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -1
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep qwen3 || true
    else
        echo "Nenhum container rodando"
    fi
    
    echo ""
    if curl -s -f http://localhost:${HOST_PORT:-8000}/health > /dev/null 2>&1; then
        log "✓ API Status: ONLINE"
        log "  URL: http://localhost:${HOST_PORT:-8000}"
        log "  Health: http://localhost:${HOST_PORT:-8000}/health"
        log "  Docs: http://localhost:${HOST_PORT:-8000}/docs"
    else
        warn "⚠ API Status: OFFLINE"
    fi
}

# Menu interativo
interactive_menu() {
    while true; do
        echo ""
        echo "🤖 Qwen3-Embedding Deploy Menu"
        echo "=" * 40
        echo "1. Construir imagem"
        echo "2. Iniciar serviços"
        echo "3. Parar serviços"
        echo "4. Reiniciar serviços"
        echo "5. Mostrar status"
        echo "6. Ver logs"
        echo "7. Executar testes"
        echo "8. Limpar tudo"
        echo "9. Sair"
        
        read -p "Escolha uma opção (1-9): " choice
        
        case $choice in
            1) build_image ;;
            2) start_services ;;
            3) stop_services ;;
            4) restart_services ;;
            5) show_status ;;
            6) 
                echo "Seguir logs em tempo real? (y/N): "
                read -n 1 follow
                echo
                if [[ $follow =~ ^[Yy]$ ]]; then
                    show_logs --follow
                else
                    show_logs
                fi
                ;;
            7) run_tests ;;
            8) 
                echo "Tem certeza que deseja limpar tudo? (y/N): "
                read -n 1 confirm
                echo
                if [[ $confirm =~ ^[Yy]$ ]]; then
                    clean_all
                fi
                ;;
            9) 
                log "Saindo..."
                exit 0
                ;;
            *) error "Opção inválida!" ;;
        esac
    done
}

# Função principal
main() {
    # Verificar dependências
    check_dependencies
    check_docker
    
    # Processar argumentos
    case "${1:-}" in
        --build)
            build_image
            ;;
        --start)
            start_services
            ;;
        --stop)
            stop_services
            ;;
        --restart)
            restart_services
            ;;
        --logs)
            show_logs "${2:-}"
            ;;
        --test)
            run_tests
            ;;
        --clean)
            clean_all
            ;;
        --status)
            show_status
            ;;
        --help)
            show_help
            exit 0
            ;;
        "")
            # Menu interativo se nenhum argumento
            interactive_menu
            ;;
        *)
            error "Opção inválida: $1"
            show_help
            exit 1
            ;;
    esac
}

# Executar função principal
main "$@" 