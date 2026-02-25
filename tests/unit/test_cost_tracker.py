"""
Unit tests for utils/cost_tracker.py
"""

from unittest.mock import patch

import pytest


class TestCostTracker:
    """Tests for CostTracker class."""

    @pytest.fixture
    def cost_tracker(self, tmp_logs_dir):
        """Create a CostTracker with a temporary log file."""
        with patch("utils.cost_tracker.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": True}}

            from utils.cost_tracker import CostTracker

            return CostTracker(
                log_file=str(tmp_logs_dir / "cost_tracking.json"), enable_tracking=True
            )

    def test_estimate_tokens_with_tiktoken(self, cost_tracker):
        """Test token estimation using tiktoken."""
        text = "Hello, world! This is a test."

        tokens = cost_tracker.estimate_tokens(text)

        # Should return a positive integer
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_tokens_empty_string(self, cost_tracker):
        """Test token estimation for empty string."""
        tokens = cost_tracker.estimate_tokens("")

        assert tokens == 0

    def test_estimate_tokens_fallback(self, cost_tracker):
        """Test token estimation fallback when tiktoken fails."""
        text = "This is a test string for fallback estimation"

        with patch(
            "tiktoken.encoding_for_model", side_effect=Exception("Model not found")
        ):
            tokens = cost_tracker.estimate_tokens(text)

        # Fallback is len(text) // 4
        expected = len(text) // 4
        assert tokens == expected

    def test_calculate_cost_zero_tokens(self, cost_tracker):
        """Test cost calculation with zero tokens."""
        cost = cost_tracker.calculate_cost(0, 0)

        assert cost == 0.0

    def test_calculate_cost_input_only(self, cost_tracker):
        """Test cost calculation with only input tokens."""
        # 1M input tokens at $0.40 per 1M
        cost = cost_tracker.calculate_cost(1_000_000, 0)

        assert cost == 0.4

    def test_calculate_cost_output_only(self, cost_tracker):
        """Test cost calculation with only output tokens."""
        # 1M output tokens at $1.60 per 1M
        cost = cost_tracker.calculate_cost(0, 1_000_000)

        assert cost == 1.6

    def test_calculate_cost_combined(self, cost_tracker):
        """Test cost calculation with both input and output tokens."""
        # 500k input + 500k output
        # (500k/1M * $0.40) + (500k/1M * $1.60) = $0.20 + $0.80 = $1.00
        cost = cost_tracker.calculate_cost(500_000, 500_000)

        assert cost == 1.0

    def test_calculate_cost_small_amounts(self, cost_tracker):
        """Test cost calculation with small token counts."""
        # 1000 input + 500 output
        cost = cost_tracker.calculate_cost(1000, 500)

        # Should be a small positive number
        assert cost > 0
        assert cost < 0.002

    def test_track_request_updates_session_stats(self, cost_tracker):
        """Test that track_request updates session statistics."""
        initial_requests = cost_tracker.session_stats["total_requests"]

        cost_tracker.track_request(
            listing_id="12345",
            prompt="Test prompt",
            reviews=["Review 1", "Review 2"],
            response="Test response",
            success=True,
        )

        assert cost_tracker.session_stats["total_requests"] == initial_requests + 1
        assert cost_tracker.session_stats["successful_requests"] == 1
        assert "12345" in cost_tracker.session_stats["listings_processed"]

    def test_track_request_failed_request(self, cost_tracker):
        """Test tracking a failed request."""
        cost_tracker.track_request(
            listing_id="12345",
            prompt="Test prompt",
            reviews=["Review 1"],
            response=None,
            success=False,
        )

        assert cost_tracker.session_stats["failed_requests"] == 1
        assert cost_tracker.session_stats["successful_requests"] == 0

    def test_track_request_cached_no_cost(self, cost_tracker):
        """Test that cached requests don't incur cost."""
        result = cost_tracker.track_request(
            listing_id="12345",
            prompt="Test prompt",
            reviews=["Review 1"],
            response="Cached response",
            success=True,
            cached=True,
        )

        assert result["cost"] == 0.0
        assert result["cached"] is True
        assert cost_tracker.session_stats["cache_hits"] == 1

    def test_track_request_returns_token_info(self, cost_tracker):
        """Test that track_request returns token information."""
        result = cost_tracker.track_request(
            listing_id="12345",
            prompt="Test prompt here",
            reviews=["A review"],
            response="A response",
            success=True,
        )

        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "cost" in result
        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0

    def test_reset_session(self, cost_tracker):
        """Test that reset_session clears all stats."""
        # Add some data
        cost_tracker.track_request(
            listing_id="12345",
            prompt="Test",
            reviews=["Review"],
            response="Response",
            success=True,
        )

        # Reset
        cost_tracker.reset_session()

        assert cost_tracker.session_stats["total_requests"] == 0
        assert cost_tracker.session_stats["successful_requests"] == 0
        assert cost_tracker.session_stats["total_cost"] == 0.0
        assert len(cost_tracker.session_stats["listings_processed"]) == 0

    def test_tracking_disabled_returns_empty_dict(self, tmp_logs_dir):
        """Test that tracking when disabled returns empty dict."""
        with patch("utils.cost_tracker.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}

            from utils.cost_tracker import CostTracker

            tracker = CostTracker(
                log_file=str(tmp_logs_dir / "cost.json"), enable_tracking=False
            )

            result = tracker.track_request(
                listing_id="12345",
                prompt="Test",
                reviews=["Review"],
                response="Response",
            )

            assert result == {}

    def test_multiple_listings_tracked(self, cost_tracker):
        """Test tracking requests for multiple listings."""
        cost_tracker.track_request("listing1", "prompt", ["r1"], "resp1", success=True)
        cost_tracker.track_request("listing2", "prompt", ["r2"], "resp2", success=True)
        cost_tracker.track_request("listing1", "prompt", ["r3"], "resp3", success=True)

        # listing1 should only appear once in listings_processed
        assert cost_tracker.session_stats["total_requests"] == 3
        assert len(cost_tracker.session_stats["listings_processed"]) == 2
        assert "listing1" in cost_tracker.session_stats["listings_processed"]
        assert "listing2" in cost_tracker.session_stats["listings_processed"]


class TestCostTrackerSessionSummary:
    """Tests for CostTracker session summary methods."""

    @pytest.fixture
    def cost_tracker(self, tmp_logs_dir):
        """Create a CostTracker with a temporary log file."""
        with patch("utils.cost_tracker.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": True}}

            from utils.cost_tracker import CostTracker

            return CostTracker(
                log_file=str(tmp_logs_dir / "cost_tracking.json"), enable_tracking=True
            )

    def test_get_session_summary_structure(self, cost_tracker):
        """Test that get_session_summary returns correct structure."""
        cost_tracker.track_request("listing1", "prompt", ["r1"], "resp1", success=True)

        summary = cost_tracker.get_session_summary()

        assert "tracking_enabled" in summary
        assert summary["tracking_enabled"] is True
        assert "session_duration_minutes" in summary
        assert "total_requests" in summary
        assert "successful_requests" in summary
        assert "cache_hit_rate" in summary
        assert "total_cost" in summary

    def test_get_session_summary_disabled(self, tmp_logs_dir):
        """Test get_session_summary when tracking is disabled."""
        with patch("utils.cost_tracker.load_json_file") as mock_load:
            mock_load.return_value = {}

            from utils.cost_tracker import CostTracker

            tracker = CostTracker(
                log_file=str(tmp_logs_dir / "cost.json"), enable_tracking=False
            )

            summary = tracker.get_session_summary()

            assert summary == {"tracking_enabled": False}

    def test_get_session_summary_calculations(self, cost_tracker):
        """Test session summary calculations are correct."""
        # Track some requests
        cost_tracker.track_request("l1", "p", ["r"], "resp", success=True, cached=False)
        cost_tracker.track_request("l2", "p", ["r"], "resp", success=True, cached=True)
        cost_tracker.track_request("l3", "p", ["r"], None, success=False, cached=False)

        summary = cost_tracker.get_session_summary()

        assert summary["total_requests"] == 3
        assert summary["successful_requests"] == 2
        assert summary["failed_requests"] == 1
        assert summary["cache_hits"] == 1
        assert summary["unique_listings"] == 3

    def test_log_session_creates_file(self, cost_tracker, tmp_logs_dir):
        """Test that log_session creates a log file."""
        cost_tracker.track_request("listing1", "prompt", ["r1"], "resp1", success=True)

        result = cost_tracker.log_session()

        assert result is True
        log_file = tmp_logs_dir / "cost_tracking.json"
        assert log_file.exists()

    def test_log_session_disabled(self, tmp_logs_dir):
        """Test log_session when tracking is disabled."""
        with patch("utils.cost_tracker.load_json_file") as mock_load:
            mock_load.return_value = {}

            from utils.cost_tracker import CostTracker

            tracker = CostTracker(
                log_file=str(tmp_logs_dir / "cost.json"), enable_tracking=False
            )

            result = tracker.log_session()

            assert result is False

    def test_print_session_summary(self, cost_tracker, capsys):
        """Test that print_session_summary outputs correctly."""
        cost_tracker.track_request("listing1", "prompt", ["r1"], "resp1", success=True)

        cost_tracker.print_session_summary()

        # Method uses logger.info, not print, so we just verify it doesn't raise
        # The method should complete without error

    def test_get_historical_stats_no_data(self, cost_tracker):
        """Test get_historical_stats with no log file."""
        stats = cost_tracker.get_historical_stats(days=30)

        # No log file exists yet
        assert stats["tracking_enabled"] is False or stats.get("no_data") is True
