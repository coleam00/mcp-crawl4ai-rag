#!/usr/bin/env python3
"""
Test script para demonstrar o sistema de fallback completo.

Este script testa tanto o sistema de fallback para chat models quanto para embedding models.
"""

import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils import (
    get_chat_client_with_fallback,
    make_chat_completion_with_fallback,
    get_embedding_client_with_fallback,
    create_embeddings_with_fallback
)

def test_chat_completion_fallback():
    """
    Testa o novo sistema de fallback para chat completions.
    """
    print("🧪 Testando Sistema de Fallback para Chat Completions")
    print("=" * 55)
    
    # Set up test environment
    os.environ["USE_CHAT_MODEL_FALLBACK"] = "true"
    os.environ["CHAT_MODEL"] = "invalid-model"
    os.environ["CHAT_MODEL_API_KEY"] = "invalid-key"
    os.environ["CHAT_MODEL_API_BASE"] = "http://invalid-url:9999/v1"
    os.environ["CHAT_MODEL_FALLBACK"] = "gpt-3.5-turbo"
    os.environ["CHAT_MODEL_FALLBACK_API_KEY"] = "sk-test123"  # This will also fail, but demonstrates the system
    
    test_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello."}
    ]
    
    try:
        print("Tentando chat completion com fallback habilitado...")
        response = make_chat_completion_with_fallback(messages=test_messages)
        print("✅ Chat completion com fallback funcionou!")
        print(f"Resposta: {response.choices[0].message.content[:100]}...")
    except Exception as e:
        print(f"❌ Chat completion falhou (esperado com chaves inválidas): {str(e)[:150]}...")
    
    # Test with fallback disabled
    os.environ["USE_CHAT_MODEL_FALLBACK"] = "false"
    
    try:
        print("\nTentando chat completion com fallback desabilitado...")
        response = make_chat_completion_with_fallback(messages=test_messages)
        print("✅ Chat completion funcionou!")
    except Exception as e:
        print(f"❌ Chat completion falhou (esperado com fallback desabilitado): {str(e)[:150]}...")


def test_embedding_fallback():
    """
    Testa o novo sistema de fallback para embeddings.
    """
    print("\n🧪 Testando Sistema de Fallback para Embeddings")
    print("=" * 50)
    
    # Set up test environment
    os.environ["USE_EMBEDDING_MODEL_FALLBACK"] = "true"
    os.environ["EMBEDDING_MODEL"] = "invalid-embedding-model"
    os.environ["EMBEDDING_MODEL_API_KEY"] = "invalid-key"
    os.environ["EMBEDDING_MODEL_API_BASE"] = "http://invalid-url:9999/v1"
    os.environ["EMBEDDING_DIMENSIONS"] = "1024"
    os.environ["EMBEDDING_MODEL_FALLBACK"] = "text-embedding-3-small"
    os.environ["EMBEDDING_MODEL_FALLBACK_API_KEY"] = "sk-test123"  # This will also fail
    os.environ["EMBEDDING_DIMENSIONS_FALLBACK"] = "1536"
    
    test_texts = ["This is a test text for embedding generation."]
    
    try:
        print("Tentando embedding com fallback habilitado...")
        embeddings = create_embeddings_with_fallback(test_texts)
        print(f"✅ Embedding com fallback funcionou! Dimensões: {len(embeddings[0])}")
    except Exception as e:
        print(f"❌ Embedding falhou (esperado com chaves inválidas): {str(e)[:150]}...")
    
    # Test with fallback disabled
    os.environ["USE_EMBEDDING_MODEL_FALLBACK"] = "false"
    
    try:
        print("\nTentando embedding com fallback desabilitado...")
        embeddings = create_embeddings_with_fallback(test_texts)
        print(f"✅ Embedding funcionou! Dimensões: {len(embeddings[0])}")
    except Exception as e:
        print(f"❌ Embedding falhou (esperado com fallback desabilitado): {str(e)[:150]}...")


def test_client_creation_fallback():
    """
    Testa o sistema original de fallback para criação de clientes.
    """
    print("\n🧪 Testando Sistema de Fallback para Criação de Clientes")
    print("=" * 55)
    
    # Simple test for client creation fallback
    print("Testando criação de cliente com configuração inválida...")
    
    # Set invalid primary config
    os.environ["CHAT_MODEL"] = "invalid-model"
    os.environ["CHAT_MODEL_API_KEY"] = "invalid-key"
    os.environ["CHAT_MODEL_API_BASE"] = "http://invalid-url:9999/v1"
    os.environ["CHAT_MODEL_FALLBACK"] = "gpt-3.5-turbo"
    os.environ["CHAT_MODEL_FALLBACK_API_KEY"] = "invalid-fallback-key"
    
    try:
        client, model_name, is_fallback = get_chat_client_with_fallback()
        status = "FALLBACK" if is_fallback else "PRIMARY"
        print(f"✅ Criação de cliente funcionou: Usando {status} model: {model_name}")
    except Exception as e:
        print(f"❌ Criação de cliente falhou (esperado): {str(e)[:100]}...")


def run_all_tests():
    """
    Executa todos os testes do sistema de fallback.
    """
    print("🚀 Iniciando Testes Completos do Sistema de Fallback")
    print("=" * 60)
    print("NOTA: Estes testes usam chaves de API inválidas para demonstrar")
    print("o comportamento do sistema de fallback. Erros são esperados.")
    print("=" * 60)
    
    # Store original environment
    original_env = {}
    test_env_vars = [
        "USE_CHAT_MODEL_FALLBACK", "CHAT_MODEL", "CHAT_MODEL_API_KEY", 
        "CHAT_MODEL_API_BASE", "CHAT_MODEL_FALLBACK", "CHAT_MODEL_FALLBACK_API_KEY",
        "USE_EMBEDDING_MODEL_FALLBACK", "EMBEDDING_MODEL", "EMBEDDING_MODEL_API_KEY",
        "EMBEDDING_MODEL_API_BASE", "EMBEDDING_DIMENSIONS", "EMBEDDING_MODEL_FALLBACK",
        "EMBEDDING_MODEL_FALLBACK_API_KEY", "EMBEDDING_DIMENSIONS_FALLBACK"
    ]
    
    for var in test_env_vars:
        original_env[var] = os.getenv(var)
    
    try:
        # Run tests
        test_chat_completion_fallback()
        test_embedding_fallback()
        test_client_creation_fallback()
        
        print("\n" + "=" * 60)
        print("🎯 Todos os testes concluídos!")
        print("ℹ️  Para testes com chaves válidas, configure as variáveis de ambiente")
        print("   e execute novamente com modelos reais.")
        print("=" * 60)
        
    finally:
        # Restore original environment
        for var, value in original_env.items():
            if value is not None:
                os.environ[var] = value
            else:
                os.environ.pop(var, None)


if __name__ == "__main__":
    run_all_tests()