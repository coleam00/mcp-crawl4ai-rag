#!/usr/bin/env python3
"""
Example script demonstrating how to use the configuration module.

This script shows practical usage patterns for the config module
and how it integrates with the MCP server.
"""

import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def main():
    """Demonstrate configuration module usage."""
    print("Configuration Module Usage Example")
    print("=" * 50)
    
    # Set up some example environment variables
    # In practice, these would come from your .env file or environment
    example_env = {
        'SUPABASE_URL': 'https://example.supabase.co',
        'SUPABASE_SERVICE_KEY': 'example_service_key_12345',
        'HOST': '127.0.0.1',
        'PORT': '8080',
        'TRANSPORT': 'stdio',
        'CHAT_MODEL': 'gpt-4o-mini',
        'EMBEDDING_MODEL': 'text-embedding-3-small',
        'EMBEDDING_DIMENSIONS': '1536',
        'USE_CONTEXTUAL_EMBEDDINGS': 'true',
        'USE_HYBRID_SEARCH': 'false',
        'USE_RERANKING': 'true',
        'MAX_CONCURRENT_REQUESTS': '3',
        'RATE_LIMIT_DELAY': '1.0',
        'MAX_WORKERS_SUMMARY': '2',
        'SUPABASE_BATCH_SIZE': '5',
    }
    
    # Set environment variables for this example
    for key, value in example_env.items():
        os.environ[key] = value
    
    try:
        # Import the configuration module
        # Note: This will fail if python-dotenv is not installed
        # In that case, run: pip install python-dotenv
        from config import (
            get_config, get_server_config, get_database_config,
            get_model_config, get_feature_flags, get_performance_config
        )
        
        print("\n1. Basic Configuration Access:")
        print("-" * 30)
        
        # Get the global configuration instance
        cfg = get_config()
        print(f"Environment type: {'Container' if cfg.is_container else 'Development'}")
        print(f"Host: {cfg.get_str('HOST')}")
        print(f"Port: {cfg.get_int('PORT')}")
        print(f"Rate limit delay: {cfg.get_float('RATE_LIMIT_DELAY')} seconds")
        print(f"Use reranking: {cfg.get_bool('USE_RERANKING')}")
        
        print("\n2. Server Configuration:")
        print("-" * 30)
        server_config = get_server_config()
        for key, value in server_config.items():
            print(f"{key}: {value}")
        
        print("\n3. Database Configuration:")
        print("-" * 30)
        db_config = get_database_config()
        for key, value in db_config.items():
            if 'key' in key.lower():
                # Mask sensitive values
                masked_value = f"{value[:4]}...{value[-4:]}" if value and len(value) > 8 else "***"
                print(f"{key}: {masked_value}")
            else:
                print(f"{key}: {value}")
        
        print("\n4. AI Model Configuration:")
        print("-" * 30)
        model_config = get_model_config()
        important_keys = ['chat_model', 'embedding_model', 'embedding_dimensions']
        for key in important_keys:
            if key in model_config:
                print(f"{key}: {model_config[key]}")
        
        print("\n5. Feature Flags:")
        print("-" * 30)
        features = get_feature_flags()
        for key, value in features.items():
            status = "✅ Enabled" if value else "❌ Disabled"
            print(f"{key}: {status}")
        
        print("\n6. Performance Configuration:")
        print("-" * 30)
        perf_config = get_performance_config()
        important_perf = [
            'max_concurrent_requests', 'rate_limit_delay', 
            'max_workers_summary', 'supabase_batch_size'
        ]
        for key in important_perf:
            if key in perf_config:
                print(f"{key}: {perf_config[key]}")
        
        print("\n7. Type Conversion Examples:")
        print("-" * 30)
        
        # Demonstrate type conversion with validation
        try:
            # This will work - valid integer
            workers = cfg.get_int('MAX_WORKERS_SUMMARY', 1)
            print(f"Workers (int): {workers}")
            
            # This will work - valid float
            delay = cfg.get_float('RATE_LIMIT_DELAY', 0.5)
            print(f"Delay (float): {delay}")
            
            # This will work - valid boolean
            use_feature = cfg.get_bool('USE_CONTEXTUAL_EMBEDDINGS', False)
            print(f"Use feature (bool): {use_feature}")
            
            # Demonstrate list parsing
            os.environ['TEST_LIST'] = 'item1,item2,item3'
            test_list = cfg.get_list('TEST_LIST', [])
            print(f"Test list: {test_list}")
            
        except Exception as e:
            print(f"Type conversion error: {e}")
        
        print("\n8. Configuration Caching:")
        print("-" * 30)
        
        # Demonstrate configuration caching
        import time
        
        start_time = time.time()
        for _ in range(1000):
            cfg.get_int('PORT')  # This should be fast due to caching
        end_time = time.time()
        
        print(f"1000 cached config reads took: {(end_time - start_time)*1000:.2f}ms")
        
        print("\n9. How to Use in Your Application:")
        print("-" * 30)
        print("""
# In your application code:
from config import get_config, get_server_config, get_feature_flags

# Get configuration
cfg = get_config()
server_config = get_server_config()
features = get_feature_flags()

# Use type-safe getters
host = cfg.get_str('HOST', '0.0.0.0')
port = cfg.get_int('PORT', 8051)
use_feature = cfg.get_bool('USE_RERANKING', False)

# Check environment
if cfg.is_container:
    print("Running in container")
else:
    print("Running in development")

# Access structured config
print(f"Server will run on {server_config['host']}:{server_config['port']}")
        """)
        
        print("\n" + "=" * 50)
        print("✅ Configuration module working correctly!")
        print("\nKey Benefits:")
        print("- ✅ Automatic environment detection")
        print("- ✅ Type-safe configuration access")
        print("- ✅ Comprehensive validation")
        print("- ✅ Configuration caching for performance")
        print("- ✅ Sensitive value masking in logs")
        print("- ✅ Structured configuration groups")
        
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        print("\nThis example requires the python-dotenv package.")
        print("Install it with: pip install python-dotenv")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()