"""
Unit tests for documentation processing functions.
"""

import json
import tempfile
from pathlib import Path
import pytest

from src.utils import (
    discover_documentation_files,
    process_document_files,
    create_repository_source_id,
    create_documentation_url,
    create_documentation_metadata,
    process_repository_docs,
)


class TestDiscoverDocumentationFiles:
    """Tests for discover_documentation_files function."""

    def test_discover_documentation_files_basic(self, temp_repo_dir):
        """Test basic file discovery with valid markdown and text files."""
        doc_files = discover_documentation_files(temp_repo_dir)

        # Convert to relative paths for easier assertion
        relative_paths = [str(f.relative_to(temp_repo_dir)) for f in doc_files]

        assert "README.md" in relative_paths
        assert "LICENSE.txt" in relative_paths
        assert "docs/api_reference.md" in relative_paths
        assert "docs/getting_started.md" in relative_paths
        assert "docs/changelog.rst" in relative_paths

        # Should exclude large file
        assert "large_file.md" not in relative_paths

    def test_discover_documentation_files_excludes_directories(self, temp_repo_dir):
        """Test that excluded directories are properly filtered out."""
        doc_files = discover_documentation_files(temp_repo_dir)
        relative_paths = [str(f.relative_to(temp_repo_dir)) for f in doc_files]

        # Should not include files from excluded directories
        assert "tests/test_file.md" not in relative_paths
        assert not any("__pycache__" in path for path in relative_paths)
        assert not any("node_modules" in path for path in relative_paths)
        assert not any("build" in path for path in relative_paths)

    def test_discover_documentation_files_includes_all_extensions(self, temp_repo_dir):
        """Test discovery of .md, .rst, .txt, .mdx, .ipynb files."""
        # Add additional file types
        (temp_repo_dir / "test.mdx").write_text("# MDX file")

        # Create a sample notebook
        notebook_content = {
            "cells": [],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 4,
        }
        (temp_repo_dir / "notebook.ipynb").write_text(json.dumps(notebook_content))

        doc_files = discover_documentation_files(temp_repo_dir)
        relative_paths = [str(f.relative_to(temp_repo_dir)) for f in doc_files]

        # Check all extensions are included
        assert any(path.endswith(".md") for path in relative_paths)
        assert any(path.endswith(".rst") for path in relative_paths)
        assert any(path.endswith(".txt") for path in relative_paths)
        assert "test.mdx" in relative_paths
        assert "notebook.ipynb" in relative_paths

    def test_discover_documentation_files_excludes_large_files(self, temp_repo_dir):
        """Test that files larger than 500KB are excluded."""
        doc_files = discover_documentation_files(temp_repo_dir)
        relative_paths = [str(f.relative_to(temp_repo_dir)) for f in doc_files]

        # Large file should be excluded
        assert "large_file.md" not in relative_paths

        # Regular files should be included
        assert "README.md" in relative_paths

    def test_discover_documentation_files_handles_missing_path(self):
        """Test graceful handling when repository path doesn't exist."""
        non_existent_path = Path("/non/existent/path")
        doc_files = discover_documentation_files(non_existent_path)

        assert doc_files == []

    def test_discover_documentation_files_handles_permission_errors(self, mocker):
        """Test handling of files that can't be accessed."""
        # Mock os.walk to raise permission error
        mock_walk = mocker.patch("os.walk")
        mock_walk.side_effect = PermissionError("Permission denied")

        with tempfile.TemporaryDirectory() as temp_dir:
            doc_files = discover_documentation_files(Path(temp_dir))
            assert doc_files == []


class TestProcessDocumentFiles:
    """Tests for process_document_files function."""

    def test_process_document_files_basic_markdown(self, temp_repo_dir):
        """Test processing regular markdown files."""
        doc_files = [
            temp_repo_dir / "README.md",
            temp_repo_dir / "docs" / "api_reference.md",
        ]

        result = process_document_files(doc_files, temp_repo_dir)

        assert len(result) == 2

        # Check structure
        readme_doc = next(doc for doc in result if doc["url"] == "README.md")
        assert "# Test Repository" in readme_doc["markdown"]

        api_doc = next(doc for doc in result if doc["url"] == "docs/api_reference.md")
        assert "# API Reference" in api_doc["markdown"]

    def test_process_document_files_jupyter_notebook(
        self, temp_repo_dir, sample_notebook_content
    ):
        """Test processing Jupyter notebooks."""
        # Create a notebook file
        notebook_path = temp_repo_dir / "test_notebook.ipynb"
        notebook_path.write_text(json.dumps(sample_notebook_content))

        doc_files = [notebook_path]

        result = process_document_files(doc_files, temp_repo_dir)

        assert len(result) == 1
        assert result[0]["url"] == "test_notebook.ipynb"
        # Check that the notebook content was converted to markdown
        assert "# Sample Notebook" in result[0]["markdown"]
        assert "```python" in result[0]["markdown"]
        assert "import pandas as pd" in result[0]["markdown"]

    def test_process_document_files_mixed_file_types(self, temp_repo_dir):
        """Test processing a mix of .md, .rst, .txt files."""
        doc_files = [
            temp_repo_dir / "README.md",
            temp_repo_dir / "LICENSE.txt",
            temp_repo_dir / "docs" / "changelog.rst",
        ]

        result = process_document_files(doc_files, temp_repo_dir)

        assert len(result) == 3
        urls = [doc["url"] for doc in result]
        assert "README.md" in urls
        assert "LICENSE.txt" in urls
        assert "docs/changelog.rst" in urls

    def test_process_document_files_handles_encoding_errors(
        self, temp_repo_dir, mocker
    ):
        """Test graceful handling of files with encoding issues."""
        # Create a file and mock open to raise UnicodeDecodeError
        bad_file = temp_repo_dir / "bad_encoding.md"
        bad_file.write_text("Good content")

        doc_files = [bad_file]

        # Mock open to raise encoding error
        mock_builtin_open = mocker.patch("builtins.open")
        mock_builtin_open.side_effect = UnicodeDecodeError(
            "utf-8", b"", 0, 1, "invalid start byte"
        )

        result = process_document_files(doc_files, temp_repo_dir)

        # Should handle error gracefully and return empty list
        assert result == []

    def test_process_document_files_handles_malformed_notebook(self, temp_repo_dir):
        """Test handling of malformed notebook files."""
        # Create a malformed notebook file
        notebook_path = temp_repo_dir / "bad_notebook.ipynb"
        notebook_path.write_text("{ invalid json }")

        doc_files = [notebook_path]

        result = process_document_files(doc_files, temp_repo_dir)

        # Should handle error gracefully and return empty result
        assert result == []

    def test_process_document_files_empty_list(self, temp_repo_dir):
        """Test behavior with empty file list."""
        result = process_document_files([], temp_repo_dir)
        assert result == []


class TestCreateRepositorySourceId:
    """Tests for create_repository_source_id function."""

    def test_create_repository_source_id_github_https(self):
        """Test with standard GitHub HTTPS URL."""
        repo_url = "https://github.com/user/repo.git"
        result = create_repository_source_id(repo_url)
        assert result == "github.com/user/repo"

    def test_create_repository_source_id_github_ssh(self):
        """Test with GitHub SSH URL."""
        repo_url = "git@github.com:user/repo.git"
        result = create_repository_source_id(repo_url)
        # SSH URLs should normalize to the same format as HTTPS URLs
        assert result == "github.com/user/repo"

    def test_create_repository_source_id_removes_git_suffix(self):
        """Test that .git suffix is properly removed."""
        repo_url = "https://github.com/user/repo.git"
        result = create_repository_source_id(repo_url)
        assert not result.endswith(".git")
        assert result == "github.com/user/repo"

    def test_create_repository_source_id_consistency_ssh_https(self):
        """Test that SSH and HTTPS URLs for the same repo generate the same source ID."""
        https_url = "https://github.com/user/repo.git"
        ssh_url = "git@github.com:user/repo.git"
        
        https_result = create_repository_source_id(https_url)
        ssh_result = create_repository_source_id(ssh_url)
        
        assert https_result == ssh_result == "github.com/user/repo"

    def test_create_repository_source_id_handles_malformed_urls(self):
        """Test fallback behavior with invalid URLs."""
        malformed_url = "not-a-valid-url"
        result = create_repository_source_id(malformed_url)
        assert result == "not-a-valid-url"

    def test_create_repository_source_id_other_git_hosts(self):
        """Test with GitLab, Bitbucket URLs."""
        gitlab_url = "https://gitlab.com/user/repo.git"
        result = create_repository_source_id(gitlab_url)
        assert result == "gitlab.com/user/repo"

        bitbucket_url = "https://bitbucket.org/user/repo.git"
        result = create_repository_source_id(bitbucket_url)
        assert result == "bitbucket.org/user/repo"


class TestCreateDocumentationUrl:
    """Tests for create_documentation_url function."""

    def test_create_documentation_url_basic(self):
        """Test basic URL creation with repo URL and doc path."""
        repo_url = "https://github.com/user/repo.git"
        doc_path = "README.md"
        result = create_documentation_url(repo_url, doc_path)
        assert result == "github.com/user/repo/README.md"

    def test_create_documentation_url_removes_git_suffix(self):
        """Test that .git suffix is handled correctly."""
        repo_url = "https://github.com/user/repo.git"
        doc_path = "docs/api.md"
        result = create_documentation_url(repo_url, doc_path)
        assert result == "github.com/user/repo/docs/api.md"
        assert ".git" not in result

    def test_create_documentation_url_nested_paths(self):
        """Test with nested documentation paths."""
        repo_url = "https://github.com/user/repo.git"
        doc_path = "docs/api/reference.md"
        result = create_documentation_url(repo_url, doc_path)
        assert result == "github.com/user/repo/docs/api/reference.md"

    def test_create_documentation_url_handles_malformed_urls(self):
        """Test fallback behavior with invalid URLs."""
        malformed_url = "not-a-valid-url"
        doc_path = "README.md"
        result = create_documentation_url(malformed_url, doc_path)
        assert result == "not-a-valid-url/README.md"


class TestCreateDocumentationMetadata:
    """Tests for create_documentation_metadata function."""

    def test_create_documentation_metadata_readme_detection(self, repo_info):
        """Test that README files are categorized correctly."""
        doc_file_info = {"url": "README.md", "markdown": "# Test README"}
        result = create_documentation_metadata(doc_file_info, repo_info)

        assert result["documentation_category"] == "readme"
        assert result["file_type"] == "md"
        assert result["repository_name"] == "test-repo"

    def test_create_documentation_metadata_api_detection(self, repo_info):
        """Test API documentation detection."""
        doc_file_info = {"url": "docs/api_reference.md", "markdown": "# API Reference"}
        result = create_documentation_metadata(doc_file_info, repo_info)

        assert result["documentation_category"] == "api"

    def test_create_documentation_metadata_tutorial_detection(self, repo_info):
        """Test tutorial/guide detection."""
        doc_file_info = {
            "url": "docs/getting_started.md",
            "markdown": "# Getting Started",
        }
        result = create_documentation_metadata(doc_file_info, repo_info)

        assert result["documentation_category"] == "tutorial"

    def test_create_documentation_metadata_changelog_detection(self, repo_info):
        """Test changelog detection."""
        doc_file_info = {"url": "CHANGELOG.md", "markdown": "# Changelog"}
        result = create_documentation_metadata(doc_file_info, repo_info)

        assert result["documentation_category"] == "changelog"

    def test_create_documentation_metadata_license_detection(self, repo_info):
        """Test license file detection."""
        doc_file_info = {"url": "LICENSE.txt", "markdown": "MIT License"}
        result = create_documentation_metadata(doc_file_info, repo_info)

        assert result["documentation_category"] == "license"

    def test_create_documentation_metadata_contributing_detection(self, repo_info):
        """Test contributing guide detection."""
        doc_file_info = {"url": "CONTRIBUTING.md", "markdown": "# Contributing"}
        result = create_documentation_metadata(doc_file_info, repo_info)

        assert result["documentation_category"] == "contributing"

    def test_create_documentation_metadata_generic_documentation(self, repo_info):
        """Test fallback to generic 'documentation' category."""
        doc_file_info = {"url": "docs/other.md", "markdown": "# Other Documentation"}
        result = create_documentation_metadata(doc_file_info, repo_info)

        assert result["documentation_category"] == "documentation"

    def test_create_documentation_metadata_code_example_counting(
        self, repo_info, mocker, monkeypatch
    ):
        """Test code example counting when USE_AGENTIC_RAG=true."""
        # Set environment variable using monkeypatch
        monkeypatch.setenv("USE_AGENTIC_RAG", "true")

        # Mock extract_code_blocks properly
        mock_extract_code_blocks = mocker.patch(
            "src.utils.extract_code_blocks", return_value=['print("hello")', "import os"]
        )

        doc_file_info = {
            "url": "docs/examples.md",
            "markdown": "# Examples\n\n```python\nprint('hello')\n```",
        }

        result = create_documentation_metadata(doc_file_info, repo_info)

        assert result["code_example_count"] == 2  # Mocked to return 2 code blocks
        mock_extract_code_blocks.assert_called_once()


class TestProcessRepositoryDocs:
    """Tests for process_repository_docs function."""

    @pytest.mark.asyncio
    async def test_process_repository_docs_success(
        self, temp_repo_dir, mock_supabase_client, mocker
    ):
        """Test successful processing of repository documentation."""
        # Mock the dependencies
        mocker.patch("src.utils.smart_chunk_markdown", return_value=["chunk1", "chunk2"])
        mocker.patch("src.utils.add_documents_to_supabase", return_value=None)

        repo_name = "test-repo"
        repo_url = "https://github.com/user/test-repo.git"

        result = await process_repository_docs(
            mock_supabase_client, temp_repo_dir, repo_name, repo_url
        )

        assert result["files_processed"] > 0
        assert result["chunks_created"] > 0
        assert "code_examples_extracted" in result

    @pytest.mark.asyncio
    async def test_process_repository_docs_no_files_found(self, mock_supabase_client):
        """Test behavior when no documentation files are found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_repo = Path(temp_dir)

            result = await process_repository_docs(
                mock_supabase_client,
                empty_repo,
                "empty-repo",
                "https://github.com/user/empty-repo.git",
            )

            assert result["files_processed"] == 0
            assert result["chunks_created"] == 0
            assert result["code_examples_extracted"] == 0
            assert "No documentation files found" in result["message"]

    @pytest.mark.asyncio
    async def test_process_repository_docs_handles_processing_errors(
        self, temp_repo_dir, mock_supabase_client, mocker
    ):
        """Test graceful error handling during processing."""
        mocker.patch(
            "src.utils.process_document_files",
            side_effect=Exception("Processing error"),
        )

        result = await process_repository_docs(
            mock_supabase_client,
            temp_repo_dir,
            "test-repo",
            "https://github.com/user/test-repo.git",
        )

        assert result["files_processed"] == 0
        assert result["chunks_created"] == 0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_process_repository_docs_returns_correct_statistics(
        self, temp_repo_dir, mock_supabase_client, mocker
    ):
        """Test that returned statistics match actual processing."""
        # Configure mocks to return specific counts
        mocker.patch(
            "src.utils.smart_chunk_markdown", return_value=["chunk1", "chunk2", "chunk3"]
        )
        mocker.patch("src.utils.add_documents_to_supabase", return_value=None)

        result = await process_repository_docs(
            mock_supabase_client,
            temp_repo_dir,
            "test-repo",
            "https://github.com/user/test-repo.git",
        )

        # Should match the number of files discovered
        expected_files = len(discover_documentation_files(temp_repo_dir))
        assert result["files_processed"] == expected_files

        # Should reflect chunking results
        expected_chunks = expected_files * 3  # 3 chunks per file from mock
        assert result["chunks_created"] == expected_chunks
