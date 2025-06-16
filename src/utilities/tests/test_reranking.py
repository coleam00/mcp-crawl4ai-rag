"""Tests for reranking utilities."""

import pytest
from unittest.mock import Mock, patch

from crawl4ai_mcp.utilities.reranking import Reranker


@pytest.fixture
def mock_cross_encoder():
    """Mock CrossEncoder model."""
    model = Mock()
    model.predict = Mock()
    return model


@pytest.fixture
def reranker(test_settings, mock_cross_encoder):
    """Create Reranker with mocked dependencies."""
    return Reranker(model=mock_cross_encoder, settings=test_settings)


@pytest.fixture
def sample_results():
    """Sample search results for testing."""
    return [
        {
            "content": "First result about machine learning",
            "url": "https://example.com/1",
            "score": 0.8
        },
        {
            "content": "Second result about deep learning",
            "url": "https://example.com/2",
            "score": 0.7
        },
        {
            "content": "Third result about neural networks",
            "url": "https://example.com/3",
            "score": 0.6
        }
    ]


class TestReranker:
    """Test reranking functionality."""
    
    def test_rerank_results_success(self, reranker, mock_cross_encoder, sample_results) -> None:
        """Test successful reranking of results."""
        # Mock reranking scores (reverse order to test sorting)
        mock_cross_encoder.predict.return_value = [0.5, 0.9, 0.7]
        
        query = "machine learning algorithms"
        reranked = reranker.rerank_results(query, sample_results)
        
        # Verify cross-encoder was called with correct pairs
        expected_pairs = [
            [query, "First result about machine learning"],
            [query, "Second result about deep learning"],
            [query, "Third result about neural networks"]
        ]
        mock_cross_encoder.predict.assert_called_once_with(expected_pairs)
        
        # Verify results are reordered by rerank score
        assert len(reranked) == 3
        assert reranked[0]["content"] == "Second result about deep learning"  # Highest score 0.9
        assert reranked[1]["content"] == "Third result about neural networks"  # Score 0.7
        assert reranked[2]["content"] == "First result about machine learning"  # Lowest score 0.5
        
        # Verify rerank scores are added
        assert reranked[0]["rerank_score"] == 0.9
        assert reranked[1]["rerank_score"] == 0.7
        assert reranked[2]["rerank_score"] == 0.5
    
    def test_rerank_results_empty_results(self, reranker) -> None:
        """Test reranking with empty results."""
        results = reranker.rerank_results("query", [])
        assert results == []
    
    def test_rerank_results_no_model(self, test_settings) -> None:
        """Test reranking without a model."""
        reranker_no_model = Reranker(model=None, settings=test_settings)
        sample = [{"content": "test"}]
        
        results = reranker_no_model.rerank_results("query", sample)
        assert results == sample  # Should return original results
    
    def test_rerank_results_custom_content_key(self, reranker, mock_cross_encoder, sample_results) -> None:
        """Test reranking with custom content key."""
        # Change content key
        for result in sample_results:
            result["text"] = result.pop("content")
        
        mock_cross_encoder.predict.return_value = [0.9, 0.8, 0.7]
        
        reranker.rerank_results("query", sample_results, content_key="text")
        
        # Verify it used the correct content key
        expected_pairs = [
            ["query", "First result about machine learning"],
            ["query", "Second result about deep learning"],
            ["query", "Third result about neural networks"]
        ]
        mock_cross_encoder.predict.assert_called_once_with(expected_pairs)
    
    def test_rerank_results_error_handling(self, reranker, mock_cross_encoder, sample_results) -> None:
        """Test reranking with prediction error."""
        # Mock error
        mock_cross_encoder.predict.side_effect = Exception("Model error")
        
        results = reranker.rerank_results("query", sample_results)
        
        # Should return original results on error
        assert results == sample_results
    
    def test_filter_by_threshold(self, reranker) -> None:
        """Test filtering results by threshold."""
        results = [
            {"content": "Result 1", "rerank_score": 0.9},
            {"content": "Result 2", "rerank_score": 0.5},
            {"content": "Result 3", "rerank_score": 0.7},
            {"content": "Result 4", "rerank_score": 0.3}
        ]
        
        filtered = reranker.filter_by_threshold(results, threshold=0.6)
        
        assert len(filtered) == 2
        assert filtered[0]["rerank_score"] == 0.9
        assert filtered[1]["rerank_score"] == 0.7
    
    def test_filter_by_threshold_custom_key(self, reranker) -> None:
        """Test filtering with custom score key."""
        results = [
            {"content": "Result 1", "custom_score": 0.9},
            {"content": "Result 2", "custom_score": 0.5},
            {"content": "Result 3", "custom_score": 0.7}
        ]
        
        filtered = reranker.filter_by_threshold(
            results, 
            threshold=0.6, 
            score_key="custom_score"
        )
        
        assert len(filtered) == 2
        assert filtered[0]["custom_score"] == 0.9
        assert filtered[1]["custom_score"] == 0.7
    
    def test_filter_by_threshold_missing_scores(self, reranker) -> None:
        """Test filtering when some results lack scores."""
        results = [
            {"content": "Result 1", "rerank_score": 0.9},
            {"content": "Result 2"},  # No score
            {"content": "Result 3", "rerank_score": 0.7}
        ]
        
        filtered = reranker.filter_by_threshold(results, threshold=0.5)
        
        # Result without score should be filtered out (default 0)
        assert len(filtered) == 2
        assert all("rerank_score" in r for r in filtered)


class TestRerankerInitialization:
    """Test Reranker initialization."""
    
    @patch('crawl4ai_mcp.utilities.reranking.CrossEncoder')
    def test_init_with_reranking_enabled(self, MockCrossEncoder, test_settings) -> None:
        """Test initialization with reranking enabled."""
        test_settings.use_reranking = True
        test_settings.cross_encoder_model = "test-model"
        
        mock_model = Mock()
        MockCrossEncoder.return_value = mock_model
        
        reranker = Reranker(settings=test_settings)
        
        # Should initialize model
        MockCrossEncoder.assert_called_once_with("test-model")
        assert reranker.model == mock_model
    
    def test_init_with_reranking_disabled(self, test_settings) -> None:
        """Test initialization with reranking disabled."""
        test_settings.use_reranking = False
        
        reranker = Reranker(settings=test_settings)
        
        # Should not initialize model
        assert reranker.model is None
    
    def test_init_with_provided_model(self, test_settings, mock_cross_encoder) -> None:
        """Test initialization with provided model."""
        reranker = Reranker(model=mock_cross_encoder, settings=test_settings)
        
        # Should use provided model
        assert reranker.model == mock_cross_encoder