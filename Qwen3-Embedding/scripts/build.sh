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

# Configurações padrão
IMAGE_NAME=${IMAGE_NAME:-"qwen3-embedding"}
IMAGE_TAG=${IMAGE_TAG:-"latest"}
REGISTRY=${REGISTRY:-""}
DOCKERFILE=${DOCKERFILE:-"Dockerfile"}

# Adicionar registry se especificado
if [ -n "$REGISTRY" ]; then
    FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
else
    FULL_IMAGE_NAME="$IMAGE_NAME:$IMAGE_TAG"
fi

log "==============================================="
log "    Qwen3-Embedding Docker Build Script"
log "==============================================="
log "Imagem: $FULL_IMAGE_NAME"
log "Dockerfile: $DOCKERFILE"
log "Contexto: $(pwd)"

# Verificar se Docker está instalado
if ! command -v docker &> /dev/null; then
    error "Docker não está instalado!"
    exit 1
fi

# Verificar se Docker está rodando
if ! docker info &> /dev/null; then
    error "Docker não está rodando!"
    exit 1
fi

# Verificar se Dockerfile existe
if [ ! -f "$DOCKERFILE" ]; then
    error "Dockerfile não encontrado: $DOCKERFILE"
    exit 1
fi

# Limpar containers e imagens antigas se solicitado
if [ "$1" = "--clean" ]; then
    log "Limpando containers e imagens antigas..."
    
    # Parar containers relacionados
    if docker ps -a --format "table {{.Names}}" | grep -q "qwen3-embedding"; then
        docker stop $(docker ps -a --format "table {{.Names}}" | grep "qwen3-embedding" | tail -n +2) || true
        docker rm $(docker ps -a --format "table {{.Names}}" | grep "qwen3-embedding" | tail -n +2) || true
    fi
    
    # Remover imagens antigas
    if docker images | grep -q "$IMAGE_NAME"; then
        docker rmi $(docker images | grep "$IMAGE_NAME" | awk '{print $3}') || true
    fi
    
    # Limpar cache do Docker
    docker builder prune -f || true
fi

# Mostrar informações do sistema
log "Informações do sistema:"
log "Docker version: $(docker --version)"
log "Espaço disponível: $(df -h . | tail -1 | awk '{print $4}')"

# Verificar se há GPU disponível
if command -v nvidia-smi &> /dev/null; then
    log "GPU detectada:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
fi

# Build da imagem
log "Iniciando build da imagem Docker..."
log "Este processo pode levar vários minutos..."

BUILD_START=$(date +%s)

# Argumentos de build
BUILD_ARGS=()
if [ -n "$MODEL_NAME" ]; then
    BUILD_ARGS+=("--build-arg" "MODEL_NAME=$MODEL_NAME")
fi

# Executar build
if docker build \
    -t "$FULL_IMAGE_NAME" \
    -f "$DOCKERFILE" \
    "${BUILD_ARGS[@]}" \
    . ; then
    
    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))
    
    log "Build concluído com sucesso!"
    log "Tempo de build: ${BUILD_TIME}s"
    log "Imagem: $FULL_IMAGE_NAME"
    
    # Mostrar informações da imagem
    log "Informações da imagem:"
    docker images "$FULL_IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    
    # Verificar se a imagem foi criada corretamente
    if docker inspect "$FULL_IMAGE_NAME" &> /dev/null; then
        log "Imagem validada com sucesso!"
        
        # Executar testes básicos se solicitado
        if [ "$2" = "--test" ]; then
            log "Executando testes básicos..."
            ./scripts/test.sh
        fi
        
        # Oferecer push se registry está configurado
        if [ -n "$REGISTRY" ]; then
            echo
            read -p "Deseja fazer push da imagem para o registry? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                ./scripts/push.sh
            fi
        fi
        
    else
        error "Falha na validação da imagem!"
        exit 1
    fi
    
else
    error "Falha no build da imagem!"
    exit 1
fi

log "Script de build concluído!"
log "Para executar o container, use:"
log "  docker-compose up -d"
log "ou"
log "  docker run -d -p 8000:8000 --gpus all $FULL_IMAGE_NAME" 