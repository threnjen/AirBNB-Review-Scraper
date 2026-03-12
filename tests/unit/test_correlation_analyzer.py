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
        with patch("review_aggregator.openai_aggregator.load_config") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_config", return_value={}):
                from review_aggregator.correlation_analyzer import (
                    CorrelationAnalyzer,
                )

                return CorrelationAnalyzer(zone_name="97067")

    @pytest.fixture
    def sample_tier_int_amenities(self):
        """DataFrame where amenities use 0/1 integers (as in cleaned CSV)."""
        return pd.DataFrame(
            {
                "SYSTEM_JACUZZI": [1, 0, 1, 0],
                "SYSTEM_POOL": [0, 0, 0, 0],
                "SYSTEM_FIREPIT": [1, 1, 1, 0],
            },
            index=["prop_1", "prop_2", "prop_3", "prop_4"],
        )

    def test_compute_amenity_prevalence_int_amenities(
        self, analyzer, sample_tier_int_amenities
    ):
        """Amenity prevalence correctly handles 0/1 integers from cleaned CSV.

        After clean_amenities_df(), amenity columns contain integers (0/1).
        The method must compare against 0 to get accurate counts.
        """
        high_tier = sample_tier_int_amenities
        # Low tier: no amenities at all
        low_tier = pd.DataFrame(
            {
                "SYSTEM_JACUZZI": [0, 0, 0],
                "SYSTEM_POOL": [0, 0, 0],
                "SYSTEM_FIREPIT": [0, 0, 0],
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
        self, analyzer, sample_tier_int_amenities
    ):
        """Amenities with integer 0 values must NOT all show 100%.

        This is the regression test for the bug where comparing against
        string 'False' instead of integer 0 made every amenity appear present.
        """
        high_tier = sample_tier_int_amenities
        low_tier = sample_tier_int_amenities.copy()

        result = analyzer.compute_amenity_prevalence(high_tier, low_tier)

        # At least one amenity should NOT be 100% in high tier
        high_pcts = [v["high_tier_pct"] for v in result.values()]
        assert not all(pct == 100.0 for pct in high_pcts), (
            "All amenities at 100% suggests comparison against wrong type"
        )


class TestSegmentByMetricStringColumns:
    """Tests for segment_by_metric handling of string-typed metric columns."""

    @pytest.fixture
    def analyzer(self):
        with patch("review_aggregator.openai_aggregator.load_config") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_config", return_value={}):
                from review_aggregator.correlation_analyzer import CorrelationAnalyzer

                return CorrelationAnalyzer(
                    zone_name="97067", top_percentile=25, bottom_percentile=25
                )

    def test_string_typed_adr_column_does_not_raise(self, analyzer):
        """segment_by_metric must handle ADR column with string dtype.

        When the raw CSV is loaded, ADR may contain string values like
        '245.57' and 'False' (from fillna). The method must coerce to
        numeric without raising TypeError.
        """
        df = pd.DataFrame(
            {
                "ADR": ["300", "250", "200", "180", "150", "120", "100", "False"],
                "capacity": [4, 6, 3, 5, 2, 4, 3, 2],
            },
            index=[f"p{i}" for i in range(8)],
        )

        high_tier, low_tier, high_thresh, low_thresh = analyzer.segment_by_metric(
            df, "adr"
        )

        assert len(high_tier) > 0
        assert len(low_tier) > 0
        assert high_thresh > low_thresh

    def test_false_string_values_excluded(self, analyzer):
        """Rows with 'False' in the metric column are excluded from tiers."""
        df = pd.DataFrame(
            {
                "ADR": ["300", "250", "200", "180", "150", "120", "100", "False"],
                "capacity": [4, 6, 3, 5, 2, 4, 3, 2],
            },
            index=[f"p{i}" for i in range(8)],
        )

        high_tier, low_tier, _, _ = analyzer.segment_by_metric(df, "adr")

        # 'False' row (p7) should not appear in either tier
        assert "p7" not in high_tier.index
        assert "p7" not in low_tier.index

    def test_string_typed_occupancy_column(self, analyzer):
        """segment_by_metric handles string-typed Occ_Rate_Based_on_Avail."""
        df = pd.DataFrame(
            {
                "Occ_Rate_Based_on_Avail": [
                    "90",
                    "80",
                    "70",
                    "60",
                    "50",
                    "40",
                    "30",
                    "False",
                ],
                "capacity": [4, 6, 3, 5, 2, 4, 3, 2],
            },
            index=[f"p{i}" for i in range(8)],
        )

        high_tier, low_tier, high_thresh, low_thresh = analyzer.segment_by_metric(
            df, "occupancy"
        )

        assert len(high_tier) > 0
        assert len(low_tier) > 0
        assert "p7" not in high_tier.index


class TestLoadPropertyDataAirdnaFilter:
    """Tests for AirDNA-data filtering in load_property_data."""

    @pytest.fixture
    def analyzer(self):
        with patch("review_aggregator.openai_aggregator.load_config") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_config", return_value={}):
                from review_aggregator.correlation_analyzer import CorrelationAnalyzer

                return CorrelationAnalyzer(zone_name="97067")

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


class TestComputeMetricResiduals:
    """Tests for compute_metric_residuals XGBoost regression."""

    @pytest.fixture
    def analyzer(self):
        with patch("review_aggregator.openai_aggregator.load_config") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_config", return_value={}):
                from review_aggregator.correlation_analyzer import CorrelationAnalyzer

                return CorrelationAnalyzer(zone_name="97067")

    def test_residuals_mean_near_zero(self, analyzer):
        """Residuals should have a mean near zero."""
        df = pd.DataFrame(
            {
                "ADR": [300, 250, 200, 180, 150, 120, 400, 350],
                "capacity": [8, 6, 4, 4, 2, 2, 10, 8],
                "bedrooms": [4, 3, 2, 2, 1, 1, 5, 4],
                "beds": [6, 5, 3, 3, 2, 1, 8, 6],
                "bathrooms": [3, 2, 1, 1, 1, 1, 4, 3],
            },
            index=[f"p{i}" for i in range(8)],
        )

        residuals, r_squared = analyzer.compute_metric_residuals(df, "adr")

        assert abs(residuals.mean()) < 50

    def test_r_squared_between_zero_and_one(self, analyzer):
        """R-squared should be between 0 and 1."""
        df = pd.DataFrame(
            {
                "ADR": [300, 250, 200, 180, 150, 120, 400, 350],
                "capacity": [8, 6, 4, 4, 2, 2, 10, 8],
                "bedrooms": [4, 3, 2, 2, 1, 1, 5, 4],
                "beds": [6, 5, 3, 3, 2, 1, 8, 6],
                "bathrooms": [3, 2, 1, 1, 1, 1, 4, 3],
            },
            index=[f"p{i}" for i in range(8)],
        )

        residuals, r_squared = analyzer.compute_metric_residuals(df, "adr")

        assert 0.0 <= r_squared <= 1.0

    def test_returns_empty_for_unknown_metric(self, analyzer):
        """Unknown metric should return empty series."""
        df = pd.DataFrame({"ADR": [100]}, index=["p1"])

        residuals, r_squared = analyzer.compute_metric_residuals(df, "unknown")

        assert residuals.empty

    def test_uses_only_size_features(self, analyzer):
        """Residuals should only be computed from capacity, bedrooms, beds, bathrooms."""
        # XGBoost needs enough samples to split (min_child_weight=10),
        # so we use 30 rows with a clear linear pattern.
        n = 30
        capacity = list(range(2, 2 + n))
        bedrooms = [c // 2 for c in capacity]
        beds = [c // 2 + 1 for c in capacity]
        bathrooms = [max(1, c // 4) for c in capacity]
        # ADR is a strict linear function of size features
        adr = [
            50 + 20 * cap + 10 * bed + 5 * bath
            for cap, bed, bath in zip(capacity, beds, bathrooms)
        ]

        df = pd.DataFrame(
            {
                "ADR": adr,
                "capacity": capacity,
                "bedrooms": bedrooms,
                "beds": beds,
                "bathrooms": bathrooms,
            },
            index=[f"p{i}" for i in range(n)],
        )

        residuals, r_squared = analyzer.compute_metric_residuals(df, "adr")

        # Strong linear pattern in size features → R² should be reasonably high
        assert r_squared > 0.80
        # Residuals should be small relative to the ADR range
        adr_range = max(adr) - min(adr)
        assert all(abs(r) < 0.25 * adr_range for r in residuals)

    def test_works_with_occupancy_metric(self, analyzer):
        """Should work for occupancy metric too."""
        df = pd.DataFrame(
            {
                "Occ_Rate_Based_on_Avail": [90, 80, 70, 60, 50, 40],
                "capacity": [2, 4, 6, 8, 10, 12],
                "bedrooms": [1, 2, 3, 4, 5, 6],
                "beds": [1, 2, 3, 4, 5, 6],
                "bathrooms": [1, 2, 3, 4, 5, 6],
            },
            index=["a", "b", "c", "d", "e", "f"],
        )

        residuals, r_squared = analyzer.compute_metric_residuals(df, "occupancy")

        assert len(residuals) == 6
        assert abs(residuals.mean()) < 50


class TestNumericColumnsConstant:
    """Tests for the updated NUMERIC_COLUMNS constant."""

    def test_no_raw_size_features(self):
        """NUMERIC_COLUMNS should not contain raw size features."""
        from review_aggregator.correlation_analyzer import NUMERIC_COLUMNS

        assert "capacity" not in NUMERIC_COLUMNS
        assert "bedrooms" not in NUMERIC_COLUMNS
        assert "beds" not in NUMERIC_COLUMNS
        assert "bathrooms" not in NUMERIC_COLUMNS

    def test_has_per_person_features(self):
        """NUMERIC_COLUMNS should contain per-person engineered features."""
        from review_aggregator.correlation_analyzer import NUMERIC_COLUMNS

        assert "BEDS_PER_PERSON" in NUMERIC_COLUMNS
        assert "BATHS_PER_PERSON" in NUMERIC_COLUMNS
        assert "BEDROOMS_PER_PERSON" in NUMERIC_COLUMNS

    def test_has_dist_to_poi(self):
        """NUMERIC_COLUMNS should still contain DIST_TO_POI."""
        from review_aggregator.correlation_analyzer import NUMERIC_COLUMNS

        assert "DIST_TO_POI" in NUMERIC_COLUMNS
