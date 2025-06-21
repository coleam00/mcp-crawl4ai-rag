#!/bin/bash

# Setup script for Ollama with Qwen3-Embedding models
# This script pulls the required embedding models and optionally chat models

set -e

echo "=== Ollama Qwen3-Embedding Setup Script ==="
echo "This script will pull the required Qwen3-Embedding models for the MCP server."
echo ""

# Check if Ollama is running
check_ollama() {
    echo "Checking if Ollama is running..."
    if curl -s -f http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama is running"
        return 0
    else
        echo "❌ Ollama is not running or not accessible"
        return 1
    fi
}

# Pull embedding models
pull_embedding_models() {
    echo ""
    echo "📥 Pulling Qwen3-Embedding models..."
    
    echo "Pulling Qwen3-Embedding-0.6B (efficient model)..."
    ollama pull dengcao/Qwen3-Embedding-0.6B
    
    echo "Pulling Qwen3-Embedding-8B (high-performance model)..."
    ollama pull dengcao/Qwen3-Embedding-8B
    
    echo "✅ Embedding models pulled successfully!"
}

# Pull chat models (optional)
pull_chat_models() {
    echo ""
    read -p "Do you want to pull Qwen3 chat models as well? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "📥 Pulling Qwen3 chat models..."
        ollama pull qwen3:latest
        echo "✅ Chat model pulled successfully!"
    else
        echo "⏭️  Skipping chat models"
    fi
}

# Show model information
show_model_info() {
    echo ""
    echo "📋 Available models:"
    ollama list
    
    echo ""
    echo "🎯 Recommended configurations:"
    echo ""
    echo "For development (efficient):"
    echo "  EMBEDDING_MODEL=dengcao/Qwen3-Embedding-0.6B"
    echo "  EMBEDDING_DIMENSIONS=1024"
    echo "  Memory requirement: ~2GB"
    echo ""
    echo "For production (high-performance):"
    echo "  EMBEDDING_MODEL=dengcao/Qwen3-Embedding-8B"
    echo "  EMBEDDING_DIMENSIONS=1024-4096"
    echo "  Memory requirement: ~8GB"
    echo ""
    echo "Update your .env file with these settings."
}

# Main execution
main() {
    if ! check_ollama; then
        echo ""
        echo "Please start Ollama first:"
        echo "  ollama serve"
        echo ""
        echo "Or if using Docker:"
        echo "  docker-compose up -d ollama"
        exit 1
    fi
    
    pull_embedding_models
    pull_chat_models
    show_model_info
    
    echo ""
    echo "🎉 Setup completed successfully!"
    echo "You can now start the MCP server with Qwen3-Embedding models."
}

# Run main function
main "$@"