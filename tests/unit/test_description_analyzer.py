"""
Unit tests for review_aggregator/description_analyzer.py

TDD: These tests are written BEFORE the implementation.
They should fail (red) until description_analyzer.py is created.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest


class TestDescriptionAnalyzer:
    """Tests for DescriptionAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a DescriptionAnalyzer with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.description_analyzer import (
                    DescriptionAnalyzer,
                )

                return DescriptionAnalyzer(zipcode="97067")

    @pytest.fixture
    def sample_property_df(self):
        """DataFrame mimicking the amenities matrix CSV with known linear ADR pattern.

        Includes binary amenity flags (SYSTEM_*) to verify dynamic feature discovery.
        """
        # ADR = 100 * bedrooms + 50 * capacity + noise
        # This makes it easy to verify residuals
        return pd.DataFrame(
            {
                "ADR": [350, 500, 250, 700, 300, 450, 600, 200],
                "capacity": [4, 6, 2, 10, 4, 6, 8, 2],
                "bedrooms": [2, 3, 1, 5, 2, 3, 4, 1],
                "beds": [3, 5, 2, 8, 3, 4, 6, 2],
                "bathrooms": [1, 2, 1, 3, 1, 2, 2, 1],
                "SYSTEM_POOL": [1, 1, 0, 1, 0, 0, 1, 0],
                "SYSTEM_PETS": [0, 1, 0, 1, 1, 0, 1, 0],
                "Days_Avail": [200, 300, 150, 350, 180, 250, 320, 100],
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
        residuals, r_squared, features = analyzer.compute_size_adjusted_residuals(
            sample_property_df
        )

        assert isinstance(residuals, pd.Series)
        assert len(residuals) == len(sample_property_df)
        assert all(idx in residuals.index for idx in sample_property_df.index)
        assert isinstance(features, list)
        assert len(features) > 0

    def test_residuals_sum_near_zero(self, analyzer, sample_property_df):
        """OLS residuals should sum to approximately zero."""
        residuals, r_squared, features = analyzer.compute_size_adjusted_residuals(
            sample_property_df
        )

        assert abs(residuals.sum()) < 1e-6

    def test_r_squared_between_zero_and_one(self, analyzer, sample_property_df):
        """R-squared should be between 0 and 1."""
        residuals, r_squared, features = analyzer.compute_size_adjusted_residuals(
            sample_property_df
        )

        assert 0.0 <= r_squared <= 1.0

    def test_perfect_linear_data_has_near_zero_residuals(self, analyzer):
        """When ADR is exactly linear in features, residuals should be ~0."""
        # ADR = 100*bedrooms + 50*capacity + 25*beds + 10*bathrooms
        # Need rows > num_features + 1 for OLS
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

        residuals, r_squared, features = analyzer.compute_size_adjusted_residuals(df)

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

        residuals, r_squared, features = analyzer.compute_size_adjusted_residuals(df)

        assert len(residuals) == 6
        assert "p2" not in residuals.index
        assert "p4" not in residuals.index

    def test_discovers_all_numeric_columns(self, analyzer):
        """Should use all numeric columns except ADR as regression features."""
        df = pd.DataFrame(
            {
                "ADR": [300, 400, 500, 200, 350, 450],
                "capacity": [4, 6, 8, 3, 5, 7],
                "bedrooms": [2, 3, 3, 1, 2, 3],
                "SYSTEM_POOL": [1, 0, 1, 0, 1, 0],
                "SYSTEM_PETS": [0, 1, 1, 0, 0, 1],
            },
            index=["a", "b", "c", "d", "e", "f"],
        )

        residuals, r_squared, features = analyzer.compute_size_adjusted_residuals(df)

        assert "capacity" in features
        assert "bedrooms" in features
        assert "SYSTEM_POOL" in features
        assert "SYSTEM_PETS" in features
        assert "ADR" not in features

    def test_includes_zero_values_in_regression(self, analyzer):
        """Zero values (e.g. 0 bedrooms, 0 for binary amenities) should be included."""
        df = pd.DataFrame(
            {
                "ADR": [300, 400, 500, 200, 350, 450],
                "capacity": [4, 6, 8, 3, 5, 7],
                "bedrooms": [2, 0, 3, 1, 2, 3],
                "SYSTEM_POOL": [1, 0, 1, 0, 1, 0],
            },
            index=["a", "b", "c", "d", "e", "f"],
        )

        residuals, r_squared, features = analyzer.compute_size_adjusted_residuals(df)

        # Row "b" with 0 bedrooms should be included
        assert "b" in residuals.index
        assert len(residuals) == 6


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


class TestLoadDescriptions(TestDescriptionAnalyzer):
    """Tests for load_descriptions with hardened error handling."""

    def test_returns_empty_dict_when_file_missing(self, analyzer):
        """Should return empty dict when descriptions file doesn't exist."""
        with patch("os.path.exists", return_value=False):
            result = analyzer.load_descriptions()

        assert result == {}

    def test_returns_empty_dict_on_non_dict_json(self, analyzer):
        """Should return empty dict when JSON is not an object (e.g. list)."""
        with patch("os.path.exists", return_value=True):
            with patch(
                "review_aggregator.description_analyzer.load_json_file",
                return_value=["not", "a", "dict"],
            ):
                result = analyzer.load_descriptions()

        assert result == {}

    def test_returns_empty_dict_on_load_failure(self, analyzer):
        """Should return empty dict when file loading raises an exception."""
        with patch("os.path.exists", return_value=True):
            with patch(
                "review_aggregator.description_analyzer.load_json_file",
                side_effect=Exception("corrupt file"),
            ):
                result = analyzer.load_descriptions()

        assert result == {}

    def test_valid_descriptions_returned(self, analyzer):
        """Should return string descriptions, joining lists."""
        raw = {
            "prop_1": "A nice cabin",
            "prop_2": ["Part one.", "Part two."],
            "prop_3": 12345,
        }
        with patch("os.path.exists", return_value=True):
            with patch(
                "review_aggregator.description_analyzer.load_json_file",
                return_value=raw,
            ):
                result = analyzer.load_descriptions()

        assert result["prop_1"] == "A nice cabin"
        assert result["prop_2"] == "Part one. Part two."
        assert "prop_3" not in result


class TestScoreSingleDescription(TestDescriptionAnalyzer):
    """Tests for score_single_description."""

    def test_prompt_template_replacement(self, analyzer):
        """Prompt template placeholders should be filled correctly."""
        template = "Score property {PROPERTY_ID}: {DESCRIPTION}"

        with patch(
            "review_aggregator.description_analyzer.OpenAIAggregator.generate_summary"
        ) as mock_gen:
            mock_gen.return_value = '{"evocativeness": 5}'
            result = analyzer.score_single_description(
                "prop_1", "A cozy cabin", template
            )

            call_args = mock_gen.call_args
            sent_reviews = call_args.kwargs.get(
                "reviews", call_args.args[1] if len(call_args.args) > 1 else None
            )
            assert "prop_1" in sent_reviews[0]
            assert "A cozy cabin" in sent_reviews[0]
            assert result["evocativeness"] == 5

    def test_returns_empty_on_llm_failure(self, analyzer):
        """Should return empty dict when LLM returns None."""
        with patch(
            "review_aggregator.description_analyzer.OpenAIAggregator.generate_summary",
            return_value=None,
        ):
            result = analyzer.score_single_description("prop_1", "desc", "template")

        assert result == {}


class TestScoreAllDescriptions(TestDescriptionAnalyzer):
    """Tests for score_all_descriptions."""

    def test_scores_matching_properties(self, analyzer, sample_descriptions):
        """Should score descriptions that match residual indices."""
        residuals = pd.Series(
            [10, 20, 30], index=["prop_1", "prop_2", "prop_3"], name="adr_residual"
        )

        with patch(
            "review_aggregator.description_analyzer.OpenAIAggregator.generate_summary",
            return_value='{"evocativeness": 7, "specificity": 5}',
        ):
            result = analyzer.score_all_descriptions(
                residuals, sample_descriptions, "Score: {DESCRIPTION}"
            )

        assert len(result) == 3
        assert "evocativeness" in result.columns

    def test_skips_missing_descriptions(self, analyzer):
        """Should skip properties without descriptions."""
        residuals = pd.Series([10, 20], index=["prop_1", "prop_99"])
        descriptions = {"prop_1": "A cabin"}

        with patch(
            "review_aggregator.description_analyzer.OpenAIAggregator.generate_summary",
            return_value='{"evocativeness": 5}',
        ):
            result = analyzer.score_all_descriptions(
                residuals, descriptions, "Score: {DESCRIPTION}"
            )

        assert len(result) == 1
        assert "prop_1" in result.index

    def test_handles_list_descriptions(self, analyzer):
        """Should join list-type descriptions into a single string."""
        residuals = pd.Series([10], index=["prop_1"])
        descriptions = {"prop_1": ["Part one.", "Part two."]}

        with patch(
            "review_aggregator.description_analyzer.OpenAIAggregator.generate_summary",
            return_value='{"evocativeness": 6}',
        ):
            result = analyzer.score_all_descriptions(
                residuals, descriptions, "{DESCRIPTION}"
            )

        assert len(result) == 1

    def test_returns_empty_df_when_all_scoring_fails(self, analyzer):
        """Should return empty DataFrame when LLM fails for all properties."""
        residuals = pd.Series([10], index=["prop_1"])
        descriptions = {"prop_1": "desc"}

        with patch(
            "review_aggregator.description_analyzer.OpenAIAggregator.generate_summary",
            return_value=None,
        ):
            result = analyzer.score_all_descriptions(
                residuals, descriptions, "template"
            )

        assert result.empty


class TestGenerateSynthesis(TestDescriptionAnalyzer):
    """Tests for generate_synthesis."""

    def test_synthesis_prompt_substitution(self, analyzer, sample_descriptions):
        """Should fill all template placeholders in the synthesis prompt."""
        residuals = pd.Series(
            [100, 50, -50, -100],
            index=["prop_1", "prop_2", "prop_3", "prop_4"],
        )
        scores_df = pd.DataFrame(
            {"evocativeness": [8, 7, 3, 2]},
            index=["prop_1", "prop_2", "prop_3", "prop_4"],
        )
        correlation_results = {"evocativeness": {"correlation": 0.85, "n": 4}}
        template = (
            "Zipcode: {ZIPCODE}, R²: {R_SQUARED}, N: {NUM_PROPERTIES}\n"
            "{CORRELATION_TABLE}\n{HIGH_PREMIUM_DESCRIPTIONS}\n"
            "{LOW_PREMIUM_DESCRIPTIONS}"
        )

        with patch(
            "review_aggregator.description_analyzer.OpenAIAggregator.generate_summary"
        ) as mock_gen:
            mock_gen.return_value = "Synthesis report"
            result = analyzer.generate_synthesis(
                r_squared=0.75,
                correlation_results=correlation_results,
                residuals=residuals,
                descriptions=sample_descriptions,
                scores_df=scores_df,
                synthesis_prompt_template=template,
            )

            assert result == "Synthesis report"
            call_args = mock_gen.call_args
            sent_reviews = call_args.kwargs.get(
                "reviews", call_args.args[1] if len(call_args.args) > 1 else None
            )
            sent_prompt = sent_reviews[0]
            assert "97067" in sent_prompt
            assert "0.750" in sent_prompt
            assert "4" in sent_prompt

    def test_handles_missing_residual_for_property(self, analyzer):
        """Should skip properties whose IDs don't match any residual index."""
        residuals = pd.Series([100], index=["prop_1"])
        descriptions = {"prop_1": "Good cabin", "prop_999": "Ghost property"}
        scores_df = pd.DataFrame({"evocativeness": [8]}, index=["prop_1"])

        with patch(
            "review_aggregator.description_analyzer.OpenAIAggregator.generate_summary",
            return_value="Report",
        ):
            # Should not raise IndexError
            result = analyzer.generate_synthesis(
                r_squared=0.5,
                correlation_results={},
                residuals=residuals,
                descriptions=descriptions,
                scores_df=scores_df,
                synthesis_prompt_template="{ZIPCODE}{R_SQUARED}{CORRELATION_TABLE}{HIGH_PREMIUM_DESCRIPTIONS}{LOW_PREMIUM_DESCRIPTIONS}{NUM_PROPERTIES}",
            )

        assert result == "Report"


class TestSaveResults(TestDescriptionAnalyzer):
    """Tests for save_results."""

    def test_creates_output_files(self, analyzer, tmp_path):
        """Should create JSON stats and Markdown files."""
        analyzer.output_dir = str(tmp_path)
        analyzer.reports_dir = str(tmp_path)
        residuals = pd.Series([10, -10], index=["p1", "p2"])
        scores_df = pd.DataFrame({"evocativeness": [8, 3]}, index=["p1", "p2"])
        features = ["capacity", "bedrooms", "SYSTEM_POOL"]

        analyzer.save_results(
            r_squared=0.75,
            correlation_results={"evocativeness": {"correlation": 0.8, "n": 2}},
            residuals=residuals,
            scores_df=scores_df,
            synthesis="Test synthesis content",
            features=features,
        )

        json_path = tmp_path / "description_quality_stats_97067.json"
        md_path = tmp_path / "description_quality_97067.md"

        assert json_path.exists()
        assert md_path.exists()

        import json

        stats = json.loads(json_path.read_text())
        assert stats["zipcode"] == "97067"
        assert stats["regression_r_squared"] == 0.75
        assert stats["num_properties_analyzed"] == 2
        assert stats["regression_features_used"] == features

        md_content = md_path.read_text()
        assert "Test synthesis content" in md_content
        assert "97067" in md_content


class TestRunAnalysis(TestDescriptionAnalyzer):
    """Tests for run_analysis orchestrator."""

    def test_exits_early_on_empty_property_data(self, analyzer):
        """Should exit without error when property data is empty."""
        with patch(
            "review_aggregator.description_analyzer.DescriptionAnalyzer.load_property_data",
            return_value=pd.DataFrame(),
        ):
            # Should not raise
            analyzer.run_analysis()

    def test_exits_early_on_empty_descriptions(self, analyzer, sample_property_df):
        """Should exit without error when descriptions are empty."""
        with patch(
            "review_aggregator.description_analyzer.DescriptionAnalyzer.load_property_data",
            return_value=sample_property_df,
        ):
            with patch(
                "review_aggregator.description_analyzer.DescriptionAnalyzer.load_descriptions",
                return_value={},
            ):
                analyzer.run_analysis()

    def test_exits_early_on_failed_residuals(self, analyzer, sample_property_df):
        """Should exit when regression fails (not enough data)."""
        tiny_df = sample_property_df.head(2)
        with patch(
            "review_aggregator.description_analyzer.DescriptionAnalyzer.load_property_data",
            return_value=tiny_df,
        ):
            with patch(
                "review_aggregator.description_analyzer.DescriptionAnalyzer.load_descriptions",
                return_value={"p1": "desc"},
            ):
                # 2 properties < 5 needed for regression
                analyzer.run_analysis()


class TestComputeResidualsWithBadFeatures(TestDescriptionAnalyzer):
    """Tests for filtering NaN features in regression."""

    def test_excludes_nan_features(self, analyzer):
        """Properties with NaN feature values should be excluded."""
        df = pd.DataFrame(
            {
                "ADR": [300, 400, 500, 200, 350, 450],
                "capacity": [4, 6, 8, 3, 5, 7],
                "bedrooms": [2, 3, float("nan"), 1, 2, 3],
                "beds": [3, 5, 6, 2, 4, 5],
                "bathrooms": [1, 2, 2, 1, 1, 2],
            },
            index=["a", "b", "c", "d", "e", "f"],
        )

        residuals, r_squared, features = analyzer.compute_size_adjusted_residuals(df)

        assert "c" not in residuals.index
        assert len(residuals) == 5


class TestLoadPropertyDataAirdnaFilter(TestDescriptionAnalyzer):
    """Tests for AirDNA-data filtering in load_property_data."""

    def test_excludes_rows_without_airdna_data(self, analyzer):
        """Properties with has_airdna_data=False should be excluded."""
        df = pd.DataFrame(
            {
                "ADR": [200.0, 300.0, 150.0],
                "has_airdna_data": [True, True, False],
                "capacity": [4, 6, 3],
                "bedrooms": [2, 3, 1],
            },
            index=["p1", "p2", "p3"],
        )
        df.index.name = "property_id"

        with patch("os.path.exists", return_value=True):
            with patch("pandas.read_csv", return_value=df):
                result = analyzer.load_property_data()

        assert "p1" in result.index
        assert "p2" in result.index
        assert "p3" not in result.index
        assert "has_airdna_data" not in result.columns

    def test_backward_compat_no_flag_column(self, analyzer):
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

    def test_flag_not_used_as_regression_feature(self, analyzer):
        """has_airdna_data column must not appear in regression features."""
        df = pd.DataFrame(
            {
                "ADR": [300, 400, 500, 200, 350, 450],
                "capacity": [4, 6, 8, 3, 5, 7],
                "bedrooms": [2, 3, 3, 1, 2, 3],
                "has_airdna_data": [True, True, True, True, True, True],
            },
            index=["a", "b", "c", "d", "e", "f"],
        )

        with patch("os.path.exists", return_value=True):
            with patch("pandas.read_csv", return_value=df):
                loaded = analyzer.load_property_data()

        assert "has_airdna_data" not in loaded.columns
