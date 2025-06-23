"""
Integration tests for environment variable loading behavior.

These tests verify that the configuration system properly loads environment
variables from different sources and handles various edge cases.
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

# Add src to path for importing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from config import Config


class TestEnvLoading:
    """Test environment loading behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        # Store original environment
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_env_file_loading_in_development(self):
        """Test .env file loading in development environment."""
        # Clear container indicators
        for key in ['CONTAINER', 'KUBERNETES_SERVICE_HOST']:
            os.environ.pop(key, None)
        
        # Create temporary .env content
        env_content = """HOST=127.0.0.1
PORT=9999
CHAT_MODEL=test-model
EMBEDDING_MODEL=test-embedding
USE_RERANKING=true
MAX_CONCURRENT_REQUESTS=10
RATE_LIMIT_DELAY=1.5
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / '.env'
            env_file.write_text(env_content)
            
            # Mock path resolution to point to our temp directory
            with patch('config.Path') as mock_path:
                # Make Path(__file__).resolve().parent.parent return temp_dir
                mock_path.return_value.resolve.return_value.parent.parent = Path(temp_dir)
                
                # Mock the existence check and dotenv loading
                with patch('config.load_dotenv') as mock_load_dotenv:
                    # Mock successful dotenv import and loading
                    mock_load_dotenv.return_value = None
                    
                    # Mock path.exists() to return True for our temp .env file
                    with patch.object(Path, 'exists', return_value=True):
                        config = Config()
                        
                        # Verify dotenv was called
                        mock_load_dotenv.assert_called_once()

    def test_env_file_not_loaded_in_container(self):
        """Test that .env file is not loaded in containerized environment."""
        # Create Docker container indicator
        with tempfile.NamedTemporaryFile(mode='w', suffix='/.dockerenv', delete=False) as f:
            dockerenv_path = f.name
        
        try:
            with patch('os.path.exists') as mock_exists:
                def mock_exists_side_effect(path):
                    if path == '/.dockerenv':
                        return True
                    return False
                
                mock_exists.side_effect = mock_exists_side_effect
                
                with patch('config.load_dotenv') as mock_load_dotenv:
                    config = Config()
                    
                    # Verify dotenv was NOT called in container
                    mock_load_dotenv.assert_not_called()
        finally:
            # Clean up temp file
            try:
                os.unlink(dockerenv_path)
            except:
                pass

    def test_container_detection_docker(self):
        """Test container detection with Docker environment."""
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True  # /.dockerenv exists
            
            config = Config()
            assert config._is_containerized() == True

    def test_container_detection_kubernetes(self):
        """Test container detection with Kubernetes environment."""
        os.environ['KUBERNETES_SERVICE_HOST'] = 'kubernetes.default.svc'
        
        config = Config()
        assert config._is_containerized() == True

    def test_container_detection_explicit_flag(self):
        """Test container detection with explicit CONTAINER flag."""
        os.environ['CONTAINER'] = 'true'
        
        config = Config()
        assert config._is_containerized() == True

    def test_no_container_detection(self):
        """Test that container detection returns False in normal environment."""
        # Ensure no container indicators
        for key in ['CONTAINER', 'KUBERNETES_SERVICE_HOST']:
            os.environ.pop(key, None)
        
        with patch('os.path.exists', return_value=False):
            config = Config()
            assert config._is_containerized() == False

    def test_environment_variable_precedence(self):
        """Test that environment variables take precedence over .env file."""
        # Set environment variable directly
        os.environ['HOST'] = '192.168.1.100'
        os.environ['PORT'] = '7777'
        
        # Mock .env file with different values
        env_content = """HOST=127.0.0.1
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
                        
                        # Environment variables should take precedence
                        assert config.HOST == '192.168.1.100'
                        assert config.PORT == '7777'

    def test_missing_env_file_handling(self):
        """Test behavior when .env file doesn't exist."""
        # Clear container indicators
        for key in ['CONTAINER', 'KUBERNETES_SERVICE_HOST']:
            os.environ.pop(key, None)
        
        with patch('os.path.exists', return_value=False):
            with patch('config.load_dotenv') as mock_load_dotenv:
                config = Config()
                
                # Should not attempt to load non-existent file
                mock_load_dotenv.assert_not_called()
                
                # Should use defaults
                assert config.HOST == config.DEFAULT_HOST
                assert config.PORT == config.DEFAULT_PORT

    def test_malformed_env_file_handling(self):
        """Test behavior with malformed .env file."""
        # Clear container indicators
        for key in ['CONTAINER', 'KUBERNETES_SERVICE_HOST']:
            os.environ.pop(key, None)
        
        # Mock dotenv raising an exception
        with patch('config.load_dotenv', side_effect=Exception("Malformed .env file")):
            with patch.object(Path, 'exists', return_value=True):
                config = Config()
                
                # Should continue with defaults despite error
                assert config.HOST == config.DEFAULT_HOST
                assert config.PORT == config.DEFAULT_PORT

    def test_dotenv_import_error_handling(self):
        """Test behavior when dotenv package is not available."""
        # Clear container indicators
        for key in ['CONTAINER', 'KUBERNETES_SERVICE_HOST']:
            os.environ.pop(key, None)
        
        # Mock ImportError for dotenv
        with patch('builtins.__import__', side_effect=ImportError("No module named 'dotenv'")):
            config = Config()
            
            # Should continue with system environment variables
            assert config.HOST == config.DEFAULT_HOST
            assert config.PORT == config.DEFAULT_PORT

    def test_no_dotenv_flag(self):
        """Test that NO_DOTENV flag prevents .env file loading."""
        os.environ['NO_DOTENV'] = '1'
        
        # Clear container indicators
        for key in ['CONTAINER', 'KUBERNETES_SERVICE_HOST']:
            os.environ.pop(key, None)
        
        with patch('config.load_dotenv') as mock_load_dotenv:
            config = Config()
            
            # Should not load .env due to NO_DOTENV flag
            mock_load_dotenv.assert_not_called()

    def test_boolean_environment_variables(self):
        """Test proper parsing of boolean environment variables."""
        test_cases = [
            ('true', True),
            ('True', True), 
            ('TRUE', True),
            ('false', False),
            ('False', False),
            ('FALSE', False),
            ('1', False),  # Only 'true' (case-insensitive) should be True
            ('0', False),
            ('yes', False),
            ('', False),
        ]
        
        for env_value, expected in test_cases:
            os.environ['USE_RERANKING'] = env_value
            config = Config()
            assert config.USE_RERANKING == expected, f"Expected {expected} for value '{env_value}'"

    def test_integer_environment_variables(self):
        """Test proper parsing of integer environment variables."""
        test_cases = [
            ('5', 5),
            ('0', 0),
            ('1000', 1000),
        ]
        
        for env_value, expected in test_cases:
            os.environ['MAX_CONCURRENT_REQUESTS'] = env_value
            config = Config()
            assert config.MAX_CONCURRENT_REQUESTS == expected

    def test_integer_environment_variables_invalid(self):
        """Test behavior with invalid integer environment variables."""
        os.environ['MAX_CONCURRENT_REQUESTS'] = 'not_a_number'
        
        # Should raise ValueError when trying to convert
        config = Config()
        with pytest.raises(ValueError):
            _ = config.MAX_CONCURRENT_REQUESTS

    def test_float_environment_variables(self):
        """Test proper parsing of float environment variables."""
        test_cases = [
            ('0.5', 0.5),
            ('1.0', 1.0),
            ('2.75', 2.75),
        ]
        
        for env_value, expected in test_cases:
            os.environ['RATE_LIMIT_DELAY'] = env_value
            config = Config()
            assert config.RATE_LIMIT_DELAY == expected

    def test_float_environment_variables_invalid(self):
        """Test behavior with invalid float environment variables."""
        os.environ['RATE_LIMIT_DELAY'] = 'not_a_float'
        
        # Should raise ValueError when trying to convert
        config = Config()
        with pytest.raises(ValueError):
            _ = config.RATE_LIMIT_DELAY

    def test_optional_environment_variables(self):
        """Test behavior of optional environment variables."""
        # Clear optional variables
        for key in ['SUPABASE_URL', 'NEO4J_URI', 'EMBEDDING_MODEL_API_BASE']:
            os.environ.pop(key, None)
        
        config = Config()
        
        # Optional variables should return None when not set
        assert config.SUPABASE_URL is None
        assert config.NEO4J_URI is None
        assert config.EMBEDDING_MODEL_API_BASE is None

    def test_required_environment_variables_with_defaults(self):
        """Test that required variables fall back to defaults when not set."""
        # Clear variables that have defaults
        for key in ['HOST', 'PORT', 'CHAT_MODEL', 'EMBEDDING_MODEL']:
            os.environ.pop(key, None)
        
        config = Config()
        
        # Should use default values
        assert config.HOST == '0.0.0.0'
        assert config.PORT == '8051'
        assert config.CHAT_MODEL == 'gpt-4o-mini'
        assert config.EMBEDDING_MODEL == 'text-embedding-3-small'