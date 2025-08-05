"""
Pytest configuration and fixtures for documentation processing tests.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock
import pytest
from supabase import Client


@pytest.fixture
def temp_repo_dir():
    """Create a temporary directory structure mimicking a repository."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)

        # Create various documentation files
        docs_dir = repo_path / "docs"
        docs_dir.mkdir()

        # README file
        (repo_path / "README.md").write_text(
            "# Test Repository\n\nThis is a test repository."
        )

        # API documentation
        (docs_dir / "api_reference.md").write_text(
            "# API Reference\n\nAPI documentation here."
        )

        # Tutorial
        (docs_dir / "getting_started.md").write_text(
            "# Getting Started\n\nTutorial content."
        )

        # Text file
        (repo_path / "LICENSE.txt").write_text("MIT License\n\nCopyright notice.")

        # RST file
        (docs_dir / "changelog.rst").write_text("Changelog\n=========\n\nVersion 1.0.0")

        # Large file (over 500KB)
        large_content = "x" * (600 * 1024)  # 600KB
        (repo_path / "large_file.md").write_text(large_content)

        # Directories to exclude
        (repo_path / "tests").mkdir()
        (repo_path / "tests" / "test_file.md").write_text("Test documentation")

        (repo_path / "__pycache__").mkdir()
        (repo_path / "node_modules").mkdir()
        (repo_path / "build").mkdir()

        yield repo_path


@pytest.fixture
def sample_notebook_content():
    """Sample Jupyter notebook content for testing."""
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Sample Notebook\n", "\n", "This is a test notebook."],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [],
                "source": ["import pandas as pd\n", "print('Hello world')"],
            },
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    mock_client = Mock(spec=Client)
    mock_table = Mock()

    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = Mock(data=[])

    return mock_client




@pytest.fixture
def repo_info():
    """Sample repository information."""
    return {"name": "test-repo", "url": "https://github.com/user/test-repo.git"}


@pytest.fixture
def doc_file_info():
    """Sample documentation file information."""
    return {
        "url": "docs/api.md",
        "markdown": "# API Documentation\n\nThis is API documentation.\n\n```python\nprint('hello')\n```",
    }


@pytest.fixture(autouse=True)
def reset_env_vars():
    """Reset environment variables after each test."""
    original_env = os.environ.copy()

    yield

    os.environ.clear()
    os.environ.update(original_env)