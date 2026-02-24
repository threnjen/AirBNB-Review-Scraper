"""
Unit tests for review_aggregator/description_analyzer.py

TDD: These tests are written BEFORE the implementation.
They should fail (red) until description_analyzer.py is created.
"""

import json
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock


class TestDescriptionAnalyzer:
    """Tests for DescriptionAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a DescriptionAnalyzer with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {"enable_caching": False, "enable_cost_tracking": False}
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.description_analyzer import (
                        DescriptionAnalyzer,
                    )

                    return DescriptionAnalyzer(zipcode="97067")

    @pytest.fixture
    def sample_property_df(self):
        """DataFrame mimicking the amenities matrix CSV with known linear ADR pattern."""
        # ADR = 100 * bedrooms + 50 * capacity + noise
        # This makes it easy to verify residuals
        return pd.DataFrame(
            {
                "ADR": [350, 500, 250, 700, 300, 450, 600, 200],
                "capacity": [4, 6, 2, 10, 4, 6, 8, 2],
                "bedrooms": [2, 3, 1, 5, 2, 3, 4, 1],
                "beds": [3, 5, 2, 8, 3, 4, 6, 2],
                "bathrooms": [1, 2, 1, 3, 1, 2, 2, 1],
            },
            index=[
                "prop_1",
                "prop_2",
                "prop_3",
                "prop_4",
                "prop_5",
                "prop_6",
                "prop_7",
                "prop_8",
            ],
        )

    @pytest.fixture
    def sample_descriptions(self):
        """Property descriptions keyed by property ID."""
        return {
            "prop_1": "Cozy cabin with mountain views and a private hot tub.",
            "prop_2": "Spacious lodge perfect for families. Game room with pool table.",
            "prop_3": "Simple studio near the slopes.",
            "prop_4": "Luxury retreat with panoramic mountain views, hot tub, fire pit, and game room. Perfect for large groups seeking an unforgettable experience.",
            "prop_5": "Nice place. Close to stuff.",
            "prop_6": "Beautiful home with modern amenities and scenic views of Mt. Hood.",
            "prop_7": "Stunning property with wrap-around deck, outdoor fire pit, and gourmet kitchen. A true mountain escape.",
            "prop_8": "Basic cabin. Has beds.",
        }

    @pytest.fixture
    def sample_score_response(self):
        """Sample LLM scoring response for a single description."""
        return json.dumps(
            {
                "evocativeness": 8,
                "specificity": 7,
                "emotional_appeal": 9,
                "storytelling": 6,
                "usp_clarity": 8,
                "professionalism": 7,
                "completeness": 6,
            }
        )


class TestComputeResiduals(TestDescriptionAnalyzer):
    """Tests for compute_size_adjusted_residuals."""

    def test_returns_series_with_residuals(self, analyzer, sample_property_df):
        """Residuals should be a Series indexed by property_id."""
        residuals, r_squared = analyzer.compute_size_adjusted_residuals(
            sample_property_df
        )

        assert isinstance(residuals, pd.Series)
        assert len(residuals) == len(sample_property_df)
        assert all(idx in residuals.index for idx in sample_property_df.index)

    def test_residuals_sum_near_zero(self, analyzer, sample_property_df):
        """OLS residuals should sum to approximately zero."""
        residuals, r_squared = analyzer.compute_size_adjusted_residuals(
            sample_property_df
        )

        assert abs(residuals.sum()) < 1e-6

    def test_r_squared_between_zero_and_one(self, analyzer, sample_property_df):
        """R-squared should be between 0 and 1."""
        residuals, r_squared = analyzer.compute_size_adjusted_residuals(
            sample_property_df
        )

        assert 0.0 <= r_squared <= 1.0

    def test_perfect_linear_data_has_near_zero_residuals(self, analyzer):
        """When ADR is exactly linear in features, residuals should be ~0."""
        # Need >= 6 rows (5 coefficients = intercept + 4 features, plus at least 1 df)
        df = pd.DataFrame(
            {
                "ADR": [200, 400, 600, 800, 1000, 1200],
                "capacity": [2, 4, 6, 8, 10, 12],
                "bedrooms": [1, 2, 3, 4, 5, 6],
                "beds": [1, 2, 3, 4, 5, 6],
                "bathrooms": [1, 2, 3, 4, 5, 6],
            },
            index=["a", "b", "c", "d", "e", "f"],
        )

        residuals, r_squared = analyzer.compute_size_adjusted_residuals(df)

        assert r_squared > 0.99
        assert all(abs(r) < 1e-6 for r in residuals)

    def test_skips_rows_with_missing_adr(self, analyzer):
        """Properties with NaN or zero ADR should be excluded."""
        # 8 rows total, 2 invalid => 6 valid (enough for regression)
        df = pd.DataFrame(
            {
                "ADR": [350, 0, 250, float("nan"), 400, 500, 300, 450],
                "capacity": [4, 6, 2, 10, 5, 7, 3, 6],
                "bedrooms": [2, 3, 1, 5, 3, 4, 2, 3],
                "beds": [3, 5, 2, 8, 4, 6, 3, 5],
                "bathrooms": [1, 2, 1, 3, 2, 2, 1, 2],
            },
            index=["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"],
        )

        residuals, r_squared = analyzer.compute_size_adjusted_residuals(df)

        assert len(residuals) == 6
        assert "p2" not in residuals.index
        assert "p4" not in residuals.index


class TestParseScoreResponse(TestDescriptionAnalyzer):
    """Tests for parse_score_response."""

    def test_parses_valid_json_scores(self, analyzer, sample_score_response):
        """Valid JSON response should return a dict of dimension scores."""
        result = analyzer.parse_score_response(sample_score_response)

        assert result["evocativeness"] == 8
        assert result["specificity"] == 7
        assert result["emotional_appeal"] == 9

    def test_handles_markdown_wrapped_json(self, analyzer):
        """JSON wrapped in ```json ... ``` should be parsed correctly."""
        wrapped = '```json\n{"evocativeness": 5, "specificity": 3}\n```'

        result = analyzer.parse_score_response(wrapped)

        assert result["evocativeness"] == 5
        assert result["specificity"] == 3

    def test_returns_empty_dict_on_invalid_json(self, analyzer):
        """Invalid JSON should return empty dict, not raise."""
        result = analyzer.parse_score_response("This is not JSON at all")

        assert result == {}

    def test_returns_empty_dict_on_none(self, analyzer):
        """None response should return empty dict."""
        result = analyzer.parse_score_response(None)

        assert result == {}


class TestCorrelateScoresWithPremium(TestDescriptionAnalyzer):
    """Tests for correlate_scores_with_premium."""

    def test_positive_correlation_detected(self, analyzer):
        """When a dimension perfectly correlates with residuals, correlation ~1."""
        scores_df = pd.DataFrame(
            {
                "evocativeness": [1, 2, 3, 4, 5, 6, 7, 8],
                "specificity": [8, 7, 6, 5, 4, 3, 2, 1],
            },
            index=[f"p{i}" for i in range(8)],
        )
        residuals = pd.Series(
            [1, 2, 3, 4, 5, 6, 7, 8], index=[f"p{i}" for i in range(8)]
        )

        result = analyzer.correlate_scores_with_premium(scores_df, residuals)

        assert result["evocativeness"]["correlation"] > 0.99
        assert result["specificity"]["correlation"] < -0.99

    def test_returns_all_dimensions(self, analyzer):
        """Result should have an entry for each score dimension."""
        scores_df = pd.DataFrame(
            {"dim_a": [1, 2, 3], "dim_b": [4, 5, 6]},
            index=["p1", "p2", "p3"],
        )
        residuals = pd.Series([10, 20, 30], index=["p1", "p2", "p3"])

        result = analyzer.correlate_scores_with_premium(scores_df, residuals)

        assert "dim_a" in result
        assert "dim_b" in result
        assert "correlation" in result["dim_a"]
