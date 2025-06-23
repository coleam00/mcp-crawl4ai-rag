#!/bin/bash

set -e

# Cores para logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para log colorido
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Configurações padrão
MODEL_NAME=${MODEL_NAME:-"Qwen/Qwen3-Embedding-0.6B"}
TASK=${TASK:-"embed"}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-8192}
GPU_MEMORY_UTIL=${GPU_MEMORY_UTIL:-0.9}
TENSOR_PARALLEL_SIZE=${TENSOR_PARALLEL_SIZE:-1}
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-8000}
LOG_LEVEL=${LOG_LEVEL:-"INFO"}
DISABLE_LOG_REQUESTS=${DISABLE_LOG_REQUESTS:-false}
ENABLE_PREFIX_CACHING=${ENABLE_PREFIX_CACHING:-true}
ENABLE_CHUNKED_PREFILL=${ENABLE_CHUNKED_PREFILL:-true}

log "🚀 Iniciando Qwen3-Embedding Server..."
log "📦 Modelo: $MODEL_NAME"
log "🎯 Tarefa: $TASK"
log "📏 Max Model Length: $MAX_MODEL_LEN"
log "🎮 GPU Memory Utilization: $GPU_MEMORY_UTIL"
log "🔧 Tensor Parallel Size: $TENSOR_PARALLEL_SIZE"

# Verificar se GPU está disponível
if command -v nvidia-smi &> /dev/null; then
    log "🎮 GPU detectada:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits
else
    warn "⚠️  GPU não detectada, usando CPU"
fi

# Criar diretórios necessários
mkdir -p /app/logs /app/models

# Verificar espaço em disco
log "💾 Verificando espaço em disco..."
df -h /app/models

# Construir argumentos do vLLM
VLLM_ARGS=(
    "--model" "$MODEL_NAME"
    "--task" "$TASK"
    "--max-model-len" "$MAX_MODEL_LEN"
    "--gpu-memory-utilization" "$GPU_MEMORY_UTIL"
    "--tensor-parallel-size" "$TENSOR_PARALLEL_SIZE"
    "--host" "$HOST"
    "--port" "$PORT"
    "--trust-remote-code"
)

# Adicionar argumentos opcionais
if [ "$LOG_LEVEL" != "INFO" ]; then
    VLLM_ARGS+=("--uvicorn-log-level" "$(echo $LOG_LEVEL | tr '[:upper:]' '[:lower:]')")
fi

if [ "$DISABLE_LOG_REQUESTS" = "true" ]; then
    VLLM_ARGS+=("--disable-log-requests")
fi

if [ "$ENABLE_PREFIX_CACHING" = "true" ]; then
    VLLM_ARGS+=("--enable-prefix-caching")
fi

if [ "$ENABLE_CHUNKED_PREFILL" = "true" ]; then
    VLLM_ARGS+=("--enable-chunked-prefill")
fi

# Adicionar argumentos de quantização se especificado
if [ -n "$QUANTIZATION" ]; then
    VLLM_ARGS+=("--quantization" "$QUANTIZATION")
fi

# Adicionar HF Token se especificado
if [ -n "$HUGGING_FACE_HUB_TOKEN" ] && [ "$HUGGING_FACE_HUB_TOKEN" != "your_hf_token_here" ]; then
    VLLM_ARGS+=("--hf-token" "$HUGGING_FACE_HUB_TOKEN")
fi

# Configurar logging
LOG_FILE="/app/logs/vllm-$(date +%Y%m%d-%H%M%S).log"
log "📝 Logs serão salvos em: $LOG_FILE"

# Função para cleanup
cleanup() {
    log "🛑 Recebido sinal de parada, finalizando..."
    pkill -P $$ 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

log "🔥 Iniciando vLLM API Server..."
log "⚡ Comando: python -m vllm.entrypoints.openai.api_server ${VLLM_ARGS[*]}"

# Executar vLLM com logging
exec python -m vllm.entrypoints.openai.api_server "${VLLM_ARGS[@]}" 2>&1 | tee "$LOG_FILE" 