# Batch Crawler - Versões Funcionais

## 🎯 Problema Identificado

O FastMCP **NÃO** expõe endpoints REST como `/tools/crawl_single_page`. Ele usa o protocolo MCP via:
- **SSE** (Server-Sent Events) - para comunicação HTTP
- **stdio** - para comunicação via subprocess

## ✅ Soluções Funcionais

### Opção 1: MCP via stdio (RECOMENDADO)
**Arquivo:** `batch_crawler_working_fixed.py`

```bash
# Executar diretamente
python batch_crawler_working_fixed.py sitemap_urls.txt

# Ou usar script batch
run_working.bat sitemap_urls.txt results.json 1

# Modo interativo
python batch_crawler_working_fixed.py -i
```

**Características:**
- ✅ Usa o protocolo MCP correto (JSON-RPC 2.0 via stdio)
- ✅ Não precisa do Docker rodando
- ✅ Executa o servidor localmente via subprocess
- ❗ Precisa das dependências Python instaladas localmente

### Opção 2: HTTP Fallback (LIMITADO)
**Arquivo:** `batch_crawler_simple.py`

```bash
# Com Docker rodando
docker-compose up -d
python batch_crawler_simple.py sitemap_urls.txt

# Ou usar script batch
run_simple.bat sitemap_urls.txt
```

**Características:**
- ✅ Funciona com Docker
- ❌ Não consegue usar MCP (cai no fallback HTTP básico)
- ✅ Não precisa de dependências Python locais
- ⚠️ Coleta apenas conteúdo HTML básico (sem processamento RAG)

## 🔧 Qual Usar?

### Para uso com RAG completo (embeddings, chunks, etc.):
**Use `batch_crawler_working_fixed.py`**
- Instale as dependências: `pip install -r ../requirements.txt`
- Execute: `run_working.bat sitemap_urls.txt`

### Para teste rápido ou coleta básica:
**Use `batch_crawler_simple.py`**
- Mantenha Docker rodando: `docker-compose up -d`
- Execute: `run_simple.bat sitemap_urls.txt`

## 📋 Diagnóstico de Problemas

### Erro "ModuleNotFoundError: No module named 'mcp'"
```bash
# Instalar dependências localmente
cd ..
pip install -r requirements.txt
crawl4ai-setup
```

### Erro "Script do servidor não encontrado"
```bash
# Verificar estrutura de diretórios
ls ../src/crawl4ai_mcp.py  # Deve existir
```

### Erro "Timeout na comunicação"
- Aumentar timeout no código (padrão: 180s)
- Verificar URL válida
- Testar com URL única primeiro

## 🔍 Debug

Para debug detalhado, adicione logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📊 Exemplo de Resultado

```json
{
  "success": true,
  "url": "https://example.com",
  "data": {
    "url": "https://example.com",
    "title": "Page Title",
    "content": "...",
    "chunks": [...],
    "embeddings": [...],
    "summary": "..."
  },
  "processing_time": 5.23,
  "timestamp": "2025-06-21T...",
  "method": "stdio-mcp"
}
```