#!/usr/bin/env python3
"""
Test script for the new provider system.

This script tests both single-provider and dual-provider configurations
to ensure backward compatibility and new functionality work correctly.
"""

import os
import asyncio
from pathlib import Path
import sys

# Add src to path so we can import providers
sys.path.append(str(Path(__file__).parent / "src"))

from providers import get_provider_manager, get_provider

# Try to import dotenv, but don't fail if not available
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

# Load environment variables if dotenv is available
if HAS_DOTENV:
    load_dotenv()

async def test_dual_provider_mode():
    """Test the new dual-provider mode."""
    print("\n=== Testing Dual-Provider Mode ===")
    
    # Temporarily set dual-provider environment variables
    os.environ["EMBEDDING_PROVIDER"] = "openai"
    os.environ["LLM_PROVIDER"] = "openai"
    os.environ["EMBEDDING_MODEL"] = "text-embedding-3-small"
    os.environ["LLM_MODEL"] = "gpt-4o-mini"
    
    try:
        manager = get_provider_manager()
        
        # Test provider info
        info = manager.provider_info
        print(f"Embedding Provider: {info['embedding_provider']}")
        print(f"LLM Provider: {info['llm_provider']}")
        print(f"Embedding Model: {info['embedding_model']}")
        print(f"LLM Model: {info['llm_model']}")
        print(f"Embedding Dimension: {manager.embedding_dimension}")
        
        # Test embeddings (if API key available)
        if os.getenv("OPENAI_API_KEY"):
            print("\nTesting embeddings...")
            response = await manager.create_embeddings(["Hello world", "Test embedding"])
            print(f"Created {len(response.embeddings)} embeddings")
            print(f"First embedding dimension: {len(response.embeddings[0])}")
            
            # Test completion
            print("\nTesting completion...")
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello in one word."}
            ]
            response = await manager.create_completion(messages)
            print(f"Completion: {response.content}")
        else:
            print("Skipping API tests (no OPENAI_API_KEY)")
            
    except Exception as e:
        print(f"Error in dual-provider mode: {e}")
    
    # Clean up environment variables
    if "EMBEDDING_PROVIDER" in os.environ:
        del os.environ["EMBEDDING_PROVIDER"]
    if "LLM_PROVIDER" in os.environ:
        del os.environ["LLM_PROVIDER"]

async def test_single_provider_mode():
    """Test backward compatibility with single-provider mode."""
    print("\n=== Testing Single-Provider Mode (Backward Compatibility) ===")
    
    # Set single-provider environment variable
    os.environ["AI_PROVIDER"] = "openai"
    
    try:
        manager = get_provider_manager()
        
        # Test provider info
        info = manager.provider_info
        print(f"Embedding Provider: {info['embedding_provider']}")
        print(f"LLM Provider: {info['llm_provider']}")
        print(f"Same provider for both: {info['embedding_provider'] == info['llm_provider']}")
        
        # Test that old factory method still works
        old_provider = get_provider()
        print(f"Old provider name: {old_provider.provider_name}")
        
    except Exception as e:
        print(f"Error in single-provider mode: {e}")
    
    # Clean up
    if "AI_PROVIDER" in os.environ:
        del os.environ["AI_PROVIDER"]

async def test_mixed_providers():
    """Test mixing different providers for embeddings and completions."""
    print("\n=== Testing Mixed Providers ===")
    
    # Test OpenAI embeddings + Gemini completions (if keys available)
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    
    if has_openai and has_gemini:
        os.environ["EMBEDDING_PROVIDER"] = "openai"
        os.environ["LLM_PROVIDER"] = "gemini"
        os.environ["EMBEDDING_MODEL"] = "text-embedding-3-small"
        os.environ["LLM_MODEL"] = "gemini-1.5-flash"
        
        try:
            manager = get_provider_manager()
            info = manager.provider_info
            
            print(f"Mixed setup: {info['embedding_provider']} + {info['llm_provider']}")
            
            # Test that both work
            embeddings = await manager.create_embeddings(["test"])
            print(f"Embeddings created: {len(embeddings.embeddings)}")
            
            completion = await manager.create_completion([
                {"role": "user", "content": "Say 'test successful' in exactly two words."}
            ])
            print(f"Completion: {completion.content}")
            
        except Exception as e:
            print(f"Error in mixed providers: {e}")
        
    else:
        print("Skipping mixed provider test (missing API keys)")
    
    # Clean up
    for key in ["EMBEDDING_PROVIDER", "LLM_PROVIDER", "EMBEDDING_MODEL", "LLM_MODEL"]:
        if key in os.environ:
            del os.environ[key]

def test_configuration_detection():
    """Test configuration detection logic."""
    print("\n=== Testing Configuration Detection ===")
    
    # Test dual-provider detection
    os.environ["EMBEDDING_PROVIDER"] = "openai"
    os.environ["LLM_PROVIDER"] = "gemini"
    
    manager = get_provider_manager()
    info = manager.provider_info
    print(f"Detected dual-provider mode: {info['embedding_provider']} + {info['llm_provider']}")
    
    # Clean up
    del os.environ["EMBEDDING_PROVIDER"]
    del os.environ["LLM_PROVIDER"]
    
    # Test single-provider fallback
    os.environ["AI_PROVIDER"] = "gemini"
    
    manager = get_provider_manager()
    info = manager.provider_info
    print(f"Detected single-provider mode: {info['embedding_provider']}")
    
    # Clean up
    del os.environ["AI_PROVIDER"]

async def main():
    """Run all tests."""
    print("🚀 Testing New Provider System")
    print("=" * 50)
    
    # Test configuration detection first (no API calls)
    test_configuration_detection()
    
    # Test modes with potential API calls
    await test_single_provider_mode()
    await test_dual_provider_mode()
    await test_mixed_providers()
    
    print("\n✅ All tests completed!")
    print("\nNote: Some tests may have been skipped due to missing API keys.")
    print("To test specific providers, set the following environment variables:")
    print("- OPENAI_API_KEY for OpenAI tests")
    print("- GEMINI_API_KEY for Gemini tests")
    print("- DEEPSEEK_API_KEY for DeepSeek tests")
    print("- ANTHROPIC_API_KEY for Anthropic tests")

if __name__ == "__main__":
    asyncio.run(main()) 