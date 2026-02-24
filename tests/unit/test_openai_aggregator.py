"""
Unit tests for review_aggregator/openai_aggregator.py
"""

import pytest
from unittest.mock import patch, MagicMock


class TestOpenAIAggregator:
    """Tests for OpenAIAggregator class."""

    @pytest.fixture
    def aggregator(self, tmp_cache_dir, tmp_logs_dir):
        """Create an OpenAIAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.3,
                    "max_tokens": 4000,
                    "chunk_size": 20,
                    "enable_caching": False,
                    "enable_cost_tracking": False,
                }
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.openai_aggregator import OpenAIAggregator

                    agg = OpenAIAggregator()
                    agg.cache_manager.cache_dir = str(tmp_cache_dir)
                    agg.cost_tracker.log_file = str(tmp_logs_dir / "cost.json")
                    return agg

    def test_estimate_tokens_valid_text(self, aggregator):
        """Test token estimation for valid text."""
        text = "This is a sample review text for testing."

        tokens = aggregator.estimate_tokens(text)

        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_tokens_empty_string(self, aggregator):
        """Test token estimation for empty string."""
        tokens = aggregator.estimate_tokens("")

        assert tokens == 0

    def test_estimate_tokens_none_value(self, aggregator):
        """Test token estimation for None."""
        tokens = aggregator.estimate_tokens(None)

        assert tokens == 0

    def test_estimate_tokens_nan_value(self, aggregator):
        """Test token estimation for NaN values."""
        import pandas as pd

        tokens = aggregator.estimate_tokens(pd.NA)

        assert tokens == 0

    def test_estimate_tokens_nan_string(self, aggregator):
        """Test token estimation for 'nan' string."""
        tokens = aggregator.estimate_tokens("nan")

        assert tokens == 0

    def test_chunk_reviews_single_chunk(self, aggregator):
        """Test chunking when all reviews fit in one chunk."""
        reviews = ["Review 1", "Review 2", "Review 3"]
        prompt = "Analyze these reviews"

        chunks = aggregator.chunk_reviews(reviews, prompt)

        assert len(chunks) == 1
        assert chunks[0] == reviews

    def test_chunk_reviews_multiple_chunks(self, aggregator):
        """Test chunking when reviews exceed chunk_size."""
        # Create more reviews than chunk_size
        reviews = [f"Review number {i}" for i in range(25)]
        prompt = "Analyze these reviews"

        # With chunk_size=20, should create 2 chunks
        chunks = aggregator.chunk_reviews(reviews, prompt)

        assert len(chunks) == 2
        assert len(chunks[0]) == 20
        assert len(chunks[1]) == 5

    def test_chunk_reviews_empty_list(self, aggregator):
        """Test chunking with empty reviews list."""
        chunks = aggregator.chunk_reviews([], "prompt")

        assert chunks == []

    def test_chunk_reviews_preserves_all_reviews(self, aggregator):
        """Test that chunking preserves all reviews."""
        reviews = [f"Review {i}" for i in range(45)]
        prompt = "Analyze"

        chunks = aggregator.chunk_reviews(reviews, prompt)

        # Flatten chunks and verify all reviews present
        all_chunked_reviews = [r for chunk in chunks for r in chunk]
        assert len(all_chunked_reviews) == 45
        assert set(all_chunked_reviews) == set(reviews)

    def test_create_chunk_prompt_format(self, aggregator):
        """Test chunk prompt formatting."""
        base_prompt = "Analyze the following reviews:"
        reviews = ["Great place!", "Loved it!"]
        chunk_info = "Chunk 1 of 2"

        result = aggregator.create_chunk_prompt(base_prompt, reviews, chunk_info)

        assert base_prompt in result
        assert chunk_info in result
        assert "Review 1: Great place!" in result
        assert "Review 2: Loved it!" in result

    def test_create_chunk_prompt_no_chunk_info(self, aggregator):
        """Test chunk prompt without chunk info."""
        base_prompt = "Analyze reviews:"
        reviews = ["Good stay"]

        result = aggregator.create_chunk_prompt(base_prompt, reviews)

        assert base_prompt in result
        assert "Review 1: Good stay" in result

    def test_call_openai_with_retry_success(self, aggregator, mock_openai_client):
        """Test successful OpenAI API call."""
        aggregator.client = mock_openai_client

        result = aggregator.call_openai_with_retry("Test prompt", "listing123")

        assert result is not None
        mock_openai_client.chat.completions.create.assert_called_once()

    def test_call_openai_with_retry_retries_on_failure(self, aggregator):
        """Test that API call retries on failure."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            Exception("API Error"),
            Exception("API Error"),
            MagicMock(choices=[MagicMock(message=MagicMock(content="Success"))]),
        ]
        aggregator.client = mock_client
        aggregator.retry_delay = 0.01  # Speed up test

        result = aggregator.call_openai_with_retry("Test prompt", "listing123")

        assert result == "Success"
        assert mock_client.chat.completions.create.call_count == 3

    def test_call_openai_with_retry_max_retries_exceeded(self, aggregator):
        """Test that None is returned after max retries."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Persistent error")
        aggregator.client = mock_client
        aggregator.retry_delay = 0.01
        aggregator.max_retries = 3

        result = aggregator.call_openai_with_retry("Test prompt", "listing123")

        assert result is None
        assert mock_client.chat.completions.create.call_count == 3

    def test_merge_chunk_summaries_single_summary(self, aggregator):
        """Test merging when there's only one summary."""
        summaries = ["This is the only summary"]

        result = aggregator.merge_chunk_summaries(summaries, "prompt", "listing123")

        assert result == "This is the only summary"

    def test_merge_chunk_summaries_multiple(self, aggregator, mock_openai_client):
        """Test merging multiple chunk summaries."""
        aggregator.client = mock_openai_client
        summaries = ["Summary 1: Good reviews", "Summary 2: More good reviews"]

        result = aggregator.merge_chunk_summaries(
            summaries, "base prompt", "listing123"
        )

        assert result is not None
        mock_openai_client.chat.completions.create.assert_called()

    def test_model_config_from_init(self, tmp_cache_dir, tmp_logs_dir):
        """Test that model configuration is loaded from config."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {
                    "model": "gpt-4",
                    "temperature": 0.5,
                    "max_tokens": 8000,
                    "chunk_size": 30,
                }
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.openai_aggregator import OpenAIAggregator

                    agg = OpenAIAggregator()

                    assert agg.model == "gpt-4"
                    assert agg.temperature == 0.5
                    assert agg.max_tokens == 8000
                    assert agg.chunk_size == 30


class TestOpenAIAggregatorGenerateSummary:
    """Tests for OpenAIAggregator.generate_summary method."""

    @pytest.fixture
    def aggregator(self, tmp_cache_dir, tmp_logs_dir):
        """Create an OpenAIAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.3,
                    "max_tokens": 4000,
                    "chunk_size": 20,
                    "enable_caching": False,
                    "enable_cost_tracking": False,
                }
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.openai_aggregator import OpenAIAggregator

                    agg = OpenAIAggregator()
                    agg.cache_manager.cache_dir = str(tmp_cache_dir)
                    agg.cache_manager.enable_cache = False
                    agg.cost_tracker.log_file = str(tmp_logs_dir / "cost.json")
                    agg.cost_tracker.enable_tracking = False
                    return agg

    def test_generate_summary_empty_reviews(self, aggregator):
        """Test generate_summary with empty reviews returns None."""
        result = aggregator.generate_summary([], "prompt", "listing123")

        assert result is None

    def test_generate_summary_none_reviews(self, aggregator):
        """Test generate_summary with None reviews returns None."""
        result = aggregator.generate_summary(None, "prompt", "listing123")

        assert result is None

    def test_generate_summary_single_request(self, aggregator, mock_openai_client):
        """Test generate_summary with small review set (single request)."""
        aggregator.client = mock_openai_client
        reviews = ["Review 1", "Review 2", "Review 3"]

        result = aggregator.generate_summary(
            reviews, "Analyze these reviews", "listing123"
        )

        assert result is not None
        mock_openai_client.chat.completions.create.assert_called_once()

    def test_generate_summary_caches_result(self, aggregator, mock_openai_client):
        """Test generate_summary caches the result after API call."""
        aggregator.client = mock_openai_client
        aggregator.cache_manager.enable_cache = True

        reviews = ["Review A", "Review B"]
        prompt = "Test prompt"

        result = aggregator.generate_summary(reviews, prompt, "listing123")

        # Verify API was called and result returned
        assert result is not None
        mock_openai_client.chat.completions.create.assert_called_once()

    def test_generate_summary_chunked_reviews(self, aggregator, mock_openai_client):
        """Test generate_summary with large review set requiring chunking."""
        aggregator.client = mock_openai_client
        aggregator.chunk_size = 5  # Force chunking

        # Create more reviews than chunk_size
        reviews = [f"Review number {i} with some text content" for i in range(12)]

        result = aggregator.generate_summary(reviews, "Analyze reviews", "listing123")

        assert result is not None
        # Should have multiple API calls: chunks + merge
        assert mock_openai_client.chat.completions.create.call_count >= 2

    def test_generate_summary_api_failure(self, aggregator):
        """Test generate_summary handles API failures gracefully."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        aggregator.client = mock_client
        aggregator.max_retries = 1
        aggregator.retry_delay = 0.01

        result = aggregator.generate_summary(["Review"], "Prompt", "listing123")

        assert result is None
