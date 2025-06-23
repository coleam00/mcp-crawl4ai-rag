"""
Integration tests for migration from old configuration to new configuration system.

These tests verify that the new configuration system maintains backward
compatibility with existing configurations and handles migration scenarios properly.
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

# Add src to path for importing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from config import Config


class TestMigration:
    """Test migration scenarios from old to new configuration."""

    def setup_method(self):
        """Set up test fixtures."""
        # Store original environment
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_migration_from_minimal_old_config(self):
        """Test migration from minimal old configuration (only required vars)."""
        # Simulate old minimal configuration
        old_config = {
            'SUPABASE_URL': 'https://old-project.supabase.co',
            'SUPABASE_SERVICE_KEY': 'old-service-key',
            # No DEFAULT_* variables
            # No new rate limiting variables
            # No explicit model configurations
        }
        
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'  # Prevent .env loading
        os.environ.update(old_config)
        
        config = Config()
        
        # Old variables should work
        assert config.SUPABASE_URL == 'https://old-project.supabase.co'
        assert config.SUPABASE_SERVICE_KEY == 'old-service-key'
        
        # New variables should use defaults
        assert config.HOST == '0.0.0.0'  # DEFAULT_HOST default
        assert config.PORT == '8051'     # DEFAULT_PORT default
        assert config.RERANKING_MODEL == 'cross-encoder/ms-marco-MiniLM-L-6-v2'
        assert config.OLLAMA_CHECK_TIMEOUT == 5
        assert config.REPO_ANALYSIS_TIMEOUT == 1800
        assert config.MAX_CONCURRENT_REQUESTS == 5
        assert config.RATE_LIMIT_DELAY == 0.5

    def test_migration_with_legacy_openai_key(self):
        """Test migration scenario with legacy OPENAI_API_KEY."""
        # Simulate old configuration with OPENAI_API_KEY
        old_config = {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-key',
            'OPENAI_API_KEY': 'sk-legacy-key-12345',  # Legacy key
            'HOST': 'localhost',
            'PORT': '8080',
        }
        
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update(old_config)
        
        config = Config()
        
        # Core config should work
        assert config.HOST == 'localhost'
        assert config.PORT == '8080'
        assert config.SUPABASE_URL == 'https://test.supabase.co'
        
        # OPENAI_API_KEY should be accessible but not used by the system
        # (The new system should prefer model-specific keys)
        assert os.environ.get('OPENAI_API_KEY') == 'sk-legacy-key-12345'

    def test_migration_with_partial_new_config(self):
        """Test migration with partial new configuration variables."""
        # Simulate configuration with some new and some missing variables
        mixed_config = {
            'SUPABASE_URL': 'https://mixed.supabase.co',
            'SUPABASE_SERVICE_KEY': 'mixed-key',
            'HOST': '192.168.1.100',
            'PORT': '9000',
            'DEFAULT_HOST': '10.0.0.1',  # New variable
            # DEFAULT_PORT missing - should use system default
            'OLLAMA_CHECK_TIMEOUT': '15',  # New variable
            # REPO_ANALYSIS_TIMEOUT missing - should use default
            'MAX_CONCURRENT_REQUESTS': '8',  # New variable
            'RATE_LIMIT_DELAY': '1.0',       # New variable
            # CIRCUIT_BREAKER_THRESHOLD missing - should use default
        }
        
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update(mixed_config)
        
        config = Config()
        
        # Explicitly set values should be used
        assert config.HOST == '192.168.1.100'
        assert config.PORT == '9000'
        assert config.DEFAULT_HOST == '10.0.0.1'
        assert config.OLLAMA_CHECK_TIMEOUT == 15
        assert config.MAX_CONCURRENT_REQUESTS == 8
        assert config.RATE_LIMIT_DELAY == 1.0
        
        # Missing values should use system defaults
        assert config.DEFAULT_PORT == '8051'
        assert config.REPO_ANALYSIS_TIMEOUT == 1800
        assert config.CIRCUIT_BREAKER_THRESHOLD == 3

    def test_migration_env_file_format(self):
        """Test migration using .env file in old format."""
        old_env_content = """
# Old configuration format
HOST=localhost
PORT=8080
SUPABASE_URL=https://old-format.supabase.co
SUPABASE_SERVICE_KEY=old-format-key
CHAT_MODEL=gpt-3.5-turbo
EMBEDDING_MODEL=text-embedding-ada-002
USE_RERANKING=false

# Some old performance settings
MAX_WORKERS_SUMMARY=5
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_file.write_text(old_env_content)
            
            # Simulate non-container environment to enable .env loading
            os.environ.clear()
            for key in ['CONTAINER', 'KUBERNETES_SERVICE_HOST']:
                os.environ.pop(key, None)
            
            with patch('config.Path') as mock_path:
                mock_path.return_value.resolve.return_value.parent.parent = Path(temp_dir)
                
                with patch('config.load_dotenv') as mock_load_dotenv:
                    with patch.object(Path, 'exists', return_value=True):
                        config = Config()
                        
                        # Verify dotenv loading was attempted
                        mock_load_dotenv.assert_called_once()
                        
                        # Test that system still works with defaults for missing vars
                        assert config.RERANKING_MODEL == 'cross-encoder/ms-marco-MiniLM-L-6-v2'
                        assert config.OLLAMA_CHECK_TIMEOUT == 5
                        assert config.MAX_CONCURRENT_REQUESTS == 5

    def test_backward_compatibility_all_properties_accessible(self):
        """Test that all configuration properties are accessible for backward compatibility."""
        # Test with minimal environment
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'SUPABASE_URL': 'https://compat.supabase.co',
            'SUPABASE_SERVICE_KEY': 'compat-key'
        })
        
        config = Config()
        
        # All these properties should be accessible without errors
        properties_to_test = [
            'HOST', 'PORT', 'DEFAULT_HOST', 'DEFAULT_PORT', 'TRANSPORT',
            'RERANKING_MODEL', 'CHAT_MODEL', 'EMBEDDING_MODEL',
            'OLLAMA_CHECK_TIMEOUT', 'REPO_ANALYSIS_TIMEOUT', 'REQUEST_TIMEOUT',
            'SUPABASE_URL', 'SUPABASE_SERVICE_KEY', 'NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD',
            'USE_KNOWLEDGE_GRAPH', 'USE_RERANKING', 'USE_HYBRID_SEARCH', 'USE_AGENTIC_RAG',
            'USE_CHAT_MODEL_FALLBACK', 'USE_EMBEDDING_MODEL_FALLBACK',
            'MAX_CRAWL_DEPTH', 'MAX_CONCURRENT_CRAWLS', 'CHUNK_SIZE', 'DEFAULT_MATCH_COUNT',
            'MAX_WORKERS_SUMMARY', 'MAX_WORKERS_SOURCE_SUMMARY',
            'MAX_CONCURRENT_REQUESTS', 'RATE_LIMIT_DELAY', 'CIRCUIT_BREAKER_THRESHOLD', 'CLIENT_CACHE_TTL',
            'EMBEDDING_MODEL_API_BASE'
        ]
        
        for prop in properties_to_test:
            try:
                value = getattr(config, prop)
                # Property should return a value (can be None for optional properties)
                assert value is not None or prop in [
                    'SUPABASE_URL', 'SUPABASE_SERVICE_KEY', 'NEO4J_URI', 
                    'NEO4J_USER', 'NEO4J_PASSWORD', 'EMBEDDING_MODEL_API_BASE'
                ], f"Property {prop} should have a default value"
            except Exception as e:
                pytest.fail(f"Property {prop} should be accessible without error, got: {e}")

    def test_migration_preserves_existing_values(self):
        """Test that migration preserves all existing configuration values."""
        # Set up comprehensive old configuration
        comprehensive_config = {
            # Core server settings
            'HOST': '172.16.0.1',
            'PORT': '7777',
            'TRANSPORT': 'stdio',
            
            # Database settings
            'SUPABASE_URL': 'https://comprehensive.supabase.co',
            'SUPABASE_SERVICE_KEY': 'comprehensive-key',
            'NEO4J_URI': 'bolt://neo4j.example.com:7687',
            'NEO4J_USER': 'admin',
            'NEO4J_PASSWORD': 'secret123',
            
            # Model settings
            'CHAT_MODEL': 'gpt-4',
            'EMBEDDING_MODEL': 'text-embedding-3-large',
            'RERANKING_MODEL': 'custom-reranker',
            
            # Feature flags
            'USE_KNOWLEDGE_GRAPH': 'true',
            'USE_RERANKING': 'true',
            'USE_HYBRID_SEARCH': 'true',
            'USE_AGENTIC_RAG': 'true',
            'USE_CHAT_MODEL_FALLBACK': 'true',
            'USE_EMBEDDING_MODEL_FALLBACK': 'true',
            
            # Performance settings
            'MAX_CRAWL_DEPTH': '5',
            'MAX_CONCURRENT_CRAWLS': '15',
            'CHUNK_SIZE': '8000',
            'DEFAULT_MATCH_COUNT': '10',
            'MAX_WORKERS_SUMMARY': '8',
            'MAX_WORKERS_SOURCE_SUMMARY': '4',
            
            # New rate limiting settings
            'MAX_CONCURRENT_REQUESTS': '12',
            'RATE_LIMIT_DELAY': '0.75',
            'CIRCUIT_BREAKER_THRESHOLD': '5',
            'CLIENT_CACHE_TTL': '7200',
            'REQUEST_TIMEOUT': '45',
            
            # Timeout settings
            'OLLAMA_CHECK_TIMEOUT': '20',
            'REPO_ANALYSIS_TIMEOUT': '3600',
        }
        
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update(comprehensive_config)
        
        config = Config()
        
        # Verify all values are preserved
        assert config.HOST == '172.16.0.1'
        assert config.PORT == '7777'
        assert config.TRANSPORT == 'stdio'
        assert config.SUPABASE_URL == 'https://comprehensive.supabase.co'
        assert config.SUPABASE_SERVICE_KEY == 'comprehensive-key'
        assert config.NEO4J_URI == 'bolt://neo4j.example.com:7687'
        assert config.NEO4J_USER == 'admin'
        assert config.NEO4J_PASSWORD == 'secret123'
        assert config.CHAT_MODEL == 'gpt-4'
        assert config.EMBEDDING_MODEL == 'text-embedding-3-large'
        assert config.RERANKING_MODEL == 'custom-reranker'
        assert config.USE_KNOWLEDGE_GRAPH == True
        assert config.USE_RERANKING == True
        assert config.USE_HYBRID_SEARCH == True
        assert config.USE_AGENTIC_RAG == True
        assert config.USE_CHAT_MODEL_FALLBACK == True
        assert config.USE_EMBEDDING_MODEL_FALLBACK == True
        assert config.MAX_CRAWL_DEPTH == 5
        assert config.MAX_CONCURRENT_CRAWLS == 15
        assert config.CHUNK_SIZE == 8000
        assert config.DEFAULT_MATCH_COUNT == 10
        assert config.MAX_WORKERS_SUMMARY == 8
        assert config.MAX_WORKERS_SOURCE_SUMMARY == 4
        assert config.MAX_CONCURRENT_REQUESTS == 12
        assert config.RATE_LIMIT_DELAY == 0.75
        assert config.CIRCUIT_BREAKER_THRESHOLD == 5
        assert config.CLIENT_CACHE_TTL == 7200
        assert config.REQUEST_TIMEOUT == 45
        assert config.OLLAMA_CHECK_TIMEOUT == 20
        assert config.REPO_ANALYSIS_TIMEOUT == 3600

    def test_migration_with_invalid_old_values(self):
        """Test migration handles invalid values in old configuration gracefully."""
        # Set up configuration with some invalid values
        invalid_config = {
            'SUPABASE_URL': 'https://invalid.supabase.co',
            'SUPABASE_SERVICE_KEY': 'invalid-key',
            'HOST': '192.168.1.1',  # Valid
            'PORT': 'not_a_number',  # Invalid
            'MAX_CONCURRENT_REQUESTS': 'invalid_number',  # Invalid
            'RATE_LIMIT_DELAY': 'not_a_float',  # Invalid
            'USE_RERANKING': 'maybe',  # Invalid boolean
        }
        
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update(invalid_config)
        
        config = Config()
        
        # Valid values should work
        assert config.HOST == '192.168.1.1'
        assert config.SUPABASE_URL == 'https://invalid.supabase.co'
        
        # Invalid values should raise errors when accessed
        with pytest.raises(ValueError):
            _ = config.PORT
            
        with pytest.raises(ValueError):
            _ = config.MAX_CONCURRENT_REQUESTS
            
        with pytest.raises(ValueError):
            _ = config.RATE_LIMIT_DELAY
        
        # Invalid boolean should default to False
        assert config.USE_RERANKING == False

    def test_migration_environment_detection_unchanged(self):
        """Test that environment detection behavior is unchanged during migration."""
        # Test container detection with old and new variables
        test_cases = [
            {'CONTAINER': 'true'},
            {'KUBERNETES_SERVICE_HOST': 'kubernetes.default.svc'},
        ]
        
        for env_vars in test_cases:
            os.environ.clear()
            os.environ.update(self.original_env)
            os.environ.update(env_vars)
            
            config = Config()
            
            # Should detect containerized environment regardless of other config
            assert config._is_containerized() == True

    def test_migration_preserves_optional_behavior(self):
        """Test that optional configuration variables maintain their behavior."""
        # Test with only required variables
        minimal_config = {
            'SUPABASE_URL': 'https://minimal.supabase.co',
            'SUPABASE_SERVICE_KEY': 'minimal-key',
        }
        
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update(minimal_config)
        
        config = Config()
        
        # Optional variables should return None
        assert config.NEO4J_URI is None
        assert config.NEO4J_USER is None
        assert config.NEO4J_PASSWORD is None
        assert config.EMBEDDING_MODEL_API_BASE is None
        
        # Required variables with defaults should use defaults
        assert config.HOST == '0.0.0.0'
        assert config.PORT == '8051'
        assert config.CHAT_MODEL == 'gpt-4o-mini'
        assert config.EMBEDDING_MODEL == 'text-embedding-3-small'

    def test_migration_dotenv_precedence_unchanged(self):
        """Test that .env file precedence behavior is unchanged."""
        # Test in development environment (non-container)
        os.environ.clear()
        for key in ['CONTAINER', 'KUBERNETES_SERVICE_HOST']:
            os.environ.pop(key, None)
        
        # Set an environment variable
        os.environ['HOST'] = 'env-host'
        
        env_content = """HOST=dotenv-host
PORT=9999
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_file.write_text(env_content)
            
            with patch('config.Path') as mock_path:
                mock_path.return_value.resolve.return_value.parent.parent = Path(temp_dir)
                
                with patch('config.load_dotenv') as mock_load_dotenv:
                    with patch.object(Path, 'exists', return_value=True):
                        config = Config()
                        
                        # Environment variables should take precedence over .env
                        assert config.HOST == 'env-host'
                        
                        # .env should be loaded
                        mock_load_dotenv.assert_called_once()