"""
Unit tests for review_aggregator/area_review_aggregator.py
"""

import pytest
from unittest.mock import patch, MagicMock


class TestAreaRagAggregator:
    """Tests for AreaRagAggregator class."""

    @pytest.fixture
    def aggregator(self):
        """Create an AreaRagAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {"enable_caching": False, "enable_cost_tracking": False}
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
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
            mock_load.return_value = {
                "openai": {"enable_caching": False, "enable_cost_tracking": False}
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
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
                "generated_summaries_12345_abc.json",
                "generated_summaries_99999_def.json",
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
            "os.listdir", return_value=["generated_summaries_97067_listing123.json"]
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
                    "review_aggregator.area_review_aggregator.save_json_file"
                ) as mock_save:
                    with patch.object(
                        aggregator.openai_aggregator.client.chat.completions,
                        "create",
                        return_value=mock_response,
                    ):
                        aggregator.rag_description_generation_chain()

                        mock_save.assert_called_once()
                        call_args = mock_save.call_args
                        filename = call_args.kwargs.get("filename", "")
                        if not filename and call_args[0]:
                            filename = call_args[0][0]
                        assert "generated_summaries_97067.json" in filename

    def test_rag_chain_limits_to_num_listings(self):
        """Test that only num_listings files are processed."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_cfg:
            mock_cfg.return_value = {
                "openai": {"enable_caching": False, "enable_cost_tracking": False}
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.area_review_aggregator import (
                        AreaRagAggregator,
                    )

                    limited_aggregator = AreaRagAggregator(
                        zipcode="97067",
                        num_listings=2,
                    )

        mock_files = [
            "generated_summaries_97067_a.json",
            "generated_summaries_97067_b.json",
            "generated_summaries_97067_c.json",
            "generated_summaries_97067_d.json",
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
                with patch("review_aggregator.area_review_aggregator.save_json_file"):
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
                "generated_summaries_97067_a.json",
                "generated_summaries_97067_b.json",
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
                    "review_aggregator.area_review_aggregator.save_json_file"
                ) as mock_save:
                    with patch.object(
                        aggregator.openai_aggregator.client.chat.completions,
                        "create",
                        return_value=mock_response,
                    ):
                        aggregator.rag_description_generation_chain()

                        # Verify that save was called (meaning processing completed)
                        assert mock_save.called
                        # Verify output shows 1 property analyzed (the non-empty one)
                        call_args = mock_save.call_args
                        saved_data = call_args.kwargs.get("data")
                        if saved_data is None and len(call_args[0]) > 1:
                            saved_data = call_args[0][1]
                        assert saved_data["num_properties_analyzed"] == 1

    def test_rag_chain_all_empty_summaries_returns_early(self, aggregator):
        """Test that if all summaries are empty, the method returns early."""
        with patch("os.listdir", return_value=["generated_summaries_97067_a.json"]):
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

        with patch("os.listdir", return_value=["generated_summaries_97067_x.json"]):
            with patch(
                "review_aggregator.area_review_aggregator.load_json_file"
            ) as mock_load:
                mock_load.side_effect = [
                    mock_summary_data,
                    {"gpt4o_mini_generate_prompt_structured": "Prompt"},
                    {"iso_code": "us"},
                ]
                with patch(
                    "review_aggregator.area_review_aggregator.save_json_file"
                ) as mock_save:
                    with patch.object(
                        aggregator.openai_aggregator.client.chat.completions,
                        "create",
                        return_value=mock_response,
                    ):
                        aggregator.rag_description_generation_chain()

                        call_args = mock_save.call_args
                        saved_data = call_args.kwargs.get("data")
                        if saved_data is None and len(call_args[0]) > 1:
                            saved_data = call_args[0][1]
                        assert "zipcode" in saved_data
                        assert saved_data["zipcode"] == "97067"
                        assert "num_properties_analyzed" in saved_data
                        assert "area_summary" in saved_data
