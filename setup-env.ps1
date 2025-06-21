# =================================================================
#  Crawl4AI RAG MCP - Environment Setup Script
# =================================================================

param(
    [switch]$NoInteractive,
    [string]$ConfigFile = ".env"
)

$ErrorActionPreference = "Stop"

# Color functions for output
function Write-Success { param($Message) Write-Host $Message -ForegroundColor Green }
function Write-Info { param($Message) Write-Host $Message -ForegroundColor Cyan }
function Write-Warning { param($Message) Write-Host $Message -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host $Message -ForegroundColor Red }

# Function to prompt for input with default value
function Get-UserInput {
    param(
        [string]$Prompt,
        [string]$Default = "",
        [switch]$Required,
        [switch]$SecureInput
    )
    
    if ($NoInteractive -and $Default) {
        return $Default
    }
    
    do {
        if ($Default) {
            $displayPrompt = "$Prompt [$Default]"
        } else {
            $displayPrompt = $Prompt
        }
        
        if ($SecureInput) {
            $input = Read-Host -Prompt $displayPrompt -AsSecureString
            $input = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($input))
        } else {
            $input = Read-Host -Prompt $displayPrompt
        }
        
        if ([string]::IsNullOrWhiteSpace($input) -and $Default) {
            return $Default
        }
        
        if ([string]::IsNullOrWhiteSpace($input) -and $Required) {
            Write-Warning "This field is required. Please enter a value."
            continue
        }
        
        return $input
    } while ($Required -and [string]::IsNullOrWhiteSpace($input))
}

# Function to prompt for yes/no
function Get-YesNo {
    param([string]$Prompt, [bool]$Default = $false)
    
    $defaultText = if ($Default) { "Y/n" } else { "y/N" }
    $response = Get-UserInput -Prompt "$Prompt [$defaultText]" -Default $(if ($Default) { "y" } else { "n" })
    return $response.ToLower() -eq "y" -or $response.ToLower() -eq "yes"
}

Write-Info "==================================================================="
Write-Info "  Crawl4AI RAG MCP - Environment Configuration Setup"
Write-Info "==================================================================="
Write-Info ""

# Check if .env already exists
if (Test-Path $ConfigFile) {
    Write-Warning ".env file already exists."
    if (-not (Get-YesNo "Do you want to overwrite it?" $false)) {
        Write-Info "Setup cancelled."
        exit 0
    }
}

Write-Info "This script will help you configure your Crawl4AI RAG MCP environment."
Write-Info "Press Enter to use default values shown in brackets."
Write-Info ""

# =================================================================
# Server Configuration
# =================================================================
Write-Info "--- Server Configuration ---"
$host = Get-UserInput "Server host (use 0.0.0.0 for Docker, localhost otherwise)" "0.0.0.0"
$port = Get-UserInput "Server port" "8051"
$transport = Get-UserInput "Transport protocol (sse/stdio)" "sse"

# =================================================================
# Model Configuration
# =================================================================
Write-Info ""
Write-Info "--- Model Configuration ---"

# Chat Model
Write-Info "Chat Model (for summaries and contextual embeddings):"
$chatModel = Get-UserInput "  Model name" "gpt-4o-mini"
$chatModelApiKey = Get-UserInput "  API Key" -Required -SecureInput
$chatModelApiBase = Get-UserInput "  API Base URL (optional, e.g., http://localhost:11434/v1 for Ollama)"

# Embedding Model
Write-Info "Embedding Model:"
$embeddingModel = Get-UserInput "  Model name" "text-embedding-3-small"
$embeddingModelApiKey = Get-UserInput "  API Key (can be same as Chat Model)" -Required -SecureInput
$embeddingModelApiBase = Get-UserInput "  API Base URL (optional)"
$embeddingDimensions = Get-UserInput "  Embedding dimensions" "1536"

# =================================================================
# Database Configuration
# =================================================================
Write-Info ""
Write-Info "--- Database Configuration ---"

# Supabase
Write-Info "Supabase (Vector Database):"
$supabaseUrl = Get-UserInput "  Supabase URL" -Required
$supabaseServiceKey = Get-UserInput "  Supabase Service Key" -Required -SecureInput

# Neo4j (optional)
Write-Info "Neo4j (Knowledge Graph Database - optional):"
$useKnowledgeGraph = Get-YesNo "Enable knowledge graph features?" $false

$neo4jUri = ""
$neo4jUser = ""
$neo4jPassword = ""

if ($useKnowledgeGraph) {
    $neo4jUri = Get-UserInput "  Neo4j URI (use neo4j://host.docker.internal:7687 for Docker)" "bolt://localhost:7687"
    $neo4jUser = Get-UserInput "  Neo4j Username" "neo4j"
    $neo4jPassword = Get-UserInput "  Neo4j Password" -Required -SecureInput
}

# =================================================================
# RAG Strategy Configuration
# =================================================================
Write-Info ""
Write-Info "--- RAG Strategy Features ---"
Write-Info "Enable advanced RAG features (impacts performance vs accuracy):"

$useContextualEmbeddings = Get-YesNo "Use contextual embeddings (slower indexing, better accuracy)?" $false
$useHybridSearch = Get-YesNo "Use hybrid search (vector + keyword)?" $false
$useAgenticRag = Get-YesNo "Use agentic RAG (code extraction and specialized search)?" $false
$useReranking = Get-YesNo "Use result reranking (better relevance)?" $false

# =================================================================
# Advanced Parameters
# =================================================================
Write-Info ""
Write-Info "--- Advanced Configuration (optional) ---"
$configureAdvanced = Get-YesNo "Configure advanced parameters?" $false

$maxCrawlDepth = "3"
$maxConcurrentCrawls = "10"
$chunkSize = "5000"
$defaultMatchCount = "5"

if ($configureAdvanced) {
    $maxCrawlDepth = Get-UserInput "  Max crawl depth" "3"
    $maxConcurrentCrawls = Get-UserInput "  Max concurrent crawls" "10"
    $chunkSize = Get-UserInput "  Chunk size" "5000"
    $defaultMatchCount = Get-UserInput "  Default match count" "5"
}

# =================================================================
# Generate .env file
# =================================================================
Write-Info ""
Write-Info "Generating $ConfigFile file..."

$envContent = @"
# =================================================================
#  CORE CONFIGURATION
# =================================================================

# --- Server Settings ---
HOST=$host
PORT=$port
TRANSPORT=$transport

# --- Model Configuration ---
# Chat Model (for summaries, contextual embeddings, etc.)
CHAT_MODEL=$chatModel
CHAT_MODEL_API_KEY=$chatModelApiKey
CHAT_MODEL_API_BASE=$chatModelApiBase

# Embedding Model
EMBEDDING_MODEL="$embeddingModel"
EMBEDDING_MODEL_API_KEY=$embeddingModelApiKey
EMBEDDING_DIMENSIONS=$embeddingDimensions
EMBEDDING_MODEL_API_BASE=$embeddingModelApiBase

# --- RAG Strategy Flags ---
USE_CONTEXTUAL_EMBEDDINGS=$($useContextualEmbeddings.ToString().ToLower())
USE_HYBRID_SEARCH=$($useHybridSearch.ToString().ToLower())
USE_AGENTIC_RAG=$($useAgenticRag.ToString().ToLower())
USE_RERANKING=$($useReranking.ToString().ToLower())
USE_KNOWLEDGE_GRAPH=$($useKnowledgeGraph.ToString().ToLower())

# --- Database Configuration ---
# Vector Database (for RAG)
SUPABASE_URL=$supabaseUrl
SUPABASE_SERVICE_KEY=$supabaseServiceKey

# Knowledge Graph Database (for agentic features)
NEO4J_URI=$neo4jUri
NEO4J_USER=$neo4jUser
NEO4J_PASSWORD=$neo4jPassword

# --- Fine-Tuning Parameters ---
# Reranking model name from sentence-transformers
RERANKING_MODEL="cross-encoder/ms-marco-MiniLM-L-6-v2"

# Crawling parameters
MAX_CRAWL_DEPTH=$maxCrawlDepth
MAX_CONCURRENT_CRAWLS=$maxConcurrentCrawls
CHUNK_SIZE=$chunkSize

# Search parameters
DEFAULT_MATCH_COUNT=$defaultMatchCount

# Concurrency settings for background tasks
MAX_WORKERS_SUMMARY=10
MAX_WORKERS_CONTEXT=10
MAX_WORKERS_SOURCE_SUMMARY=5

# Content processing settings
MIN_CODE_BLOCK_LENGTH=1000
SUPABASE_BATCH_SIZE=20
"@

try {
    $envContent | Out-File -FilePath $ConfigFile -Encoding UTF8
    Write-Success "✓ $ConfigFile file created successfully!"
} catch {
    Write-Error "Failed to create $ConfigFile file: $_"
    exit 1
}

# =================================================================
# Summary and Next Steps
# =================================================================
Write-Info ""
Write-Success "==================================================================="
Write-Success "  Setup Complete!"
Write-Success "==================================================================="
Write-Info ""
Write-Info "Configuration saved to: $ConfigFile"
Write-Info ""
Write-Info "Enabled features:"
Write-Info "  • Contextual Embeddings: $($useContextualEmbeddings.ToString().ToLower())"
Write-Info "  • Hybrid Search: $($useHybridSearch.ToString().ToLower())"
Write-Info "  • Agentic RAG: $($useAgenticRag.ToString().ToLower())"
Write-Info "  • Reranking: $($useReranking.ToString().ToLower())"
Write-Info "  • Knowledge Graph: $($useKnowledgeGraph.ToString().ToLower())"
Write-Info ""
Write-Info "Next steps:"
Write-Info "  1. Review the generated .env file"
Write-Info "  2. Install dependencies: pip install -r requirements.txt"
if ($useKnowledgeGraph) {
    Write-Info "  3. Start Neo4j database (required for knowledge graph features)"
    Write-Info "  4. Run the MCP server: python -m src.crawl4ai_mcp"
} else {
    Write-Info "  3. Run the MCP server: python -m src.crawl4ai_mcp"
}
Write-Info ""
Write-Success "Happy crawling! 🕷️"