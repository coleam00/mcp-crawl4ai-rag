"""
Integration tests for container restart scenarios.

These tests verify that configuration changes are properly detected
and handled when containers restart with different environment variables.
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path for importing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from config import Config


class TestContainerRestart:
    """Test container restart scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        # Store original environment
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_configuration_changes_detected_on_restart(self):
        """Test that configuration changes are properly detected on container restart."""
        # Simulate first container startup
        initial_env = {
            'CONTAINER': 'true',
            'HOST': '0.0.0.0',
            'PORT': '8051',
            'CHAT_MODEL': 'gpt-4o-mini',
            'USE_RERANKING': 'false',
            'MAX_CONCURRENT_REQUESTS': '5'
        }
        
        os.environ.update(initial_env)
        
        # Create initial config
        config1 = Config()
        initial_host = config1.HOST
        initial_port = config1.PORT
        initial_model = config1.CHAT_MODEL
        initial_reranking = config1.USE_RERANKING
        initial_concurrent = config1.MAX_CONCURRENT_REQUESTS
        
        # Simulate container restart with different environment
        restart_env = {
            'CONTAINER': 'true',
            'HOST': '127.0.0.1',  # Changed
            'PORT': '9999',       # Changed
            'CHAT_MODEL': 'gpt-4o',  # Changed
            'USE_RERANKING': 'true',  # Changed
            'MAX_CONCURRENT_REQUESTS': '10'  # Changed
        }
        
        os.environ.update(restart_env)
        
        # Create new config instance (simulating restart)
        config2 = Config()
        
        # Verify changes are detected
        assert config2.HOST != initial_host
        assert config2.PORT != initial_port
        assert config2.CHAT_MODEL != initial_model
        assert config2.USE_RERANKING != initial_reranking
        assert config2.MAX_CONCURRENT_REQUESTS != initial_concurrent
        
        # Verify new values are correct
        assert config2.HOST == '127.0.0.1'
        assert config2.PORT == '9999'
        assert config2.CHAT_MODEL == 'gpt-4o'
        assert config2.USE_RERANKING == True
        assert config2.MAX_CONCURRENT_REQUESTS == 10

    def test_environment_variable_priority_in_containers(self):
        """Test that environment variables have correct priority in containers."""
        # Set container environment
        os.environ['CONTAINER'] = 'true'
        
        # Set both system defaults and specific values
        os.environ['DEFAULT_HOST'] = '192.168.1.1'
        os.environ['DEFAULT_PORT'] = '7777'
        os.environ['HOST'] = '10.0.0.1'
        os.environ['PORT'] = '8888'
        
        config = Config()
        
        # Specific values should override defaults
        assert config.HOST == '10.0.0.1'
        assert config.PORT == '8888'
        assert config.DEFAULT_HOST == '192.168.1.1'
        assert config.DEFAULT_PORT == '7777'

    def test_docker_environment_detection(self):
        """Test proper Docker environment detection."""
        with patch('os.path.exists') as mock_exists:
            # Mock /.dockerenv file exists
            mock_exists.return_value = True
            
            config = Config()
            
            # Should detect Docker environment
            assert config._is_containerized() == True
            mock_exists.assert_called_with('/.dockerenv')

    def test_kubernetes_environment_detection(self):
        """Test proper Kubernetes environment detection."""
        # Set Kubernetes service host
        os.environ['KUBERNETES_SERVICE_HOST'] = 'kubernetes.default.svc.cluster.local'
        
        config = Config()
        
        # Should detect Kubernetes environment
        assert config._is_containerized() == True

    def test_explicit_container_flag_detection(self):
        """Test explicit container flag detection."""
        os.environ['CONTAINER'] = 'true'
        
        with patch('os.path.exists', return_value=False):
            config = Config()
            
            # Should detect containerized environment via flag
            assert config._is_containerized() == True

    def test_mixed_container_indicators(self):
        """Test behavior with mixed container indicators."""
        # Set multiple indicators
        os.environ['CONTAINER'] = 'true'
        os.environ['KUBERNETES_SERVICE_HOST'] = 'kubernetes.default.svc'
        
        with patch('os.path.exists', return_value=True):  # /.dockerenv exists
            config = Config()
            
            # Should detect containerized environment
            assert config._is_containerized() == True

    def test_no_env_file_loading_in_any_container_environment(self):
        """Test that .env files are never loaded in any container environment."""
        container_environments = [
            {'CONTAINER': 'true'},
            {'KUBERNETES_SERVICE_HOST': 'kubernetes.default.svc'},
            # Docker environment tested via file existence mock
        ]
        
        for env_vars in container_environments:
            # Clear environment and set container indicator
            os.environ.clear()
            os.environ.update(self.original_env)
            os.environ.update(env_vars)
            
            with patch('config.load_dotenv') as mock_load_dotenv:
                with patch('os.path.exists', return_value=False):
                    config = Config()
                    
                    # Should not attempt to load .env file
                    mock_load_dotenv.assert_not_called()

    def test_docker_compose_service_names(self):
        """Test configuration for Docker Compose service names."""
        # Simulate Docker Compose environment
        os.environ['CONTAINER'] = 'true'
        os.environ['EMBEDDING_MODEL_API_BASE'] = 'http://ollama:11434/v1'
        os.environ['NEO4J_URI'] = 'bolt://neo4j:7687'
        
        config = Config()
        
        # Should use service names instead of localhost
        assert config.EMBEDDING_MODEL_API_BASE == 'http://ollama:11434/v1'
        assert config.NEO4J_URI == 'bolt://neo4j:7687'

    def test_container_restart_with_new_feature_flags(self):
        """Test container restart with new feature flags enabled."""
        # Initial startup with features disabled
        initial_env = {
            'CONTAINER': 'true',
            'USE_RERANKING': 'false',
            'USE_HYBRID_SEARCH': 'false',
            'USE_AGENTIC_RAG': 'false',
            'USE_KNOWLEDGE_GRAPH': 'false',
            'USE_CHAT_MODEL_FALLBACK': 'false',
            'USE_EMBEDDING_MODEL_FALLBACK': 'false'
        }
        
        os.environ.update(initial_env)
        config1 = Config()
        
        # Verify initial state
        assert config1.USE_RERANKING == False
        assert config1.USE_HYBRID_SEARCH == False
        assert config1.USE_AGENTIC_RAG == False
        assert config1.USE_KNOWLEDGE_GRAPH == False
        assert config1.USE_CHAT_MODEL_FALLBACK == False
        assert config1.USE_EMBEDDING_MODEL_FALLBACK == False
        
        # Restart with features enabled
        restart_env = {
            'CONTAINER': 'true',
            'USE_RERANKING': 'true',
            'USE_HYBRID_SEARCH': 'true',
            'USE_AGENTIC_RAG': 'true',
            'USE_KNOWLEDGE_GRAPH': 'true',
            'USE_CHAT_MODEL_FALLBACK': 'true',
            'USE_EMBEDDING_MODEL_FALLBACK': 'true'
        }
        
        os.environ.update(restart_env)
        config2 = Config()
        
        # Verify features are now enabled
        assert config2.USE_RERANKING == True
        assert config2.USE_HYBRID_SEARCH == True
        assert config2.USE_AGENTIC_RAG == True
        assert config2.USE_KNOWLEDGE_GRAPH == True
        assert config2.USE_CHAT_MODEL_FALLBACK == True
        assert config2.USE_EMBEDDING_MODEL_FALLBACK == True

    def test_container_restart_with_performance_tuning(self):
        """Test container restart with different performance settings."""
        # Initial performance settings
        initial_env = {
            'CONTAINER': 'true',
            'MAX_CONCURRENT_REQUESTS': '5',
            'RATE_LIMIT_DELAY': '0.5',
            'CIRCUIT_BREAKER_THRESHOLD': '3',
            'REQUEST_TIMEOUT': '30',
            'MAX_WORKERS_SUMMARY': '1',
            'SUPABASE_BATCH_SIZE': '2'
        }
        
        os.environ.update(initial_env)
        config1 = Config()
        
        # Restart with tuned performance settings
        restart_env = {
            'CONTAINER': 'true',
            'MAX_CONCURRENT_REQUESTS': '10',
            'RATE_LIMIT_DELAY': '1.0',
            'CIRCUIT_BREAKER_THRESHOLD': '5',
            'REQUEST_TIMEOUT': '60',
            'MAX_WORKERS_SUMMARY': '2',
            'SUPABASE_BATCH_SIZE': '5'
        }
        
        os.environ.update(restart_env)
        config2 = Config()
        
        # Verify performance settings changed
        assert config2.MAX_CONCURRENT_REQUESTS == 10
        assert config2.RATE_LIMIT_DELAY == 1.0
        assert config2.CIRCUIT_BREAKER_THRESHOLD == 5
        assert config2.REQUEST_TIMEOUT == 60
        assert config2.MAX_WORKERS_SUMMARY == 2
        # Note: SUPABASE_BATCH_SIZE is not in the current config class

    def test_container_restart_with_model_changes(self):
        """Test container restart with different AI models."""
        # Initial model configuration
        initial_env = {
            'CONTAINER': 'true',
            'CHAT_MODEL': 'gpt-4o-mini',
            'EMBEDDING_MODEL': 'text-embedding-3-small',
            'RERANKING_MODEL': 'cross-encoder/ms-marco-MiniLM-L-6-v2'
        }
        
        os.environ.update(initial_env)
        config1 = Config()
        
        # Restart with different models
        restart_env = {
            'CONTAINER': 'true',
            'CHAT_MODEL': 'qwen3:latest',
            'EMBEDDING_MODEL': 'dengcao/Qwen3-Embedding-0.6B:Q8_0',
            'RERANKING_MODEL': 'cross-encoder/ms-marco-MiniLM-L-12-v2'
        }
        
        os.environ.update(restart_env)
        config2 = Config()
        
        # Verify model changes
        assert config2.CHAT_MODEL == 'qwen3:latest'
        assert config2.EMBEDDING_MODEL == 'dengcao/Qwen3-Embedding-0.6B:Q8_0'
        assert config2.RERANKING_MODEL == 'cross-encoder/ms-marco-MiniLM-L-12-v2'

    def test_container_restart_preserves_unset_defaults(self):
        """Test that unset variables still use defaults after restart."""
        # Set container environment with minimal configuration
        os.environ.clear()
        os.environ.update(self.original_env)
        os.environ['CONTAINER'] = 'true'
        # Deliberately not setting most variables
        
        config = Config()
        
        # Should use default values for unset variables
        assert config.HOST == '0.0.0.0'  # DEFAULT_HOST
        assert config.PORT == '8051'     # DEFAULT_PORT
        assert config.TRANSPORT == 'sse'
        assert config.CHAT_MODEL == 'gpt-4o-mini'
        assert config.EMBEDDING_MODEL == 'text-embedding-3-small'
        assert config.MAX_CONCURRENT_REQUESTS == 5
        assert config.RATE_LIMIT_DELAY == 0.5

    def test_container_restart_with_invalid_values(self):
        """Test container restart with invalid environment values."""
        os.environ['CONTAINER'] = 'true'
        os.environ['MAX_CONCURRENT_REQUESTS'] = 'invalid'
        os.environ['RATE_LIMIT_DELAY'] = 'not_a_number'
        
        config = Config()
        
        # Should raise ValueError for invalid numeric values
        with pytest.raises(ValueError):
            _ = config.MAX_CONCURRENT_REQUESTS
            
        with pytest.raises(ValueError):
            _ = config.RATE_LIMIT_DELAY

    def test_container_restart_environment_isolation(self):
        """Test that each container restart creates isolated configuration."""
        # First container instance
        os.environ['CONTAINER'] = 'true'
        os.environ['HOST'] = '192.168.1.1'
        config1 = Config()
        host1 = config1.HOST
        
        # Change environment (simulating different container)
        os.environ['HOST'] = '10.0.0.1'
        config2 = Config()
        host2 = config2.HOST
        
        # Configurations should be independent
        assert host1 == '192.168.1.1'
        assert host2 == '10.0.0.1'
        assert host1 != host2

    def test_container_with_legacy_and_new_variables(self):
        """Test container restart with both legacy and new configuration variables."""
        # Set both old and new style variables
        os.environ['CONTAINER'] = 'true'
        
        # Legacy variables (should still work)
        os.environ['MAX_WORKERS_SUMMARY'] = '3'
        
        # New rate limiting variables
        os.environ['MAX_CONCURRENT_REQUESTS'] = '8'
        os.environ['RATE_LIMIT_DELAY'] = '0.75'
        os.environ['CIRCUIT_BREAKER_THRESHOLD'] = '4'
        
        config = Config()
        
        # Both should be accessible
        assert config.MAX_WORKERS_SUMMARY == 3
        assert config.MAX_CONCURRENT_REQUESTS == 8
        assert config.RATE_LIMIT_DELAY == 0.75
        assert config.CIRCUIT_BREAKER_THRESHOLD == 4