# Qwen3-Embedding Docker Deploy

Deploy completo do modelo Qwen3-Embedding com API compatível OpenAI usando vLLM e Docker.

## 🚀 Características

- ✅ **API compatível com OpenAI** - Use com qualquer cliente OpenAI
- ✅ **Suporte a dimensões customizadas** - MRL (Matryoshka Representation Learning)
- ✅ **Múltiplos modelos** - 0.6B, 4B e 8B parâmetros
- ✅ **Deploy assistido** - Scripts automatizados para facilitar o uso
- ✅ **Monitoramento** - Health checks e métricas
- ✅ **Testes automáticos** - Validação completa da API
- ✅ **Multi-GPU** - Suporte a paralelização tensor

## 📋 Pré-requisitos

- Docker >= 20.10
- Docker Compose >= 1.28
- NVIDIA GPU (recomendado)
- NVIDIA Container Toolkit (para GPU)
- 8GB+ RAM disponível para Docker
- 10GB+ espaço em disco

## ⚡ Início Rápido

### 1. Configuração Inicial

```bash
# Clone ou baixe este projeto
cd Qwen3-Embedding

# Copie o arquivo de configuração
cp .env.example .env

# Edite as configurações se necessário
nano .env
```

### 2. Deploy Automático

```bash
# Deploy completo com um comando
./scripts/deploy.sh --build --start --test

# Ou use o menu interativo
./scripts/deploy.sh
```

### 3. Teste Rápido

```bash
# Testar a API
curl -X POST http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-Embedding-0.6B",
    "input": ["Olá mundo!"],
    "dimensions": 512
  }'
```

## 🔧 Configuração

### Variáveis de Ambiente (.env)

```bash
# Modelo principal (opções: 0.6B, 4B, 8B)
MODEL_NAME=Qwen/Qwen3-Embedding-0.6B

# Configurações de rede
HOST_PORT=8000

# Configurações de GPU
GPU_MEMORY_UTIL=0.9
TENSOR_PARALLEL_SIZE=1

# Token do Hugging Face (opcional)
HUGGING_FACE_HUB_TOKEN=your_token_here
```

### Modelos Disponíveis

| Modelo | Tamanho | Dimensões Max | Memória GPU | Uso Recomendado |
|--------|---------|---------------|-------------|-----------------|
| Qwen3-Embedding-0.6B | 0.6B | 1024 | ~2GB | Desenvolvimento, testes |
| Qwen3-Embedding-4B | 4B | 2560 | ~8GB | Produção balanceada |
| Qwen3-Embedding-8B | 8B | 4096 | ~16GB | Máxima qualidade |

## 🚦 Comandos Principais

### Scripts de Deploy

```bash
# Deploy completo
./scripts/deploy.sh --build --start

# Construir imagem
./scripts/build.sh

# Iniciar serviços
./scripts/deploy.sh --start

# Parar serviços
./scripts/deploy.sh --stop

# Ver logs
./scripts/deploy.sh --logs

# Executar testes
./scripts/test.sh

# Status dos serviços
./scripts/deploy.sh --status
```

### Docker Compose

```bash
# Iniciar em background
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar serviços
docker-compose down

# Reconstruir e iniciar
docker-compose up -d --build
```

## 📊 Uso da API

### Cliente Python

```python
import openai

# Configurar cliente
client = openai.OpenAI(
    api_key="EMPTY",
    base_url="http://localhost:8000/v1"
)

# Gerar embedding
response = client.embeddings.create(
    model="Qwen/Qwen3-Embedding-0.6B",
    input=["Seu texto aqui"],
    dimensions=512  # Opcional: customizar dimensões
)

print(response.data[0].embedding)
```

### Cliente Curl

```bash
# Embedding básico
curl -X POST http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-Embedding-0.6B",
    "input": ["Texto para embedding"]
  }'

# Múltiplos textos com dimensões customizadas
curl -X POST http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-Embedding-0.6B",
    "input": ["Texto 1", "Texto 2", "Texto 3"],
    "dimensions": 768
  }'
```

### Cliente de Exemplo

```bash
# Usar o cliente Python incluído
python examples/client.py --help

# Gerar embedding
python examples/client.py --text "Seu texto aqui"

# Demo de busca semântica
python examples/client.py --demo

# Benchmark de dimensões
python examples/client.py --benchmark
```

## 🔍 Testes e Validação

### Testes Automáticos

```bash
# Executar todos os testes
./scripts/test.sh

# Aguardar serviço e testar
./scripts/test.sh --wait

# Testes incluem:
# - Health check
# - Listagem de modelos
# - Embedding básico
# - Embedding em lote
# - Dimensões customizadas
# - Performance
```

### Monitoramento

```bash
# Status dos serviços
./scripts/deploy.sh --status

# Logs em tempo real
./scripts/deploy.sh --logs --follow

# Métricas do container
docker stats qwen3-embedding-server
```

## 📁 Estrutura do Projeto

```
Qwen3-Embedding/
├── Dockerfile                 # Imagem Docker
├── docker-compose.yml         # Orquestração
├── start.sh                   # Script de inicialização
├── .env.example              # Configurações de exemplo
├── README.md                 # Este arquivo
├── scripts/
│   ├── build.sh              # Build da imagem
│   ├── deploy.sh             # Deploy completo
│   └── test.sh               # Testes automáticos
├── examples/
│   └── client.py             # Cliente Python de exemplo
├── config/                   # Configurações opcionais
├── logs/                     # Logs do serviço
└── models/                   # Cache de modelos
```

## 🔧 Configurações Avançadas

### Multi-GPU

```bash
# No .env, configure:
TENSOR_PARALLEL_SIZE=2  # Para 2 GPUs
GPU_COUNT=2

# Ou diretamente no docker-compose:
docker-compose up -d --scale qwen3-embedding=1
```

### Modelos Quantizados

```bash
# Usar modelo quantizado AWQ
MODEL_NAME=Qwen/Qwen3-Embedding-0.6B-AWQ
QUANTIZATION=awq
```

### Configurações de Performance

```bash
# Otimizar para throughput
ENABLE_PREFIX_CACHING=true
ENABLE_CHUNKED_PREFILL=true
GPU_MEMORY_UTIL=0.95

# Otimizar para latência
ENABLE_PREFIX_CACHING=false
DISABLE_LOG_REQUESTS=true
```

## 🐛 Solução de Problemas

### Problemas Comuns

**1. Erro: "CUDA out of memory"**
```bash
# Reduza a utilização de GPU
GPU_MEMORY_UTIL=0.7

# Ou use modelo menor
MODEL_NAME=Qwen/Qwen3-Embedding-0.6B
```

**2. API não responde**
```bash
# Verifique os logs
./scripts/deploy.sh --logs

# Reinicie os serviços
./scripts/deploy.sh --restart
```

**3. Modelo não baixa**
```bash
# Configure token do Hugging Face
HUGGING_FACE_HUB_TOKEN=your_token

# Ou use ModelScope
VLLM_USE_MODELSCOPE=true
```

### Debug Avançado

```bash
# Executar container em modo debug
docker run -it --rm --gpus all \
  -p 8000:8000 \
  qwen3-embedding:latest \
  bash

# Verificar GPU no container
nvidia-smi

# Testar modelo manualmente
python -c "from vllm import LLM; print('OK')"
```

## 📚 Documentação Adicional

- [Documentação vLLM](https://docs.vllm.ai/)
- [Qwen3-Embedding Hugging Face](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference/embeddings)

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para detalhes.

## 💡 Suporte

- **Issues**: Abra uma issue no GitHub
- **Discussões**: Use GitHub Discussions
- **Chat**: Discord ou Telegram da comunidade

---

**Desenvolvido com ❤️ para facilitar o uso de embeddings avançados** 