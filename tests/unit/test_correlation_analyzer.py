"""
Unit tests for review_aggregator/correlation_analyzer.py
"""

from unittest.mock import patch

import pandas as pd
import pytest


class TestCorrelationAnalyzer:
    """Tests for CorrelationAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a CorrelationAnalyzer with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {"enable_caching": False, "enable_cost_tracking": False}
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.correlation_analyzer import (
                        CorrelationAnalyzer,
                    )

                    return CorrelationAnalyzer(zipcode="97067")

    @pytest.fixture
    def sample_tier_with_string_false(self):
        """DataFrame where amenities use string 'False' (as loaded from CSV)."""
        return pd.DataFrame(
            {
                "SYSTEM_JACUZZI": ["Private hot tub", "False", "Hot tub", "False"],
                "SYSTEM_POOL": ["False", "False", "False", "False"],
                "SYSTEM_FIREPIT": ["Fire pit", "Fire pit", "Fire pit", "False"],
            },
            index=["prop_1", "prop_2", "prop_3", "prop_4"],
        )

    def test_compute_amenity_prevalence_string_false(
        self, analyzer, sample_tier_with_string_false
    ):
        """Amenity prevalence correctly handles string 'False' from CSV.

        When CSV is read, missing amenities are the string 'False', not Python bool.
        The method must compare against 'False' (str) to get accurate counts.
        """
        high_tier = sample_tier_with_string_false
        # Low tier: no amenities at all
        low_tier = pd.DataFrame(
            {
                "SYSTEM_JACUZZI": ["False", "False", "False"],
                "SYSTEM_POOL": ["False", "False", "False"],
                "SYSTEM_FIREPIT": ["False", "False", "False"],
            },
            index=["prop_5", "prop_6", "prop_7"],
        )

        result = analyzer.compute_amenity_prevalence(high_tier, low_tier)

        # SYSTEM_JACUZZI: 2 of 4 in high tier = 50%, 0 of 3 in low tier = 0%
        assert result["SYSTEM_JACUZZI"]["high_tier_pct"] == 50.0
        assert result["SYSTEM_JACUZZI"]["low_tier_pct"] == 0.0
        assert result["SYSTEM_JACUZZI"]["difference"] == 50.0

        # SYSTEM_POOL: 0 of 4 in high tier = 0%, 0 of 3 in low tier = 0%
        assert result["SYSTEM_POOL"]["high_tier_pct"] == 0.0
        assert result["SYSTEM_POOL"]["low_tier_pct"] == 0.0

        # SYSTEM_FIREPIT: 3 of 4 in high tier = 75%, 0 of 3 in low tier = 0%
        assert result["SYSTEM_FIREPIT"]["high_tier_pct"] == 75.0
        assert result["SYSTEM_FIREPIT"]["low_tier_pct"] == 0.0

    def test_compute_amenity_prevalence_not_all_100(
        self, analyzer, sample_tier_with_string_false
    ):
        """Amenities with string 'False' must NOT all show 100%.

        This is the regression test for the bug where comparing against
        Python bool False made every amenity appear present in every property.
        """
        high_tier = sample_tier_with_string_false
        low_tier = sample_tier_with_string_false.copy()

        result = analyzer.compute_amenity_prevalence(high_tier, low_tier)

        # At least one amenity should NOT be 100% in high tier
        high_pcts = [v["high_tier_pct"] for v in result.values()]
        assert not all(
            pct == 100.0 for pct in high_pcts
        ), "All amenities at 100% suggests string 'False' vs bool False bug"
