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
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
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
        assert not all(pct == 100.0 for pct in high_pcts), (
            "All amenities at 100% suggests string 'False' vs bool False bug"
        )


class TestLoadPropertyDataAirdnaFilter:
    """Tests for AirDNA-data filtering in load_property_data."""

    @pytest.fixture
    def analyzer(self):
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.correlation_analyzer import CorrelationAnalyzer

                return CorrelationAnalyzer(zipcode="97067")

    def test_excludes_rows_without_airdna_data(self, analyzer, tmp_path):
        """Properties with has_airdna_data=False should be excluded."""
        csv_path = tmp_path / "property_amenities_matrix_97067.csv"
        df = pd.DataFrame(
            {
                "ADR": [200.0, 300.0, 150.0],
                "Occ_Rate_Based_on_Avail": [60, 80, 50],
                "has_airdna_data": [True, True, False],
                "capacity": [4, 6, 3],
            },
            index=["p1", "p2", "p3"],
        )
        df.index.name = "property_id"
        df.to_csv(csv_path)

        with patch(
            "os.path.exists",
            return_value=True,
        ):
            with patch("pandas.read_csv", return_value=df):
                result = analyzer.load_property_data()

        assert "p1" in result.index
        assert "p2" in result.index
        assert "p3" not in result.index
        assert "has_airdna_data" not in result.columns

    def test_backward_compat_no_flag_column(self, analyzer, tmp_path):
        """CSVs without has_airdna_data column should load all rows."""
        df = pd.DataFrame(
            {
                "ADR": [200.0, 300.0],
                "capacity": [4, 6],
            },
            index=["p1", "p2"],
        )
        df.index.name = "property_id"

        with patch("os.path.exists", return_value=True):
            with patch("pandas.read_csv", return_value=df):
                result = analyzer.load_property_data()

        assert len(result) == 2

    def test_logs_filtering_count(self, analyzer):
        """Should log how many properties were filtered."""
        df = pd.DataFrame(
            {
                "ADR": [200.0, 300.0, 150.0],
                "has_airdna_data": [True, False, False],
                "capacity": [4, 6, 3],
            },
            index=["p1", "p2", "p3"],
        )
        df.index.name = "property_id"

        with patch("os.path.exists", return_value=True):
            with patch("pandas.read_csv", return_value=df):
                with patch(
                    "review_aggregator.correlation_analyzer.logger"
                ) as mock_logger:
                    analyzer.load_property_data()

        mock_logger.info.assert_any_call(
            "Filtered 2 properties without AirDNA data (1 remaining)"
        )
