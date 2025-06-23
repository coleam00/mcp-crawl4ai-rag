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

# Configurações
API_BASE_URL=${API_BASE_URL:-"http://localhost:8000"}
TIMEOUT=${TIMEOUT:-300}
MODEL_NAME=${MODEL_NAME:-"Qwen/Qwen3-Embedding-0.6B"}

log "==============================================="
log "    Qwen3-Embedding API Test Script"
log "==============================================="
log "API Base URL: $API_BASE_URL"
log "Timeout: ${TIMEOUT}s"
log "Modelo: $MODEL_NAME"

# Verificar se curl está instalado
if ! command -v curl &> /dev/null; then
    error "curl não está instalado!"
    exit 1
fi

# Função para aguardar o serviço estar pronto
wait_for_service() {
    log "Aguardando serviço estar pronto..."
    local max_attempts=$((TIMEOUT / 5))
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$API_BASE_URL/health" > /dev/null 2>&1; then
            log "Serviço está pronto!"
            return 0
        fi
        
        log "Tentativa $attempt/$max_attempts - Aguardando 5s..."
        sleep 5
        ((attempt++))
    done
    
    error "Timeout aguardando serviço ficar pronto!"
    return 1
}

# Teste de health check
test_health() {
    log "Testando health check..."
    
    if response=$(curl -s -f "$API_BASE_URL/health" 2>&1); then
        log "✓ Health check OK"
        return 0
    else
        error "✗ Health check falhou: $response"
        return 1
    fi
}

# Teste de modelos disponíveis
test_models() {
    log "Testando listagem de modelos..."
    
    if response=$(curl -s -f "$API_BASE_URL/v1/models" 2>&1); then
        log "✓ Modelos listados com sucesso"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        return 0
    else
        error "✗ Falha ao listar modelos: $response"
        return 1
    fi
}

# Teste básico de embedding
test_basic_embedding() {
    log "Testando embedding básico..."
    
    local test_text="Este é um teste básico de embedding."
    
    local payload=$(cat <<EOF
{
    "model": "$MODEL_NAME",
    "input": ["$test_text"],
    "encoding_format": "float"
}
EOF
)
    
    if response=$(curl -s -f \
        -X POST "$API_BASE_URL/v1/embeddings" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>&1); then
        
        log "✓ Embedding básico OK"
        
        # Verificar se a resposta contém dados válidos
        if echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    embeddings = data['data'][0]['embedding']
    print(f'Dimensões: {len(embeddings)}')
    print(f'Primeiros 5 valores: {embeddings[:5]}')
    assert len(embeddings) > 0, 'Embedding vazio'
    assert isinstance(embeddings[0], (int, float)), 'Valores inválidos'
    print('Embedding válido!')
except Exception as e:
    print(f'Erro: {e}')
    sys.exit(1)
" 2>&1; then
            log "✓ Embedding validado com sucesso"
            return 0
        else
            error "✗ Embedding inválido"
            return 1
        fi
    else
        error "✗ Falha no embedding básico: $response"
        return 1
    fi
}

# Teste de múltiplos textos
test_batch_embedding() {
    log "Testando embedding em lote..."
    
    local payload=$(cat <<EOF
{
    "model": "$MODEL_NAME",
    "input": [
        "Primeiro texto para embedding",
        "Segundo texto para processamento",
        "Terceiro exemplo de entrada"
    ],
    "encoding_format": "float"
}
EOF
)
    
    if response=$(curl -s -f \
        -X POST "$API_BASE_URL/v1/embeddings" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>&1); then
        
        log "✓ Embedding em lote OK"
        
        # Verificar se retornou 3 embeddings
        if echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    assert len(data['data']) == 3, f'Esperado 3 embeddings, recebido {len(data[\"data\"])}'
    for i, item in enumerate(data['data']):
        assert len(item['embedding']) > 0, f'Embedding {i} vazio'
    print('Batch embedding válido!')
except Exception as e:
    print(f'Erro: {e}')
    sys.exit(1)
" 2>&1; then
            log "✓ Batch embedding validado com sucesso"
            return 0
        else
            error "✗ Batch embedding inválido"
            return 1
        fi
    else
        error "✗ Falha no batch embedding: $response"
        return 1
    fi
}

# Teste de dimensões customizadas
test_custom_dimensions() {
    log "Testando dimensões customizadas..."
    
    local test_dimensions=(128 256 512 768)
    
    for dim in "${test_dimensions[@]}"; do
        log "Testando dimensão: $dim"
        
        local payload=$(cat <<EOF
{
    "model": "$MODEL_NAME",
    "input": ["Teste de dimensão $dim"],
    "dimensions": $dim,
    "encoding_format": "float"
}
EOF
)
        
        if response=$(curl -s -f \
            -X POST "$API_BASE_URL/v1/embeddings" \
            -H "Content-Type: application/json" \
            -d "$payload" 2>&1); then
            
            # Verificar se a dimensão está correta
            if echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    embedding = data['data'][0]['embedding']
    actual_dim = len(embedding)
    expected_dim = $dim
    assert actual_dim == expected_dim, f'Esperado {expected_dim}, recebido {actual_dim}'
    print(f'Dimensão {expected_dim} OK')
except Exception as e:
    print(f'Erro: {e}')
    sys.exit(1)
" 2>&1; then
                log "✓ Dimensão $dim validada"
            else
                error "✗ Dimensão $dim inválida"
                return 1
            fi
        else
            error "✗ Falha ao testar dimensão $dim: $response"
            return 1
        fi
    done
    
    log "✓ Todas as dimensões testadas com sucesso"
    return 0
}

# Teste de performance
test_performance() {
    log "Testando performance..."
    
    local payload=$(cat <<EOF
{
    "model": "$MODEL_NAME",
    "input": ["Teste de performance para medir latência da API"],
    "encoding_format": "float"
}
EOF
)
    
    local total_time=0
    local num_requests=5
    
    for i in $(seq 1 $num_requests); do
        local start_time=$(date +%s.%N)
        
        if curl -s -f \
            -X POST "$API_BASE_URL/v1/embeddings" \
            -H "Content-Type: application/json" \
            -d "$payload" > /dev/null 2>&1; then
            
            local end_time=$(date +%s.%N)
            local request_time=$(echo "$end_time - $start_time" | bc -l)
            total_time=$(echo "$total_time + $request_time" | bc -l)
            
            log "Request $i: ${request_time}s"
        else
            error "✗ Request $i falhou"
            return 1
        fi
    done
    
    local avg_time=$(echo "scale=3; $total_time / $num_requests" | bc -l)
    log "✓ Performance OK - Tempo médio: ${avg_time}s"
    
    return 0
}

# Executar todos os testes
run_all_tests() {
    local failed_tests=0
    
    # Aguardar serviço
    if ! wait_for_service; then
        exit 1
    fi
    
    # Executar testes
    test_health || ((failed_tests++))
    test_models || ((failed_tests++))
    test_basic_embedding || ((failed_tests++))
    test_batch_embedding || ((failed_tests++))
    test_custom_dimensions || ((failed_tests++))
    
    # Teste de performance (opcional)
    if command -v bc &> /dev/null; then
        test_performance || ((failed_tests++))
    else
        warn "bc não instalado, pulando teste de performance"
    fi
    
    # Resultado final
    log "==============================================="
    if [ $failed_tests -eq 0 ]; then
        log "✓ Todos os testes passaram!"
        log "API está funcionando corretamente"
        return 0
    else
        error "✗ $failed_tests teste(s) falharam"
        return 1
    fi
}

# Executar testes
if [ "$1" = "--wait" ]; then
    run_all_tests
else
    # Executar apenas se o serviço já estiver rodando
    if curl -s -f "$API_BASE_URL/health" > /dev/null 2>&1; then
        run_all_tests
    else
        error "Serviço não está rodando. Use --wait para aguardar ou inicie o serviço primeiro."
        exit 1
    fi
fi 