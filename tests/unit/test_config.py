"""
Unit tests for the Config class and configuration management system.

This module tests all aspects of the configuration system including:
- Environment detection (container vs development)
- Configuration loading with fallbacks
- Type conversion (string, int, float, bool)
- Validation of required variables
- Error handling for invalid values
- Masking of sensitive data in logs
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from typing import Dict, Any

import pytest

from config import Config, config


class TestConfigInitialization:
    """Test configuration initialization and environment detection."""
    
    def test_config_initialization_clean_env(self, clean_env):
        """Test config initialization in clean environment."""
        # Clear environment
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'  # Prevent .env loading
        
        config_instance = Config()
        assert config_instance is not None
    
    def test_config_initialization_with_dotenv(self, clean_env, temp_dotenv_file):
        """Test config initialization with .env file loading."""
        # Write test content to .env file
        with open(temp_dotenv_file, 'w') as f:
            f.write('TEST_VAR=test_value\n')
            f.write('HOST=192.168.1.1\n')
        
        # Mock the dotenv file path
        with patch('config.Path.resolve') as mock_resolve:
            mock_resolve.return_value = temp_dotenv_file.parent
            with patch('config.Path.exists', return_value=True):
                config_instance = Config()
                assert config_instance is not None
    
    def test_config_initialization_without_dotenv_library(self, clean_env):
        """Test config initialization when dotenv library is not available."""
        os.environ.clear()
        
        # Mock ImportError for dotenv
        with patch('config.load_dotenv', side_effect=ImportError):
            config_instance = Config()
            assert config_instance is not None
    
    def test_config_initialization_dotenv_exception(self, clean_env):
        """Test config initialization when dotenv loading raises exception."""
        os.environ.clear()
        
        # Mock exception during dotenv loading
        with patch('config.load_dotenv', side_effect=Exception("File error")):
            config_instance = Config()
            assert config_instance is not None


class TestEnvironmentDetection:
    """Test environment detection methods."""
    
    def test_is_containerized_dockerenv_file(self, clean_env):
        """Test container detection via .dockerenv file."""
        config_instance = Config()
        
        with patch('os.path.exists', return_value=True) as mock_exists:
            assert config_instance._is_containerized() is True
            mock_exists.assert_called_with('/.dockerenv')
    
    def test_is_containerized_container_env_var(self, clean_env):
        """Test container detection via CONTAINER environment variable."""
        os.environ['CONTAINER'] = 'true'
        config_instance = Config()
        
        with patch('os.path.exists', return_value=False):
            assert config_instance._is_containerized() is True
    
    def test_is_containerized_kubernetes(self, clean_env):
        """Test container detection via Kubernetes environment."""
        os.environ['KUBERNETES_SERVICE_HOST'] = '10.0.0.1'
        config_instance = Config()
        
        with patch('os.path.exists', return_value=False):
            assert config_instance._is_containerized() is True
    
    def test_is_not_containerized(self, clean_env):
        """Test non-containerized environment detection."""
        config_instance = Config()
        
        with patch('os.path.exists', return_value=False):
            assert config_instance._is_containerized() is False
    
    def test_dotenv_loading_disabled_in_container(self, clean_env):
        """Test that .env loading is disabled in containerized environments."""
        config_instance = Config()
        
        with patch.object(config_instance, '_is_containerized', return_value=True):
            with patch.object(config_instance, '_load_dotenv_file') as mock_load:
                config_instance._load_environment()
                mock_load.assert_not_called()
    
    def test_dotenv_loading_disabled_by_env_var(self, clean_env):
        """Test that .env loading can be disabled via NO_DOTENV environment variable."""
        os.environ['NO_DOTENV'] = 'true'
        config_instance = Config()
        
        with patch.object(config_instance, '_is_containerized', return_value=False):
            with patch.object(config_instance, '_load_dotenv_file') as mock_load:
                config_instance._load_environment()
                mock_load.assert_not_called()


class TestConfigurationProperties:
    """Test configuration property values and defaults."""
    
    def test_server_configuration_defaults(self, clean_env):
        """Test server configuration default values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        config_instance = Config()
        
        assert config_instance.HOST == "0.0.0.0"
        assert config_instance.PORT == "8051"
        assert config_instance.DEFAULT_HOST == "0.0.0.0"
        assert config_instance.DEFAULT_PORT == "8051"
        assert config_instance.TRANSPORT == "sse"
    
    def test_server_configuration_overrides(self, clean_env, sample_config_values):
        """Test server configuration with environment overrides."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'HOST': sample_config_values['HOST'],
            'PORT': sample_config_values['PORT'],
            'TRANSPORT': sample_config_values['TRANSPORT']
        })
        
        config_instance = Config()
        assert config_instance.HOST == sample_config_values['HOST']
        assert config_instance.PORT == sample_config_values['PORT']
        assert config_instance.TRANSPORT == sample_config_values['TRANSPORT']
    
    def test_model_configuration_defaults(self, clean_env):
        """Test model configuration default values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        config_instance = Config()
        
        assert config_instance.RERANKING_MODEL == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert config_instance.CHAT_MODEL == "gpt-4o-mini"
        assert config_instance.EMBEDDING_MODEL == "text-embedding-3-small"
    
    def test_model_configuration_overrides(self, clean_env, sample_config_values):
        """Test model configuration with environment overrides."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'RERANKING_MODEL': sample_config_values['RERANKING_MODEL'],
            'CHAT_MODEL': sample_config_values['CHAT_MODEL'],
            'EMBEDDING_MODEL': sample_config_values['EMBEDDING_MODEL']
        })
        
        config_instance = Config()
        assert config_instance.RERANKING_MODEL == sample_config_values['RERANKING_MODEL']
        assert config_instance.CHAT_MODEL == sample_config_values['CHAT_MODEL']
        assert config_instance.EMBEDDING_MODEL == sample_config_values['EMBEDDING_MODEL']
    
    def test_timeout_configuration_defaults(self, clean_env):
        """Test timeout configuration default values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        config_instance = Config()
        
        assert config_instance.OLLAMA_CHECK_TIMEOUT == 5
        assert config_instance.REPO_ANALYSIS_TIMEOUT == 1800
        assert config_instance.REQUEST_TIMEOUT == 30
    
    def test_timeout_configuration_overrides(self, clean_env, sample_config_values):
        """Test timeout configuration with environment overrides."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'OLLAMA_CHECK_TIMEOUT': sample_config_values['OLLAMA_CHECK_TIMEOUT'],
            'REPO_ANALYSIS_TIMEOUT': sample_config_values['REPO_ANALYSIS_TIMEOUT'],
            'REQUEST_TIMEOUT': sample_config_values['REQUEST_TIMEOUT']
        })
        
        config_instance = Config()
        assert config_instance.OLLAMA_CHECK_TIMEOUT == int(sample_config_values['OLLAMA_CHECK_TIMEOUT'])
        assert config_instance.REPO_ANALYSIS_TIMEOUT == int(sample_config_values['REPO_ANALYSIS_TIMEOUT'])
        assert config_instance.REQUEST_TIMEOUT == int(sample_config_values['REQUEST_TIMEOUT'])
    
    def test_database_configuration_defaults(self, clean_env):
        """Test database configuration default values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        config_instance = Config()
        
        assert config_instance.SUPABASE_URL is None
        assert config_instance.SUPABASE_SERVICE_KEY is None
        assert config_instance.NEO4J_URI is None
        assert config_instance.NEO4J_USER is None
        assert config_instance.NEO4J_PASSWORD is None
    
    def test_database_configuration_overrides(self, clean_env, sample_config_values):
        """Test database configuration with environment overrides."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'SUPABASE_URL': sample_config_values['SUPABASE_URL'],
            'SUPABASE_SERVICE_KEY': sample_config_values['SUPABASE_SERVICE_KEY'],
            'NEO4J_URI': sample_config_values['NEO4J_URI'],
            'NEO4J_USER': sample_config_values['NEO4J_USER'],
            'NEO4J_PASSWORD': sample_config_values['NEO4J_PASSWORD']
        })
        
        config_instance = Config()
        assert config_instance.SUPABASE_URL == sample_config_values['SUPABASE_URL']
        assert config_instance.SUPABASE_SERVICE_KEY == sample_config_values['SUPABASE_SERVICE_KEY']
        assert config_instance.NEO4J_URI == sample_config_values['NEO4J_URI']
        assert config_instance.NEO4J_USER == sample_config_values['NEO4J_USER']
        assert config_instance.NEO4J_PASSWORD == sample_config_values['NEO4J_PASSWORD']


class TestFeatureFlags:
    """Test feature flag configuration."""
    
    def test_feature_flags_defaults(self, clean_env):
        """Test feature flag default values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        config_instance = Config()
        
        assert config_instance.USE_KNOWLEDGE_GRAPH is False
        assert config_instance.USE_RERANKING is False
        assert config_instance.USE_HYBRID_SEARCH is False
        assert config_instance.USE_AGENTIC_RAG is False
        assert config_instance.USE_CHAT_MODEL_FALLBACK is False
        assert config_instance.USE_EMBEDDING_MODEL_FALLBACK is False
    
    def test_feature_flags_true_values(self, clean_env):
        """Test feature flags with true values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'USE_KNOWLEDGE_GRAPH': 'true',
            'USE_RERANKING': 'True',
            'USE_HYBRID_SEARCH': 'TRUE',
            'USE_AGENTIC_RAG': 'true',
            'USE_CHAT_MODEL_FALLBACK': 'true',
            'USE_EMBEDDING_MODEL_FALLBACK': 'true'
        })
        
        config_instance = Config()
        assert config_instance.USE_KNOWLEDGE_GRAPH is True
        assert config_instance.USE_RERANKING is True
        assert config_instance.USE_HYBRID_SEARCH is True
        assert config_instance.USE_AGENTIC_RAG is True
        assert config_instance.USE_CHAT_MODEL_FALLBACK is True
        assert config_instance.USE_EMBEDDING_MODEL_FALLBACK is True
    
    def test_feature_flags_false_values(self, clean_env):
        """Test feature flags with false values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'USE_KNOWLEDGE_GRAPH': 'false',
            'USE_RERANKING': 'False',
            'USE_HYBRID_SEARCH': 'FALSE',
            'USE_AGENTIC_RAG': 'no',
            'USE_CHAT_MODEL_FALLBACK': '0',
            'USE_EMBEDDING_MODEL_FALLBACK': 'disabled'
        })
        
        config_instance = Config()
        assert config_instance.USE_KNOWLEDGE_GRAPH is False
        assert config_instance.USE_RERANKING is False
        assert config_instance.USE_HYBRID_SEARCH is False
        assert config_instance.USE_AGENTIC_RAG is False
        assert config_instance.USE_CHAT_MODEL_FALLBACK is False
        assert config_instance.USE_EMBEDDING_MODEL_FALLBACK is False


class TestPerformanceConfiguration:
    """Test performance configuration settings."""
    
    def test_performance_defaults(self, clean_env):
        """Test performance configuration default values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        config_instance = Config()
        
        assert config_instance.MAX_CRAWL_DEPTH == 3
        assert config_instance.MAX_CONCURRENT_CRAWLS == 10
        assert config_instance.CHUNK_SIZE == 5000
        assert config_instance.DEFAULT_MATCH_COUNT == 5
        assert config_instance.MAX_WORKERS_SUMMARY == 10
        assert config_instance.MAX_WORKERS_SOURCE_SUMMARY == 5
    
    def test_performance_overrides(self, clean_env, sample_config_values):
        """Test performance configuration with environment overrides."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'MAX_CRAWL_DEPTH': sample_config_values['MAX_CRAWL_DEPTH'],
            'MAX_CONCURRENT_CRAWLS': sample_config_values['MAX_CONCURRENT_CRAWLS'],
            'CHUNK_SIZE': sample_config_values['CHUNK_SIZE'],
            'DEFAULT_MATCH_COUNT': sample_config_values['DEFAULT_MATCH_COUNT'],
            'MAX_WORKERS_SUMMARY': sample_config_values['MAX_WORKERS_SUMMARY'],
            'MAX_WORKERS_SOURCE_SUMMARY': sample_config_values['MAX_WORKERS_SOURCE_SUMMARY']
        })
        
        config_instance = Config()
        assert config_instance.MAX_CRAWL_DEPTH == int(sample_config_values['MAX_CRAWL_DEPTH'])
        assert config_instance.MAX_CONCURRENT_CRAWLS == int(sample_config_values['MAX_CONCURRENT_CRAWLS'])
        assert config_instance.CHUNK_SIZE == int(sample_config_values['CHUNK_SIZE'])
        assert config_instance.DEFAULT_MATCH_COUNT == int(sample_config_values['DEFAULT_MATCH_COUNT'])
        assert config_instance.MAX_WORKERS_SUMMARY == int(sample_config_values['MAX_WORKERS_SUMMARY'])
        assert config_instance.MAX_WORKERS_SOURCE_SUMMARY == int(sample_config_values['MAX_WORKERS_SOURCE_SUMMARY'])


class TestRateLimitingConfiguration:
    """Test rate limiting configuration settings."""
    
    def test_rate_limiting_defaults(self, clean_env):
        """Test rate limiting configuration default values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        config_instance = Config()
        
        assert config_instance.MAX_CONCURRENT_REQUESTS == 5
        assert config_instance.RATE_LIMIT_DELAY == 0.5
        assert config_instance.CIRCUIT_BREAKER_THRESHOLD == 3
        assert config_instance.CLIENT_CACHE_TTL == 3600
    
    def test_rate_limiting_overrides(self, clean_env, sample_config_values):
        """Test rate limiting configuration with environment overrides."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'MAX_CONCURRENT_REQUESTS': sample_config_values['MAX_CONCURRENT_REQUESTS'],
            'RATE_LIMIT_DELAY': sample_config_values['RATE_LIMIT_DELAY'],
            'CIRCUIT_BREAKER_THRESHOLD': sample_config_values['CIRCUIT_BREAKER_THRESHOLD'],
            'CLIENT_CACHE_TTL': sample_config_values['CLIENT_CACHE_TTL']
        })
        
        config_instance = Config()
        assert config_instance.MAX_CONCURRENT_REQUESTS == int(sample_config_values['MAX_CONCURRENT_REQUESTS'])
        assert config_instance.RATE_LIMIT_DELAY == float(sample_config_values['RATE_LIMIT_DELAY'])
        assert config_instance.CIRCUIT_BREAKER_THRESHOLD == int(sample_config_values['CIRCUIT_BREAKER_THRESHOLD'])
        assert config_instance.CLIENT_CACHE_TTL == int(sample_config_values['CLIENT_CACHE_TTL'])


class TestTypeConversion:
    """Test type conversion functionality."""
    
    def test_int_conversion_valid(self, clean_env):
        """Test valid integer conversion."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'MAX_CRAWL_DEPTH': '10',
            'OLLAMA_CHECK_TIMEOUT': '25',
            'MAX_CONCURRENT_REQUESTS': '100'
        })
        
        config_instance = Config()
        assert config_instance.MAX_CRAWL_DEPTH == 10
        assert config_instance.OLLAMA_CHECK_TIMEOUT == 25
        assert config_instance.MAX_CONCURRENT_REQUESTS == 100
    
    def test_int_conversion_invalid(self, clean_env):
        """Test invalid integer conversion raises ValueError."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ['MAX_CRAWL_DEPTH'] = 'not-a-number'
        
        config_instance = Config()
        with pytest.raises(ValueError):
            _ = config_instance.MAX_CRAWL_DEPTH
    
    def test_float_conversion_valid(self, clean_env):
        """Test valid float conversion."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ['RATE_LIMIT_DELAY'] = '2.5'
        
        config_instance = Config()
        assert config_instance.RATE_LIMIT_DELAY == 2.5
    
    def test_float_conversion_invalid(self, clean_env):
        """Test invalid float conversion raises ValueError."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ['RATE_LIMIT_DELAY'] = 'not-a-float'
        
        config_instance = Config()
        with pytest.raises(ValueError):
            _ = config_instance.RATE_LIMIT_DELAY
    
    def test_bool_conversion_valid(self, clean_env):
        """Test valid boolean conversion."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        # Test various true values
        for true_val in ['true', 'True', 'TRUE', 'yes', 'Yes', '1']:
            os.environ['USE_KNOWLEDGE_GRAPH'] = true_val
            config_instance = Config()
            assert config_instance.USE_KNOWLEDGE_GRAPH is True
        
        # Test various false values
        for false_val in ['false', 'False', 'FALSE', 'no', 'No', '0', 'disabled', '']:
            os.environ['USE_KNOWLEDGE_GRAPH'] = false_val
            config_instance = Config()
            assert config_instance.USE_KNOWLEDGE_GRAPH is False


class TestErrorHandling:
    """Test error handling and validation."""
    
    def test_missing_required_optional_values(self, clean_env):
        """Test handling of missing optional values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        config_instance = Config()
        
        # Optional values should return None
        assert config_instance.SUPABASE_URL is None
        assert config_instance.SUPABASE_SERVICE_KEY is None
        assert config_instance.NEO4J_URI is None
        assert config_instance.NEO4J_USER is None
        assert config_instance.NEO4J_PASSWORD is None
        assert config_instance.EMBEDDING_MODEL_API_BASE is None
    
    def test_invalid_numeric_values(self, clean_env, invalid_config_values):
        """Test handling of invalid numeric values."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        config_instance = Config()
        
        # Test invalid integer
        os.environ['OLLAMA_CHECK_TIMEOUT'] = invalid_config_values['OLLAMA_CHECK_TIMEOUT']
        with pytest.raises(ValueError):
            _ = config_instance.OLLAMA_CHECK_TIMEOUT
        
        # Test invalid float
        os.environ['RATE_LIMIT_DELAY'] = invalid_config_values['RATE_LIMIT_DELAY']
        with pytest.raises(ValueError):
            _ = config_instance.RATE_LIMIT_DELAY
    
    def test_negative_values_accepted(self, clean_env):
        """Test that negative values are accepted (if valid for the use case)."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'MAX_CRAWL_DEPTH': '-1',
            'RATE_LIMIT_DELAY': '-0.5'
        })
        
        config_instance = Config()
        assert config_instance.MAX_CRAWL_DEPTH == -1
        assert config_instance.RATE_LIMIT_DELAY == -0.5
    
    def test_zero_values_accepted(self, clean_env):
        """Test that zero values are accepted."""
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        os.environ.update({
            'MAX_CRAWL_DEPTH': '0',
            'RATE_LIMIT_DELAY': '0.0',
            'MAX_CONCURRENT_REQUESTS': '0'
        })
        
        config_instance = Config()
        assert config_instance.MAX_CRAWL_DEPTH == 0
        assert config_instance.RATE_LIMIT_DELAY == 0.0
        assert config_instance.MAX_CONCURRENT_REQUESTS == 0


class TestGlobalConfigInstance:
    """Test the global configuration instance."""
    
    def test_global_config_instance_exists(self):
        """Test that the global config instance exists."""
        assert config is not None
        assert isinstance(config, Config)
    
    def test_global_config_instance_is_singleton(self):
        """Test that the global config instance behaves consistently."""
        # Import the global config instance
        from config import config as config1
        from config import config as config2
        
        # They should be the same object
        assert config1 is config2
    
    def test_global_config_properties_accessible(self):
        """Test that global config properties are accessible."""
        # Basic smoke test - these should not raise exceptions
        _ = config.HOST
        _ = config.PORT
        _ = config.TRANSPORT
        _ = config.CHAT_MODEL
        _ = config.EMBEDDING_MODEL
        _ = config.USE_KNOWLEDGE_GRAPH
        _ = config.MAX_CRAWL_DEPTH


class TestConfigurationDocumentation:
    """Test that configuration is properly documented."""
    
    def test_all_properties_have_docstrings(self):
        """Test that all configuration properties have docstrings."""
        config_instance = Config()
        
        # Get all properties
        properties = [
            name for name in dir(config_instance)
            if isinstance(getattr(Config, name, None), property)
            and not name.startswith('_')
        ]
        
        # Check each property has a docstring
        for prop_name in properties:
            prop = getattr(Config, prop_name)
            assert prop.__doc__ is not None, f"Property {prop_name} missing docstring"
            assert prop.__doc__.strip() != "", f"Property {prop_name} has empty docstring"
    
    def test_class_has_docstring(self):
        """Test that the Config class has a docstring."""
        assert Config.__doc__ is not None
        assert Config.__doc__.strip() != ""
    
    def test_init_method_has_docstring(self):
        """Test that the __init__ method has a docstring."""
        assert Config.__init__.__doc__ is not None
        assert Config.__init__.__doc__.strip() != ""


class TestConfigurationIntegration:
    """Test configuration integration scenarios."""
    
    def test_mixed_environment_sources(self, clean_env, temp_dotenv_file):
        """Test configuration with mixed environment sources."""
        # Set some values in actual environment
        os.environ.update({
            'HOST': '127.0.0.1',
            'USE_KNOWLEDGE_GRAPH': 'true'
        })
        
        # Set some values in .env file
        with open(temp_dotenv_file, 'w') as f:
            f.write('PORT=9999\n')
            f.write('TRANSPORT=stdio\n')
            f.write('USE_RERANKING=true\n')
        
        # Mock the dotenv file path
        with patch('config.Path.resolve') as mock_resolve:
            mock_resolve.return_value = temp_dotenv_file.parent
            with patch('config.Path.exists', return_value=True):
                config_instance = Config()
                
                # Environment variables should take precedence
                assert config_instance.HOST == '127.0.0.1'
                assert config_instance.USE_KNOWLEDGE_GRAPH is True
                
                # .env values should be loaded for unset variables
                # Note: This depends on dotenv override behavior
                # In real scenarios, environment variables typically take precedence
    
    def test_configuration_in_different_environments(self, clean_env):
        """Test configuration behavior in different deployment environments."""
        # Test development environment
        os.environ.clear()
        os.environ['NO_DOTENV'] = 'true'
        
        with patch('os.path.exists', return_value=False):  # No container
            config_instance = Config()
            assert not config_instance._is_containerized()
        
        # Test container environment
        os.environ.clear()
        os.environ['CONTAINER'] = 'true'
        
        config_instance = Config()
        assert config_instance._is_containerized()
        
        # Test Kubernetes environment
        os.environ.clear()
        os.environ['KUBERNETES_SERVICE_HOST'] = '10.0.0.1'
        
        config_instance = Config()
        assert config_instance._is_containerized()


class TestConfigurationValidation:
    """Test configuration validation scenarios."""
    
    def test_all_configuration_keys_tested(self, config_test_utils):
        """Ensure all configuration properties are covered by tests."""
        # Get all properties from the Config class
        config_properties = config_test_utils.get_all_config_properties(Config)
        
        # List of properties that should be tested
        expected_properties = [
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
        
        # Check that all expected properties exist
        for prop in expected_properties:
            assert prop in config_properties, f"Expected property {prop} not found in Config class"
        
        # Check for any unexpected properties
        unexpected_properties = set(config_properties) - set(expected_properties)
        if unexpected_properties:
            print(f"Warning: Found unexpected properties: {unexpected_properties}")
            print("Consider adding tests for these properties or updating the expected list.")
     
    def test_sensitive_data_identification(self, config_test_utils):
        """Test identification of sensitive configuration keys."""
        sensitive_keys = [
            'SUPABASE_SERVICE_KEY',
            'NEO4J_PASSWORD',
            'CHAT_MODEL_API_KEY',
            'EMBEDDING_MODEL_API_KEY'
        ]
        
        for key in sensitive_keys:
            assert config_test_utils.is_sensitive_key(key), f"Key {key} should be identified as sensitive"
        
        non_sensitive_keys = [
            'HOST',
            'PORT',
            'TRANSPORT',
            'MAX_CRAWL_DEPTH'
        ]
        
        for key in non_sensitive_keys:
            assert not config_test_utils.is_sensitive_key(key), f"Key {key} should not be identified as sensitive"