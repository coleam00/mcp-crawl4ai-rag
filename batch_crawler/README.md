# Batch Crawler para MCP Crawl4AI RAG

Este diretório contém um script para processar múltiplas URLs sequencialmente usando o servidor MCP Crawl4AI RAG.

## Arquivos

### Scripts Principais
- `batch_crawler_working.py` - **Script que FUNCIONA** (usa stdio)
- `batch_crawler.py` - Script original (limitado por FastMCP SSE)
- `batch_crawler_mcp.py` - Versão usando biblioteca MCP (demonstração)

### Utilitários  
- `requirements.txt` - Dependências Python específicas do script
- `example_urls.txt` - Arquivo de exemplo com URLs para teste
- `test_mcp_connection.py` - Script para diagnosticar comunicação MCP
- `test_encoding.bat` - Script para testar codificação de caracteres

### Scripts Windows
- `setup.bat` - Script de setup automático (Windows)
- `start.bat` - Script para execução em modo interativo (Windows) 
- `cleanup.bat` - Script para limpeza de ambientes virtuais (Windows)

### Documentação
- `README.md` - Este arquivo

## ⚠️ Qual Script Usar?

**Para USO REAL: `batch_crawler_working.py`**
- ✅ Funciona de verdade com o servidor MCP
- ✅ Usa comunicação stdio (não SSE problemático)  
- ✅ Resultados reais de crawling
- ✅ Totalmente funcional

**Para TESTE/DEBUG: `test_mcp_connection.py`**
- Diagnostica problemas de conexão
- Identifica endpoints disponíveis

**NÃO usar: `batch_crawler.py`**  
- Limitado por problemas do FastMCP SSE
- Endpoints HTTP não funcionais

## Instalação

### Opção 1: Setup Automático (Windows)

1. Execute o setup automático:
```batch
setup.bat
```

Este script irá:
- Verificar se `uv` está instalado
- Criar ambiente virtual com `uv venv .venv`
- Instalar dependências automaticamente
- Verificar se tudo está funcionando

### Opção 2: Manual

1. Crie um ambiente virtual:
```bash
uv venv .venv
# ou: python -m venv .venv
```

2. Ative o ambiente virtual:
```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Uso

### Pré-requisitos

1. **O servidor MCP deve estar rodando** (padrão: `http://localhost:8051`)
   
   Para iniciar o servidor, no diretório principal execute:
   ```bash
   # Opção 1: Com uv (recomendado)
   uv run src/crawl4ai_mcp.py
   
   # Opção 2: Com Python tradicional
   python src/crawl4ai_mcp.py
   ```

2. **Configure o servidor** conforme documentação no diretório principal
   - Certifique-se de ter o arquivo `.env` configurado
   - Verifique se as dependências do servidor estão instaladas

### Executar o script

#### Opção 1: Modo Interativo (Windows - Recomendado)

```batch
# Modo interativo - interface amigável
start.bat

# Modo direto com argumentos
start.bat example_urls.txt
start.bat meu_arquivo.txt --output resultados.json --delay 2
```

O modo interativo oferece:
- ✅ Menu de seleção de arquivos
- ✅ Configuração assistida de opções
- ✅ Verificação automática do servidor MCP
- ✅ Validação de arquivos
- ✅ Opção de abrir resultados automaticamente

#### Opção 2: Linha de Comando (RECOMENDADO)

```bash
# Ativar ambiente virtual primeiro
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Uso básico com script que FUNCIONA
python batch_crawler_working.py example_urls.txt

# Com opções personalizadas
python batch_crawler_working.py meu_arquivo.txt --output resultados.json --delay 2

# Se servidor MCP estiver em local diferente
python batch_crawler_working.py urls.txt --server-script "../../src/crawl4ai_mcp.py"

# Ver todas as opções
python batch_crawler_working.py --help
```

#### Opção 3: Teste/Diagnóstico

```bash
# Testar comunicação com servidor
python test_mcp_connection.py

# Teste de codificação (Windows)
test_encoding.bat
```

## Opções Disponíveis

- `urls_file` - Arquivo texto com URLs (uma por linha, obrigatório)
- `--output, -o` - Arquivo de saída JSON (padrão: crawl_results.json)
- `--delay, -d` - Delay em segundos entre requisições (padrão: 1.0)
- `--server-url, -s` - URL do servidor MCP (padrão: http://localhost:8051)

## Formato do Arquivo de URLs

```
# Comentários começam com #
https://example.com/page1
https://example.com/page2
https://another-site.com/docs

# URLs inválidas são automaticamente ignoradas
```

## Saída

O script gera:

1. **Arquivo JSON** com resultados detalhados:
   - Resumo estatístico
   - Resultado individual de cada URL
   - Timestamps e tempos de processamento

2. **Log file** com timestamp da execução:
   - Progresso em tempo real
   - Erros detalhados
   - Estatísticas de performance

## Funcionalidades

- ✅ **Processamento sequencial** - Uma URL por vez
- ✅ **Validação de URLs** - URLs inválidas são ignoradas
- ✅ **Retry automático** - Tratamento robusto de erros
- ✅ **Logging detalhado** - Logs no console e arquivo
- ✅ **Progresso visual** - Contador "X de Y URLs"
- ✅ **Configurável** - Delay, server URL, arquivo de saída
- ✅ **Teste de conexão** - Verifica servidor antes de iniciar

## Exemplo de Saída JSON

```json
{
  "summary": {
    "total_urls": 5,
    "successful": 4,
    "failed": 1,
    "total_processing_time": 45.2,
    "generated_at": "2025-01-21T10:30:00"
  },
  "results": [
    {
      "url": "https://example.com",
      "success": true,
      "processing_time": 8.5,
      "timestamp": "2025-01-21T10:30:01",
      "data": {
        "success": true,
        "chunks_stored": 12,
        "content_length": 5420,
        "source_id": "example.com"
      }
    }
  ]
}
```

## Solução de Problemas

### Erro de Conexão com Servidor MCP

**Erro comum:** `Nao foi possivel conectar ao servidor MCP`

**Soluções:**

1. **Verifique se o servidor está rodando:**
   ```bash
   # No diretório principal do projeto
   uv run src/crawl4ai_mcp.py
   ```
   Você deve ver algo como: `Starting server on http://localhost:8051`

2. **Verifique a porta:**
   - Padrão: `http://localhost:8051`
   - Se usar porta diferente, ajuste com `--server-url`

3. **Teste a conexão manualmente:**
   ```bash
   # Teste se o servidor responde (404 é normal)
   curl http://localhost:8051
   # ou
   python -c "import httpx; print(httpx.get('http://localhost:8051'))"
   ```
   **Nota:** Se receber "404 Not Found", está correto! Isso significa que o servidor está rodando.

4. **Verifique configuração do servidor:**
   - Arquivo `.env` deve estar configurado
   - Variáveis obrigatórias: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, etc.

5. **Logs do servidor:**
   - Verifique mensagens de erro no terminal onde rodou o servidor
   - Problemas comuns: chaves API inválidas, banco não configurado

6. **Use o script de teste:**
   ```bash
   # Ativar ambiente virtual primeiro
   .venv\Scripts\activate
   
   # Executar teste de comunicação
   python test_mcp_connection.py
   ```
   Este script testa:
   - Conexão básica com o servidor
   - Listagem de ferramentas MCP
   - Execução da ferramenta `crawl_single_page`

### Erro de Permissão no Setup (Windows)
Se receber "Acesso negado" ao criar ambiente virtual:

1. **Execute cleanup.bat primeiro:**
   ```batch
   cleanup.bat
   ```

2. **Execute setup como Administrador:**
   - Clique direito em `setup.bat` → "Executar como administrador"

3. **Feche IDEs/editores** que possam estar usando arquivos da pasta

4. **Alternativa manual:**
   ```batch
   # Remover pasta manualmente
   rmdir /s /q .venv
   
   # Tentar novamente
   setup.bat
   ```

### URLs não processadas
- Verifique formato das URLs no arquivo
- URLs devem começar com http:// ou https://
- Linhas vazias e comentários (#) são ignorados

### Performance
- Ajuste o delay entre requisições conforme necessário
- Monitor logs para identificar URLs problemáticas
- Verifique recursos do servidor MCP

## Scripts de Automação (Windows)

### setup.bat
Script para configuração inicial automática:

- ✅ Verifica se `uv` está instalado
- ✅ Cria ambiente virtual com `uv venv .venv`
- ✅ Instala dependências do `requirements.txt`
- ✅ Valida que tudo está funcionando
- ✅ Exibe instruções de uso

**Uso:** Duplo clique ou execute `setup.bat` no terminal

### start.bat
Script para execução com interface interativa:

**Modo Interativo:**
- ✅ Menu de seleção de arquivos .txt
- ✅ Configuração assistida de parâmetros
- ✅ Verificação automática do servidor MCP
- ✅ Validação de arquivos de entrada
- ✅ Opção para abrir resultados automaticamente
- ✅ Possibilidade de processar múltiplos arquivos

**Modo Direto:**
```batch
start.bat arquivo.txt --output resultado.json --delay 2
```

**Fluxo do Modo Interativo:**
1. Lista arquivos .txt disponíveis
2. Permite seleção por número ou caminho manual
3. Solicita configurações opcionais (arquivo saída, delay, servidor)
4. Confirma configuração antes de executar
5. Executa o crawling com progresso em tempo real
6. Oferece abrir resultados e processar novo arquivo