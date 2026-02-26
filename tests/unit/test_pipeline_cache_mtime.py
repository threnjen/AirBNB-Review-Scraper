"""
Unit tests for mtime-based PipelineCacheManager.

Tests the filesystem-driven cache: expected_outputs, _is_file_fresh_by_mtime,
is_stage_fresh, get_missing_outputs, should_run_stage, clear_stage_for_zipcode.
No metadata file, no _completed flags — freshness is purely mtime-based.
"""

import json
import os
import time
from unittest.mock import patch

import pytest


class TestExpectedOutputs:
    """Tests for PipelineCacheManager.expected_outputs."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "correlation_metrics": ["adr", "occupancy"],
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager(metadata_path=metadata_path)

    def test_search_returns_single_file(self, cache_manager):
        result = cache_manager.expected_outputs("search", "97067")
        assert result == ["outputs/01_search_results/search_results_97067.json"]

    def test_airdna_returns_listing_files_plus_comp_set(self, cache_manager, tmp_path):
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_results = [{"room_id": "111"}, {"room_id": "222"}]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        result = cache_manager.expected_outputs("airdna", "97067")
        assert "outputs/02_comp_sets/comp_set_97067.json" in result
        assert "outputs/02_comp_sets/listing_111.json" in result
        assert "outputs/02_comp_sets/listing_222.json" in result

    def test_airdna_missing_search_results_returns_empty(self, cache_manager):
        result = cache_manager.expected_outputs("airdna", "99999")
        assert result == []

    def test_reviews_returns_per_listing_files(self, cache_manager, tmp_path):
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_results = [{"room_id": "111"}, {"room_id": "222"}]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        result = cache_manager.expected_outputs("reviews", "97067")
        assert "outputs/03_reviews_scraped/reviews_97067_111.json" in result
        assert "outputs/03_reviews_scraped/reviews_97067_222.json" in result

    def test_details_returns_per_listing_files(self, cache_manager, tmp_path):
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_results = [{"room_id": "111"}, {"id": "333"}]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        result = cache_manager.expected_outputs("details", "97067")
        assert "outputs/04_details_scraped/property_details_111.json" in result
        assert "outputs/04_details_scraped/property_details_333.json" in result

    def test_build_details_returns_five_zipcode_files(self, cache_manager):
        result = cache_manager.expected_outputs("build_details", "97067")
        assert len(result) == 5
        assert (
            "outputs/05_details_results/property_amenities_matrix_97067.csv" in result
        )
        assert (
            "outputs/05_details_results/property_amenities_matrix_cleaned_97067.csv"
            in result
        )
        assert "outputs/05_details_results/house_rules_details_97067.json" in result
        assert "outputs/05_details_results/property_descriptions_97067.json" in result
        assert "outputs/05_details_results/neighborhood_highlights_97067.json" in result

    def test_aggregate_reviews_returns_per_listing_files(self, cache_manager, tmp_path):
        # aggregate_reviews derives from review files on disk
        reviews_dir = tmp_path / "outputs" / "03_reviews_scraped"
        reviews_dir.mkdir(parents=True)
        (reviews_dir / "reviews_97067_111.json").write_text('{"111": []}')
        (reviews_dir / "reviews_97067_222.json").write_text('{"222": []}')
        (reviews_dir / "reviews_90210_999.json").write_text('{"999": []}')
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "reviews": str(reviews_dir),
        }

        result = cache_manager.expected_outputs("aggregate_reviews", "97067")
        assert (
            "outputs/06_generated_summaries/generated_summaries_97067_111.json"
            in result
        )
        assert (
            "outputs/06_generated_summaries/generated_summaries_97067_222.json"
            in result
        )
        # Should NOT include other zipcode's listings
        assert not any("999" in r for r in result)

    def test_aggregate_summaries_returns_two_files(self, cache_manager):
        result = cache_manager.expected_outputs("aggregate_summaries", "97067")
        assert "reports/area_summary_97067.json" in result
        assert "reports/area_summary_97067.md" in result
        assert len(result) == 2

    def test_extract_data_returns_single_file(self, cache_manager):
        result = cache_manager.expected_outputs("extract_data", "97067")
        assert result == ["outputs/07_extracted_data/area_data_97067.json"]

    def test_analyze_correlations_returns_per_metric_files(self, cache_manager):
        result = cache_manager.expected_outputs("analyze_correlations", "97067")
        assert (
            "outputs/08_correlation_results/correlation_stats_adr_97067.json" in result
        )
        assert (
            "outputs/08_correlation_results/correlation_stats_occupancy_97067.json"
            in result
        )
        assert "reports/correlation_insights_adr_97067.md" in result
        assert "reports/correlation_insights_occupancy_97067.md" in result
        assert len(result) == 4

    def test_analyze_descriptions_returns_two_files(self, cache_manager):
        result = cache_manager.expected_outputs("analyze_descriptions", "97067")
        assert (
            "outputs/09_description_analysis/description_quality_stats_97067.json"
            in result
        )
        assert "reports/description_quality_97067.md" in result
        assert len(result) == 2

    def test_unknown_stage_returns_empty(self, cache_manager):
        result = cache_manager.expected_outputs("nonexistent_stage", "97067")
        assert result == []


class TestIsFileFreshByMtime:
    """Tests for mtime-based file freshness."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager(metadata_path=metadata_path)

    def test_fresh_file_returns_true(self, cache_manager, tmp_path):
        test_file = str(tmp_path / "output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)

        assert cache_manager._is_file_fresh_by_mtime(test_file) is True

    def test_missing_file_returns_false(self, cache_manager, tmp_path):
        test_file = str(tmp_path / "nonexistent.json")
        assert cache_manager._is_file_fresh_by_mtime(test_file) is False

    def test_stale_file_returns_false(self, cache_manager, tmp_path):
        test_file = str(tmp_path / "old.json")
        with open(test_file, "w") as f:
            json.dump({}, f)
        # Set mtime to 10 days ago (TTL is 7 days = 168 hours)
        old_time = time.time() - (10 * 24 * 3600)
        os.utime(test_file, (old_time, old_time))

        assert cache_manager._is_file_fresh_by_mtime(test_file) is False


class TestIsFileFreshMtime:
    """Tests for rewritten is_file_fresh using mtime."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager(metadata_path=metadata_path)

    def test_fresh_existing_file(self, cache_manager, tmp_path):
        test_file = str(tmp_path / "reviews_97067_123.json")
        with open(test_file, "w") as f:
            json.dump({}, f)
        assert cache_manager.is_file_fresh("reviews", test_file) is True

    def test_missing_file_returns_false(self, cache_manager, tmp_path):
        test_file = str(tmp_path / "nonexistent.json")
        assert cache_manager.is_file_fresh("reviews", test_file) is False

    def test_stale_file_returns_false(self, cache_manager, tmp_path):
        test_file = str(tmp_path / "reviews_97067_123.json")
        with open(test_file, "w") as f:
            json.dump({}, f)
        old_time = time.time() - (10 * 24 * 3600)
        os.utime(test_file, (old_time, old_time))
        assert cache_manager.is_file_fresh("reviews", test_file) is False

    def test_force_refresh_overrides_freshness(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_reviews": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        test_file = str(tmp_path / "reviews_97067_123.json")
        with open(test_file, "w") as f:
            json.dump({}, f)
        assert manager.is_file_fresh("reviews", test_file) is False

    def test_cache_disabled_returns_false(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {"pipeline_cache_enabled": False}
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        test_file = str(tmp_path / "output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)
        assert manager.is_file_fresh("reviews", test_file) is False


class TestIsStageFreshMtime:
    """Tests for mtime-based is_stage_fresh — no _completed flags."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager(metadata_path=metadata_path)

    def test_all_expected_files_present_and_fresh(self, cache_manager, tmp_path):
        """Stage is fresh when all expected outputs exist with recent mtime."""
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump([{"room_id": "111"}], f)

        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        assert cache_manager.is_stage_fresh("search", "97067") is True

    def test_some_expected_files_missing(self, cache_manager, tmp_path):
        """Stage is not fresh when some expected outputs are missing."""
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_results = [{"room_id": "111"}, {"room_id": "222"}]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        # Create only one of two expected review files
        reviews_dir = tmp_path / "outputs" / "03_reviews_scraped"
        reviews_dir.mkdir(parents=True)
        (reviews_dir / "reviews_97067_111.json").write_text("{}")
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "reviews": str(reviews_dir),
        }

        assert cache_manager.is_stage_fresh("reviews", "97067") is False

    def test_all_expected_files_stale(self, cache_manager, tmp_path):
        """Stage is not fresh when files exist but mtime is beyond TTL."""
        search_output = str(
            tmp_path / "outputs" / "01_search_results" / "search_results_97067.json"
        )
        os.makedirs(os.path.dirname(search_output), exist_ok=True)
        with open(search_output, "w") as f:
            json.dump([{"room_id": "111"}], f)
        old_time = time.time() - (10 * 24 * 3600)
        os.utime(search_output, (old_time, old_time))

        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(os.path.dirname(search_output)),
        }

        assert cache_manager.is_stage_fresh("search", "97067") is False

    def test_empty_expected_outputs_returns_false(self, cache_manager):
        """Stage with no expected outputs (e.g. missing search results) is not fresh."""
        assert cache_manager.is_stage_fresh("airdna", "99999") is False

    def test_force_refresh_overrides_freshness(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_search": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump([{"room_id": "111"}], f)
        manager.STAGE_OUTPUT_DIRS = {
            **manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        assert manager.is_stage_fresh("search", "97067") is False

    def test_cache_disabled_returns_false(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {"pipeline_cache_enabled": False}
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        assert manager.is_stage_fresh("search", "97067") is False


class TestGetMissingOutputs:
    """Tests for PipelineCacheManager.get_missing_outputs."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager(metadata_path=metadata_path)

    def test_all_present_returns_empty(self, cache_manager, tmp_path):
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump([{"room_id": "111"}], f)
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        missing = cache_manager.get_missing_outputs("search", "97067")
        assert missing == []

    def test_some_missing_returns_those(self, cache_manager, tmp_path):
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_results = [{"room_id": "111"}, {"room_id": "222"}]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)

        # Create one review file, leave one missing
        reviews_dir = tmp_path / "outputs" / "03_reviews_scraped"
        reviews_dir.mkdir(parents=True)
        (reviews_dir / "reviews_97067_111.json").write_text("{}")

        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
            "reviews": str(reviews_dir),
        }

        missing = cache_manager.get_missing_outputs("reviews", "97067")
        assert any("reviews_97067_222" in m for m in missing)
        assert not any("reviews_97067_111" in m for m in missing)

    def test_stale_files_included_in_missing(self, cache_manager, tmp_path):
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_output = str(search_dir / "search_results_97067.json")
        with open(search_output, "w") as f:
            json.dump([{"room_id": "111"}], f)
        old_time = time.time() - (10 * 24 * 3600)
        os.utime(search_output, (old_time, old_time))
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        missing = cache_manager.get_missing_outputs("search", "97067")
        assert len(missing) == 1
        assert "search_results_97067" in missing[0]

    def test_all_missing_returns_all(self, cache_manager, tmp_path):
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_results = [{"room_id": "111"}, {"room_id": "222"}]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        # Don't create any review files
        missing = cache_manager.get_missing_outputs("reviews", "97067")
        assert len(missing) == 2


class TestShouldRunStageMtime:
    """Tests for rewritten should_run_stage using mtime-based freshness."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager(metadata_path=metadata_path)

    def test_skip_when_all_fresh(self, cache_manager, tmp_path):
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump([{"room_id": "111"}], f)
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        assert cache_manager.should_run_stage("search", "97067") == "skip"

    def test_resume_when_incomplete(self, cache_manager):
        assert cache_manager.should_run_stage("reviews", "97067") == "resume"

    def test_clear_and_run_when_force_refresh(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_reviews": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        assert manager.should_run_stage("reviews", "97067") == "clear_and_run"

    def test_resume_when_cache_disabled(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {"pipeline_cache_enabled": False}
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        assert manager.should_run_stage("reviews", "97067") == "resume"


class TestClearStageForZipcodeMtime:
    """Tests for rewritten clear_stage_for_zipcode using expected_outputs."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager(metadata_path=metadata_path)

    def test_deletes_only_expected_zipcode_files(self, cache_manager, tmp_path):
        """Only files in expected_outputs for the zipcode are deleted."""
        reviews_dir = tmp_path / "outputs" / "03_reviews_scraped"
        reviews_dir.mkdir(parents=True)
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)

        search_results = [{"room_id": "111"}, {"room_id": "222"}]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)

        (reviews_dir / "reviews_97067_111.json").write_text("{}")
        (reviews_dir / "reviews_97067_222.json").write_text("{}")
        (reviews_dir / "reviews_90210_999.json").write_text("{}")

        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
            "reviews": str(reviews_dir),
        }

        cache_manager.clear_stage_for_zipcode("reviews", "97067")

        remaining = sorted(f.name for f in reviews_dir.iterdir())
        assert remaining == [
            "reviews_90210_999.json",
        ]

    def test_preserves_other_zipcode_files(self, cache_manager, tmp_path):
        """Files for other zipcodes are never touched."""
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump([{"room_id": "111"}], f)

        search_output_90210 = str(search_dir / "search_results_90210.json")
        with open(search_output_90210, "w") as f:
            json.dump([{"room_id": "999"}], f)

        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        cache_manager.clear_stage_for_zipcode("search", "97067")

        assert os.path.exists(search_output_90210)
        assert not os.path.exists(str(search_dir / "search_results_97067.json"))

    def test_handles_missing_directory(self, cache_manager, tmp_path):
        missing_dir = str(tmp_path / "outputs" / "nonexistent")
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "reviews": missing_dir,
        }
        # Should not raise
        cache_manager.clear_stage_for_zipcode("reviews", "97067")

    def test_details_stage_deletes_by_listing_id(self, cache_manager, tmp_path):
        """Details stage clears files by listing ID from search results."""
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_results = [{"room_id": "111"}, {"room_id": "222"}]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)

        details_dir = tmp_path / "outputs" / "04_details_scraped"
        details_dir.mkdir(parents=True)
        (details_dir / "property_details_111.json").write_text("{}")
        (details_dir / "property_details_222.json").write_text("{}")
        (details_dir / "property_details_999.json").write_text("{}")

        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
            "details": str(details_dir),
        }

        cache_manager.clear_stage_for_zipcode("details", "97067")

        remaining = sorted(f.name for f in details_dir.iterdir())
        assert remaining == ["property_details_999.json"]

    def test_preserves_directory_after_clearing(self, cache_manager, tmp_path):
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump([{"room_id": "111"}], f)

        reviews_dir = tmp_path / "outputs" / "03_reviews_scraped"
        reviews_dir.mkdir(parents=True)
        (reviews_dir / "reviews_97067_111.json").write_text("{}")

        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
            "reviews": str(reviews_dir),
        }

        cache_manager.clear_stage_for_zipcode("reviews", "97067")

        assert reviews_dir.exists()
        assert reviews_dir.is_dir()
