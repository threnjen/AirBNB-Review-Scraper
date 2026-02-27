"""
Unit tests for review_aggregator/area_review_aggregator.py
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestAreaRagAggregator:
    """Tests for AreaRagAggregator class."""

    @pytest.fixture
    def aggregator(self):
        """Create an AreaRagAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.area_review_aggregator import (
                    AreaRagAggregator,
                )

                return AreaRagAggregator(
                    zipcode="97067",
                    num_listings=5,
                    review_thresh_to_include_prop=5,
                )

    def test_initialization_defaults(self):
        """Test AreaRagAggregator initializes with default values."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.area_review_aggregator import (
                    AreaRagAggregator,
                )

                agg = AreaRagAggregator()

                assert agg.num_listings == 3
                assert agg.review_thresh_to_include_prop == 5
                assert agg.zipcode == "00501"
                assert agg.overall_mean == 0.0

    def test_initialization_custom_params(self, aggregator):
        """Test AreaRagAggregator initializes with custom parameters."""
        assert aggregator.zipcode == "97067"
        assert aggregator.num_listings == 5
        assert aggregator.review_thresh_to_include_prop == 5

    def test_openai_aggregator_present(self, aggregator):
        """Test that OpenAIAggregator is present."""
        assert aggregator.openai_aggregator is not None

    def test_rag_chain_no_summary_files_returns_early(self, aggregator):
        """Test rag_description_generation_chain returns early when no summary files exist."""
        with patch("os.listdir", return_value=[]):
            result = aggregator.rag_description_generation_chain()

            assert result is None

    def test_rag_chain_no_matching_zipcode_files(self, aggregator):
        """Test rag_description_generation_chain returns early when no files match zipcode."""
        with patch(
            "os.listdir",
            return_value=[
                "listing_summary_12345_abc.json",
                "listing_summary_99999_def.json",
            ],
        ):
            result = aggregator.rag_description_generation_chain()

            # No files match zipcode 97067
            assert result is None

    def test_rag_chain_with_valid_summaries(self, aggregator):
        """Test rag_description_generation_chain processes valid summaries."""
        mock_summary_data = {"listing123": "Great property with amazing views."}
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Area summary text"

        with patch(
            "os.listdir", return_value=["listing_summary_97067_listing123.json"]
        ):
            with patch(
                "review_aggregator.area_review_aggregator.load_json_file"
            ) as mock_load:
                mock_load.side_effect = [
                    mock_summary_data,
                    {
                        "gpt4o_mini_generate_prompt_structured": "Summarize {ZIP_CODE_HERE} area"
                    },
                    {"iso_code": "us"},
                ]
                with patch(
                    "review_aggregator.area_review_aggregator.AreaRagAggregator.save_results"
                ) as mock_save_results:
                    with patch.object(
                        aggregator.openai_aggregator.client.chat.completions,
                        "create",
                        return_value=mock_response,
                    ):
                        aggregator.rag_description_generation_chain()

                        mock_save_results.assert_called_once()
                        call_kwargs = mock_save_results.call_args.kwargs
                        assert call_kwargs["num_properties"] == 1
                        assert call_kwargs["iso_code"] == "us"
                        assert call_kwargs["area_summary"] == "Area summary text"

    def test_rag_chain_limits_to_num_listings(self):
        """Test that only num_listings files are processed."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_cfg:
            mock_cfg.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.area_review_aggregator import (
                    AreaRagAggregator,
                )

                limited_aggregator = AreaRagAggregator(
                    zipcode="97067",
                    num_listings=2,
                )

        mock_files = [
            "listing_summary_97067_a.json",
            "listing_summary_97067_b.json",
            "listing_summary_97067_c.json",
            "listing_summary_97067_d.json",
        ]
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary"

        with patch("os.listdir", return_value=mock_files):
            with patch(
                "review_aggregator.area_review_aggregator.load_json_file"
            ) as mock_load:
                mock_load.side_effect = [
                    {"listing_a": "Summary A"},
                    {"listing_b": "Summary B"},
                    {"gpt4o_mini_generate_prompt_structured": "Prompt"},
                    {"iso_code": "us"},
                ]
                with patch(
                    "review_aggregator.area_review_aggregator.AreaRagAggregator.save_results"
                ):
                    with patch.object(
                        limited_aggregator.openai_aggregator.client.chat.completions,
                        "create",
                        return_value=mock_response,
                    ):
                        limited_aggregator.rag_description_generation_chain()

                        # Should only load 2 summary files (num_listings=2) + prompt + config
                        assert mock_load.call_count == 4

    def test_rag_chain_skips_empty_summaries(self, aggregator):
        """Test that empty summary texts are skipped."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Result"

        with patch(
            "os.listdir",
            return_value=[
                "listing_summary_97067_a.json",
                "listing_summary_97067_b.json",
            ],
        ):
            with patch(
                "review_aggregator.area_review_aggregator.load_json_file"
            ) as mock_load:
                mock_load.side_effect = [
                    {"listing_a": ""},  # Empty summary
                    {"listing_b": "Valid summary"},  # Valid summary
                    {"gpt4o_mini_generate_prompt_structured": "Prompt"},
                    {"iso_code": "us"},
                ]
                with patch(
                    "review_aggregator.area_review_aggregator.AreaRagAggregator.save_results"
                ) as mock_save_results:
                    with patch.object(
                        aggregator.openai_aggregator.client.chat.completions,
                        "create",
                        return_value=mock_response,
                    ):
                        aggregator.rag_description_generation_chain()

                        # Verify that save_results was called
                        assert mock_save_results.called
                        # Verify output shows 1 property analyzed (the non-empty one)
                        call_kwargs = mock_save_results.call_args.kwargs
                        assert call_kwargs["num_properties"] == 1

    def test_rag_chain_all_empty_summaries_returns_early(self, aggregator):
        """Test that if all summaries are empty, the method returns early."""
        with patch("os.listdir", return_value=["listing_summary_97067_a.json"]):
            with patch(
                "review_aggregator.area_review_aggregator.load_json_file"
            ) as mock_load:
                mock_load.return_value = {"listing_a": ""}  # Empty summary

                result = aggregator.rag_description_generation_chain()

                # Should return early since no valid summaries
                assert result is None

    def test_output_structure(self, aggregator):
        """Test that output JSON has correct structure."""
        mock_summary_data = {"listing123": "Test summary"}
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated area summary"

        with patch("os.listdir", return_value=["listing_summary_97067_x.json"]):
            with patch(
                "review_aggregator.area_review_aggregator.load_json_file"
            ) as mock_load:
                mock_load.side_effect = [
                    mock_summary_data,
                    {"gpt4o_mini_generate_prompt_structured": "Prompt"},
                    {"iso_code": "us"},
                ]
                with patch(
                    "review_aggregator.area_review_aggregator.AreaRagAggregator.save_results"
                ) as mock_save_results:
                    with patch.object(
                        aggregator.openai_aggregator.client.chat.completions,
                        "create",
                        return_value=mock_response,
                    ):
                        aggregator.rag_description_generation_chain()

                        call_kwargs = mock_save_results.call_args.kwargs
                        assert call_kwargs["num_properties"] == 1
                        assert call_kwargs["iso_code"] == "us"
                        assert call_kwargs["area_summary"] == "Generated area summary"


class TestSaveResults:
    """Tests for AreaRagAggregator.save_results."""

    @pytest.fixture
    def aggregator(self):
        """Create an AreaRagAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.area_review_aggregator import (
                    AreaRagAggregator,
                )

                return AreaRagAggregator(
                    zipcode="97067",
                    num_listings=5,
                    review_thresh_to_include_prop=5,
                )

    def test_creates_output_files(self, aggregator, tmp_path):
        """Should create JSON stats and Markdown report files."""
        aggregator.output_dir = str(tmp_path)

        aggregator.save_results(
            num_properties=42,
            iso_code="us",
            area_summary="## Area Description\nCozy cabins near Mt Hood.",
        )

        json_path = tmp_path / "area_summary_97067.json"
        md_path = tmp_path / "area_summary_97067.md"

        assert json_path.exists()
        assert md_path.exists()

        stats = json.loads(json_path.read_text())
        assert stats["zipcode"] == "97067"
        assert stats["num_properties_analyzed"] == 42
        assert "Cozy cabins" in stats["area_summary"]

    def test_markdown_contains_header_and_body(self, aggregator, tmp_path):
        """Markdown report should have a structured header and LLM body."""
        aggregator.output_dir = str(tmp_path)

        aggregator.save_results(
            num_properties=10,
            iso_code="us",
            area_summary="## Positives\n- **Cleanliness**: spotless",
        )

        md_content = (tmp_path / "area_summary_97067.md").read_text()

        assert "# Area Summary: 97067" in md_content
        assert "**ISO Code:** us" in md_content
        assert "**Properties Analyzed:** 10" in md_content
        assert "---" in md_content
        assert "## Positives" in md_content
        assert "**Cleanliness**" in md_content

    def test_creates_output_dir_if_missing(self, aggregator, tmp_path):
        """Should create the output directory if it does not exist."""
        nested_dir = tmp_path / "nested" / "reports"
        aggregator.output_dir = str(nested_dir)

        aggregator.save_results(
            num_properties=1,
            iso_code="gb",
            area_summary="Summary text",
        )

        assert (nested_dir / "area_summary_97067.md").exists()
        assert (nested_dir / "area_summary_97067.json").exists()
