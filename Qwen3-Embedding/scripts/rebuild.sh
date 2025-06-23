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

cd "$(dirname "$0")/.."

log "🔄 Fazendo rebuild rápido do Qwen3-Embedding..."

# Parar containers existentes
log "🛑 Parando containers existentes..."
docker-compose down || true

# Remover imagem antiga
log "🗑️  Removendo imagem antiga..."
docker rmi qwen3-embedding:latest || true

# Rebuild sem cache
log "🔨 Fazendo rebuild sem cache..."
docker-compose build --no-cache

# Verificar se build foi bem-sucedido
if [ $? -eq 0 ]; then
    log "✅ Build concluído com sucesso!"
    
    # Perguntar se quer iniciar
    echo -e "${BLUE}Deseja iniciar o container agora? (y/n): ${NC}"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log "🚀 Iniciando container..."
        docker-compose up -d
        
        log "📊 Status dos containers:"
        docker-compose ps
        
        log "📝 Para ver os logs em tempo real:"
        echo "docker-compose logs -f qwen3-embedding"
        
        log "🧪 Para testar a API:"
        echo "./scripts/test.sh"
    fi
else
    error "❌ Falha no build!"
    exit 1
fi 