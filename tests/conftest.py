"""
Pytest configuration and fixtures for the Crawl4AI MCP test suite.

This module provides shared fixtures and test utilities for testing
the configuration system and other components.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Generator
from unittest.mock import patch, MagicMock

import pytest


# Add src directory to Python path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def clean_env() -> Generator[Dict[str, str], None, None]:
    """
    Fixture that provides a clean environment for testing.
    
    Stores the current environment variables and restores them after the test,
    allowing tests to modify environment variables without affecting other tests.
    """
    original_env = dict(os.environ)
    try:
        yield original_env
    finally:
        # Clear all current env vars
        os.environ.clear()
        # Restore original environment
        os.environ.update(original_env)


@pytest.fixture
def mock_env() -> Generator[Dict[str, str], None, None]:
    """
    Fixture that provides a mock environment dictionary.
    
    Returns an empty environment that can be populated by tests
    without affecting the actual system environment.
    """
    env_vars = {}
    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars


@pytest.fixture
def temp_dotenv_file() -> Generator[Path, None, None]:
    """
    Fixture that creates a temporary .env file for testing.
    
    Creates a temporary .env file that can be used to test
    environment variable loading from files.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        dotenv_path = Path(f.name)
        yield dotenv_path
    
    # Cleanup
    if dotenv_path.exists():
        dotenv_path.unlink()


@pytest.fixture
def mock_docker_env():
    """
    Fixture that mocks a Docker container environment.
    
    Creates the necessary files and environment variables to simulate
    running inside a Docker container.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock .dockerenv file
        dockerenv_path = Path(temp_dir) / '.dockerenv'
        dockerenv_path.touch()
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            yield temp_dir


@pytest.fixture
def mock_kubernetes_env() -> Generator[None, None, None]:
    """
    Fixture that mocks a Kubernetes environment.
    
    Sets the KUBERNETES_SERVICE_HOST environment variable to simulate
    running inside a Kubernetes pod.
    """
    with patch.dict(os.environ, {'KUBERNETES_SERVICE_HOST': '10.0.0.1'}):
        yield


@pytest.fixture
def sample_config_values() -> Dict[str, Any]:
    """
    Fixture that provides sample configuration values for testing.
    
    Returns a dictionary of configuration values that can be used
    in tests to verify proper loading and type conversion.
    """
    return {
        # Server Configuration
        'HOST': '127.0.0.1',
        'PORT': '9000',
        'DEFAULT_HOST': '0.0.0.0',
        'DEFAULT_PORT': '8051',
        'TRANSPORT': 'stdio',
        
        # Model Configuration
        'RERANKING_MODEL': 'custom-reranker',
        'CHAT_MODEL': 'gpt-4',
        'EMBEDDING_MODEL': 'text-embedding-ada-002',
        
        # Timeout Configuration
        'OLLAMA_CHECK_TIMEOUT': '10',
        'REPO_ANALYSIS_TIMEOUT': '3600',
        'REQUEST_TIMEOUT': '60',
        
        # Database Configuration
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_KEY': 'test-service-key',
        'NEO4J_URI': 'bolt://localhost:7687',
        'NEO4J_USER': 'neo4j',
        'NEO4J_PASSWORD': 'password',
        
        # Feature Flags
        'USE_KNOWLEDGE_GRAPH': 'true',
        'USE_RERANKING': 'true',
        'USE_HYBRID_SEARCH': 'false',
        'USE_AGENTIC_RAG': 'true',
        'USE_CHAT_MODEL_FALLBACK': 'false',
        'USE_EMBEDDING_MODEL_FALLBACK': 'true',
        
        # Performance Configuration
        'MAX_CRAWL_DEPTH': '5',
        'MAX_CONCURRENT_CRAWLS': '20',
        'CHUNK_SIZE': '8000',
        'DEFAULT_MATCH_COUNT': '10',
        'MAX_WORKERS_SUMMARY': '5',
        'MAX_WORKERS_SOURCE_SUMMARY': '3',
        
        # Rate Limiting
        'MAX_CONCURRENT_REQUESTS': '10',
        'RATE_LIMIT_DELAY': '1.0',
        'CIRCUIT_BREAKER_THRESHOLD': '5',
        'CLIENT_CACHE_TTL': '7200',
        
        # API Configuration
        'EMBEDDING_MODEL_API_BASE': 'https://api.example.com/v1',
    }


@pytest.fixture
def sensitive_config_values() -> Dict[str, str]:
    """
    Fixture that provides sensitive configuration values for testing masking.
    
    Returns a dictionary of sensitive values that should be masked
    in logs and error messages.
    """
    return {
        'SUPABASE_SERVICE_KEY': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test',
        'NEO4J_PASSWORD': 'super-secret-password',
        'CHAT_MODEL_API_KEY': 'sk-1234567890abcdef',
        'EMBEDDING_MODEL_API_KEY': 'sk-abcdef1234567890',
        'CHAT_MODEL_FALLBACK_API_KEY': 'sk-fallback-key-123',
        'EMBEDDING_MODEL_FALLBACK_API_KEY': 'sk-fallback-embed-456',
    }


@pytest.fixture
def mock_dotenv():
    """
    Fixture that mocks the dotenv library functionality.
    
    Provides a mock implementation of python-dotenv that can be used
    to test behavior when the library is available or unavailable.
    """
    mock_load_dotenv = MagicMock()
    
    with patch.dict('sys.modules', {'dotenv': MagicMock()}):
        with patch('dotenv.load_dotenv', mock_load_dotenv):
            yield mock_load_dotenv


@pytest.fixture
def config_with_defaults():
    """
    Fixture that provides a Config instance with default values.
    
    Creates a Config instance in a clean environment to test
    default value behavior.
    """
    from config import Config
    
    with patch.dict(os.environ, {}, clear=True):
        # Disable dotenv loading for predictable defaults
        with patch.dict(os.environ, {'NO_DOTENV': 'true'}):
            config = Config()
            yield config


@pytest.fixture
def invalid_config_values() -> Dict[str, str]:
    """
    Fixture that provides invalid configuration values for testing validation.
    
    Returns a dictionary of invalid values that should trigger
    validation errors or type conversion failures.
    """
    return {
        'OLLAMA_CHECK_TIMEOUT': 'not-a-number',
        'RATE_LIMIT_DELAY': 'invalid-float',
        'MAX_CONCURRENT_REQUESTS': 'negative-five',
        'USE_KNOWLEDGE_GRAPH': 'maybe',
        'PORT': 'http',
    }


# Test utilities
class ConfigTestUtils:
    """Utility class providing helper methods for configuration testing."""
    
    @staticmethod
    def set_env_vars(env_dict: Dict[str, str]) -> None:
        """Set multiple environment variables."""
        for key, value in env_dict.items():
            os.environ[key] = value
    
    @staticmethod
    def clear_env_vars(keys: list) -> None:
        """Clear specific environment variables."""
        for key in keys:
            os.environ.pop(key, None)
    
    @staticmethod
    def get_all_config_properties(config_class) -> list:
        """Get all property names from a config class."""
        return [
            name for name in dir(config_class)
            if isinstance(getattr(config_class, name), property)
            and not name.startswith('_')
        ]
    
    @staticmethod
    def is_sensitive_key(key: str) -> bool:
        """Check if a configuration key contains sensitive data."""
        sensitive_patterns = [
            'KEY', 'PASSWORD', 'SECRET', 'TOKEN', 'CREDENTIAL'
        ]
        return any(pattern in key.upper() for pattern in sensitive_patterns)


@pytest.fixture
def config_test_utils():
    """Fixture that provides the ConfigTestUtils class."""
    return ConfigTestUtils