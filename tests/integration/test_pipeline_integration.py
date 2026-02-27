"""
Integration tests for the AirBNB Review Scraper pipeline.
Tests cross-component interactions with mocked external services.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestPropertyAggregatorIntegration:
    """Integration tests for PropertyRagAggregator with OpenAI and caching."""

    @pytest.fixture
    def property_aggregator(self, tmp_logs_dir):
        """Create a PropertyRagAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {
                    "model": "gpt-4.1-mini",
                    "enable_cost_tracking": True,
                }
            }
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.property_review_aggregator import (
                    PropertyRagAggregator,
                )

                agg = PropertyRagAggregator(
                    zipcode="97067",
                    num_listings_to_summarize=3,
                )
                agg.openai_aggregator.cost_tracker.log_file = str(
                    tmp_logs_dir / "cost.json"
                )
                return agg

    def test_aggregator_to_cache_flow(
        self, property_aggregator, sample_reviews, sample_prompt
    ):
        """Test that reviews flow through aggregator and return a summary."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated summary"

        with patch.object(
            property_aggregator.openai_aggregator.client.chat.completions,
            "create",
            return_value=mock_response,
        ):
            review_strings = [f"{r['rating']} {r['review']}" for r in sample_reviews]
            result = property_aggregator.openai_aggregator.generate_summary(
                reviews=review_strings,
                prompt=sample_prompt,
                listing_id="test_listing",
            )

            assert result == "Generated summary"

    def test_cost_tracker_accumulates_requests(
        self, property_aggregator, sample_reviews, sample_prompt
    ):
        """Test that cost tracker accumulates across multiple requests."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary"

        with patch.object(
            property_aggregator.openai_aggregator.client.chat.completions,
            "create",
            return_value=mock_response,
        ):
            # Make multiple requests
            for i in range(3):
                review_strings = [
                    f"{r['rating']} {r['review']}" for r in sample_reviews
                ]
                property_aggregator.openai_aggregator.generate_summary(
                    reviews=review_strings,
                    prompt=sample_prompt,
                    listing_id=f"cost_test_{i}",
                )

            stats = property_aggregator.openai_aggregator.cost_tracker.session_stats
            assert stats.get("total_requests", 0) == 3

    def test_mean_rating_integration(self, property_aggregator, sample_reviews):
        """Test mean rating calculation with real review data structure."""
        mean = property_aggregator.get_listing_id_mean_rating(sample_reviews)

        # Verify it's a valid rating in expected range
        assert 1.0 <= mean <= 5.0
        assert isinstance(mean, float)


class TestAreaAggregatorIntegration:
    """Integration tests for AreaRagAggregator with filesystem and OpenAI."""

    @pytest.fixture
    def area_aggregator(self, tmp_logs_dir, tmp_path):
        """Create an AreaRagAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {
                    "model": "gpt-4.1-mini",
                    "enable_cost_tracking": True,
                }
            }
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.area_review_aggregator import (
                    AreaRagAggregator,
                )

                agg = AreaRagAggregator(
                    zipcode="97067",
                    num_listings=5,
                    output_dir=str(tmp_path),
                )
                agg.openai_aggregator.cost_tracker.log_file = str(
                    tmp_logs_dir / "cost.json"
                )
                return agg

    def test_area_aggregator_loads_and_aggregates_summaries(
        self, area_aggregator, sample_property_summary
    ):
        """Test that AreaRagAggregator loads summaries and calls OpenAI."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Area summary for Mt Hood region"

        # Mock the os.listdir to return matching files
        with patch(
            "os.listdir",
            return_value=[
                "listing_summary_97067_12345678.json",
                "listing_summary_97067_87654321.json",
                "listing_summary_97067_11111111.json",
            ],
        ):
            with patch(
                "review_aggregator.area_review_aggregator.load_json_file"
            ) as mock_load:
                # Setup mock to return summary data then prompt then config
                mock_load.side_effect = [
                    {"12345678": sample_property_summary},
                    {"87654321": "Another great property with mountain views."},
                    {"11111111": "Cozy cabin perfect for families."},
                    {
                        "gpt4o_mini_generate_prompt_structured": "Summarize {ZIP_CODE_HERE}"
                    },
                    {"iso_code": "us"},
                ]

                with patch.object(
                    area_aggregator.openai_aggregator.client.chat.completions,
                    "create",
                    return_value=mock_response,
                ):
                    area_aggregator.rag_description_generation_chain()

                    # Verify markdown report was created
                    md_path = Path(area_aggregator.output_dir) / "area_summary_97067.md"
                    assert md_path.exists()
                    md_content = md_path.read_text()
                    assert "# Area Summary: 97067" in md_content
                    assert "**Properties Analyzed:** 3" in md_content


class TestCostTrackerIntegration:
    """Integration tests for CostTracker."""

    @pytest.fixture
    def cost_tracker(self, tmp_logs_dir):
        """Create a CostTracker for testing."""
        with patch("utils.cost_tracker.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_cost_tracking": True}}
            from utils.cost_tracker import CostTracker

            ct = CostTracker(log_file=str(tmp_logs_dir / "cost.json"))
            return ct

    def test_session_accumulation(self, cost_tracker, sample_reviews, sample_prompt):
        """Test that session stats accumulate correctly."""
        review_strings = [f"{r['rating']} {r['review']}" for r in sample_reviews]

        # Track multiple requests
        for i in range(5):
            cost_tracker.track_request(
                listing_id=f"session_test_{i}",
                prompt=sample_prompt,
                reviews=review_strings,
                response=f"Response {i}",
                success=True,
                cached=False,
                chunk_info=None,
            )

        stats = cost_tracker.session_stats
        assert stats.get("total_requests", 0) == 5
        assert stats.get("successful_requests", 0) == 5

    def test_cost_calculation(self, cost_tracker):
        """Test cost calculation with known token counts."""
        # Cost for 1M input tokens = $0.40, 1M output tokens = $1.60
        # 1000 input + 500 output should be:
        # (1000 / 1_000_000) * 0.40 + (500 / 1_000_000) * 1.60
        # = 0.0004 + 0.0008 = 0.0012
        cost = cost_tracker.calculate_cost(input_tokens=1000, output_tokens=500)

        assert cost == pytest.approx(0.0012, rel=0.01)

    def test_reset_session(self, cost_tracker, sample_reviews, sample_prompt):
        """Test session reset clears accumulated stats."""
        review_strings = [f"{r['rating']} {r['review']}" for r in sample_reviews]

        # Track some requests
        cost_tracker.track_request(
            listing_id="reset_test",
            prompt=sample_prompt,
            reviews=review_strings,
            response="Response",
            success=True,
            cached=False,
            chunk_info=None,
        )

        # Reset
        cost_tracker.reset_session()

        stats = cost_tracker.session_stats
        assert stats.get("total_requests", 0) == 0


class TestEndToEndPipeline:
    """End-to-end integration tests for full pipeline flows."""

    def test_property_to_area_pipeline(self, sample_property_summary, tmp_path):
        """Test flow from property summaries to area summary."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_config:
            mock_config.return_value = {"openai": {"enable_cost_tracking": False}}
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.area_review_aggregator import (
                    AreaRagAggregator,
                )

                aggregator = AreaRagAggregator(
                    zipcode="97067",
                    num_listings=5,
                    output_dir=str(tmp_path),
                )

                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Complete area summary"

                # Mock the filesystem interactions
                with patch(
                    "os.listdir",
                    return_value=[
                        "listing_summary_97067_123.json",
                        "listing_summary_97067_456.json",
                    ],
                ):
                    with patch(
                        "review_aggregator.area_review_aggregator.load_json_file"
                    ) as mock_load:
                        mock_load.side_effect = [
                            {"123": sample_property_summary},
                            {"456": "Another property summary"},
                            {
                                "gpt4o_mini_generate_prompt_structured": "Summarize area {ZIP_CODE_HERE}"
                            },
                            {"iso_code": "us"},
                        ]

                        with patch.object(
                            aggregator.openai_aggregator.client.chat.completions,
                            "create",
                            return_value=mock_response,
                        ):
                            aggregator.rag_description_generation_chain()

                            # Verify markdown report was created
                            md_path = tmp_path / "area_summary_97067.md"
                            assert md_path.exists()
                            md_content = md_path.read_text()
                            assert "# Area Summary: 97067" in md_content
                            assert "**Properties Analyzed:** 2" in md_content
                            assert "Complete area summary" in md_content


class TestPipelineCacheIntegration:
    """Integration tests for PipelineCacheManager with pipeline stages."""

    @pytest.fixture
    def pipeline_cache(self, tmp_path):
        """Create a PipelineCacheManager with a temporary metadata path."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager()

    def test_stage_fresh_when_all_outputs_exist(self, pipeline_cache, tmp_path):
        """Test that a stage with all expected outputs on disk is fresh."""
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_file = search_dir / "search_results_97067.json"
        search_file.write_text('[{"room_id": "111"}]')

        pipeline_cache.STAGE_OUTPUT_DIRS = {
            **pipeline_cache.STAGE_OUTPUT_DIRS,
            "search_results": str(search_dir),
        }

        assert pipeline_cache.is_stage_fresh("search_results", "97067") is True

    def test_force_refresh_causes_rerun(self, tmp_path):
        """Test that force_refresh flag overrides cached status."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_details_scrape": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            cache = PipelineCacheManager()

        # Even with files on disk, force_refresh makes it stale
        assert cache.is_stage_fresh("details_scrape", "97067") is False

    def test_per_file_skip_in_scraper(self, pipeline_cache, tmp_path):
        """Test that scrapers skip individual files that are cached by mtime."""
        output_file = str(tmp_path / "reviews_97067_12345.json")
        with open(output_file, "w") as f:
            json.dump({"12345": [{"review": "Great", "rating": 5}]}, f)

        assert pipeline_cache.is_file_fresh("reviews_scrape", output_file) is True

    def test_deleted_file_not_cached(self, pipeline_cache, tmp_path):
        """Test that a deleted file is not considered fresh."""
        output_file = str(tmp_path / "deleted.json")
        with open(output_file, "w") as f:
            json.dump({}, f)
        os.remove(output_file)

        assert pipeline_cache.is_file_fresh("details_scrape", output_file) is False

    def test_force_refresh_wipes_output_directory(self, tmp_path):
        """Test that clear_stage wipes the output directory when force_refresh is set."""
        output_dir = tmp_path / "outputs" / "04_reviews_scrape"
        output_dir.mkdir(parents=True)

        # Plant a stale file that should be cleaned up
        stale_file = output_dir / "reviews_97067_old_listing.json"
        stale_file.write_text("{}")

        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_reviews_scrape": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            cache = PipelineCacheManager()

        # Simulate what main.py does: check freshness, then clear_stage
        assert cache.is_stage_fresh("reviews_scrape") is False

        cache.STAGE_OUTPUT_DIRS = {"reviews_scrape": str(output_dir)}
        cache.clear_stage("reviews_scrape")

        # Stale file should be gone, directory should remain
        assert output_dir.exists()
        assert not stale_file.exists()
        assert list(output_dir.iterdir()) == []

    def test_cascade_force_refresh_marks_downstream_stale(self, tmp_path):
        """Test that cascading force-refresh makes downstream analysis stages stale."""

        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            cache = PipelineCacheManager()

        # Simulate reviews being not-fresh → cascade downstream
        cache.cascade_force_refresh("reviews_scrape")

        # Non-analysis downstream stages are NOT cascaded
        assert cache.force_refresh_flags["comp_sets"] is False
        assert cache.force_refresh_flags["listing_summaries"] is False

        # Analysis stages ARE cascaded and therefore stale
        assert cache.is_stage_fresh("area_summary", "97067") is False
        assert cache.force_refresh_flags["area_summary"] is True
        assert cache.force_refresh_flags["correlation_results"] is True
        assert cache.force_refresh_flags["description_analysis"] is True
