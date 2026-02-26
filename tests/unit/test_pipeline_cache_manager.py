"""
Unit tests for utils/pipeline_cache_manager.py

Tests here cover behaviors NOT already in test_pipeline_cache_mtime.py:
  - cascade_force_refresh / init cascade
  - config loading / fallback
  - force_refresh flag overrides on is_file_fresh
  - clear_stage (full-directory wipe)
  - clear_stage_for_zipcode with listing-ID derivation
  - _get_listing_ids_for_zipcode
  - cache-disabled behaviour
"""

import json
import os
from unittest.mock import patch

import pytest


class TestPipelineCacheManager:
    """Tests for PipelineCacheManager class."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a PipelineCacheManager with a temporary directory."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_scrape_airdna": False,
                "force_refresh_search": False,
                "force_refresh_reviews": False,
                "force_refresh_scrape_details": False,
                "force_refresh_build_details": False,
                "force_refresh_aggregate_reviews": False,
                "force_refresh_aggregate_summaries": False,
                "force_refresh_extract_data": False,
                "force_refresh_analyze_correlations": False,
                "force_refresh_analyze_descriptions": False,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager()

    @pytest.fixture
    def disabled_cache_manager(self, tmp_path):
        """Create a PipelineCacheManager with caching disabled."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": False,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager()

    # --- is_file_fresh (mtime-based) ---

    def test_is_file_fresh_within_ttl(self, cache_manager, tmp_path):
        """Test that a recently-created file is considered fresh by mtime."""
        test_file = str(tmp_path / "test_output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)

        assert cache_manager.is_file_fresh("reviews", test_file) is True

    def test_is_file_fresh_missing(self, cache_manager, tmp_path):
        """Test that a nonexistent file returns False."""
        test_file = str(tmp_path / "nonexistent.json")

        assert cache_manager.is_file_fresh("reviews", test_file) is False

    # --- force_refresh overrides ---

    def test_force_refresh_overrides_file_freshness(self, tmp_path):
        """Test that is_file_fresh returns False when force flag is True."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_reviews": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager()

        test_file = str(tmp_path / "output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)

        assert manager.is_file_fresh("reviews", test_file) is False

    def test_force_refresh_search_bypasses_file_freshness(self, tmp_path):
        """Test that force_refresh flag makes both file and stage freshness False."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_search": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager()

        test_file = str(tmp_path / "search_results.json")
        with open(test_file, "w") as f:
            json.dump([{"room_id": "123"}], f)

        assert manager.is_file_fresh("search", test_file) is False
        assert manager.force_refresh_flags.get("search", False) is True

    def test_is_file_fresh_without_force_flag_still_works(
        self, cache_manager, tmp_path
    ):
        """Test that is_file_fresh returns True when force flag is False and file exists."""
        test_file = str(tmp_path / "reviews_97067_99999.json")
        with open(test_file, "w") as f:
            json.dump({}, f)

        assert cache_manager.is_file_fresh("reviews", test_file) is True

    # --- cache disabled ---

    def test_cache_disabled_returns_false(self, disabled_cache_manager, tmp_path):
        """Test that disabled cache always reports stale."""
        test_file = str(tmp_path / "output.json")

        assert disabled_cache_manager.is_file_fresh("reviews", test_file) is False
        assert disabled_cache_manager.is_stage_fresh("reviews") is False

    def test_get_cache_stats_disabled(self, disabled_cache_manager):
        """Test that get_cache_stats reports disabled."""
        stats = disabled_cache_manager.get_cache_stats()

        assert stats["enabled"] is False

    # --- config loading ---

    def test_config_load_failure_uses_defaults(self, tmp_path):
        """Test that config load failure falls back to defaults with warning."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.side_effect = FileNotFoundError("config.json not found")
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager()

        assert manager.enable_cache is True
        assert manager.ttl_hours == 24 * 7

    # --- clear_stage (full directory wipe) ---

    def test_clear_stage_wipes_output_directory(self, cache_manager, tmp_path):
        """Test that clear_stage wipes the output directory contents."""
        output_dir = tmp_path / "outputs" / "03_reviews_scraped"
        output_dir.mkdir(parents=True)
        (output_dir / "reviews_97067_123.json").write_text("{}")
        (output_dir / "reviews_97067_456.json").write_text("{}")

        cache_manager.STAGE_OUTPUT_DIRS = {"reviews": str(output_dir)}
        cache_manager.clear_stage("reviews")

        assert output_dir.exists()
        assert list(output_dir.iterdir()) == []

    def test_clear_stage_preserves_directory_itself(self, cache_manager, tmp_path):
        """Test that clear_stage keeps the directory after wiping contents."""
        output_dir = tmp_path / "outputs" / "05_details_results"
        output_dir.mkdir(parents=True)
        (output_dir / "data.csv").write_text("a,b")

        cache_manager.STAGE_OUTPUT_DIRS = {"build_details": str(output_dir)}
        cache_manager.clear_stage("build_details")

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_clear_stage_handles_missing_directory(self, cache_manager, tmp_path):
        """Test that clear_stage does not raise when output dir does not exist."""
        missing_dir = str(tmp_path / "outputs" / "nonexistent")

        cache_manager.STAGE_OUTPUT_DIRS = {"reviews": missing_dir}
        cache_manager.clear_stage("reviews")

    # --- cascade_force_refresh ---

    def test_cascade_force_refresh_sets_all_later_stages(self, cache_manager):
        """Test that cascade_force_refresh sets all downstream stages to True."""
        cache_manager.cascade_force_refresh("reviews")

        assert cache_manager.force_refresh_flags.get("airdna") is False
        assert cache_manager.force_refresh_flags.get("search") is False
        assert cache_manager.force_refresh_flags.get("reviews") is False

        assert cache_manager.force_refresh_flags.get("details") is True
        assert cache_manager.force_refresh_flags.get("build_details") is True
        assert cache_manager.force_refresh_flags.get("aggregate_reviews") is True
        assert cache_manager.force_refresh_flags.get("aggregate_summaries") is True
        assert cache_manager.force_refresh_flags.get("extract_data") is True
        assert cache_manager.force_refresh_flags.get("analyze_correlations") is True
        assert cache_manager.force_refresh_flags.get("analyze_descriptions") is True

    def test_cascade_from_last_stage_is_noop(self, cache_manager):
        """Test that cascade from the last stage changes nothing."""
        original_flags = dict(cache_manager.force_refresh_flags)

        cache_manager.cascade_force_refresh("analyze_descriptions")

        assert cache_manager.force_refresh_flags == original_flags

    def test_cascade_from_first_stage_sets_all_others(self, cache_manager):
        """Test that cascade from the first stage sets all 9 remaining stages."""
        cache_manager.cascade_force_refresh("search")

        assert cache_manager.force_refresh_flags.get("search") is False

        for stage in [
            "airdna",
            "reviews",
            "details",
            "build_details",
            "aggregate_reviews",
            "aggregate_summaries",
            "extract_data",
            "analyze_correlations",
            "analyze_descriptions",
        ]:
            assert cache_manager.force_refresh_flags.get(stage) is True, (
                f"Expected {stage} to be True after cascade from search"
            )

    def test_cascade_unknown_stage_is_noop(self, cache_manager):
        """Test that cascade with an unknown stage name does nothing."""
        original_flags = dict(cache_manager.force_refresh_flags)

        cache_manager.cascade_force_refresh("nonexistent_stage")

        assert cache_manager.force_refresh_flags == original_flags

    # --- init cascade ---

    def test_new_force_refresh_flags_loaded_from_config(self, tmp_path):
        """Test that force_refresh flags are loaded from config with init cascade."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_extract_data": True,
                "force_refresh_analyze_correlations": False,
                "force_refresh_analyze_descriptions": False,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager()

        assert manager.force_refresh_flags["extract_data"] is True
        assert manager.force_refresh_flags["analyze_correlations"] is True
        assert manager.force_refresh_flags["analyze_descriptions"] is True

    def test_init_cascade_sets_downstream_flags(self, tmp_path):
        """Test that on init, a True flag cascades to all later stages."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_reviews": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager()

        assert manager.force_refresh_flags["airdna"] is False
        assert manager.force_refresh_flags["search"] is False
        assert manager.force_refresh_flags["reviews"] is True

        assert manager.force_refresh_flags["details"] is True
        assert manager.force_refresh_flags["build_details"] is True
        assert manager.force_refresh_flags["aggregate_reviews"] is True
        assert manager.force_refresh_flags["aggregate_summaries"] is True
        assert manager.force_refresh_flags["extract_data"] is True
        assert manager.force_refresh_flags["analyze_correlations"] is True
        assert manager.force_refresh_flags["analyze_descriptions"] is True

    def test_init_no_cascade_when_no_flags_set(self, tmp_path):
        """Test that no cascade occurs when all force_refresh flags are False."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager()

        for stage in manager.STAGE_ORDER:
            assert manager.force_refresh_flags[stage] is False, (
                f"Expected {stage} to be False when no flags are set"
            )


class TestZipcodeScopedCache:
    """Tests for zipcode-scoped cache clearing and related helpers."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a PipelineCacheManager with a temporary directory."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_scrape_airdna": False,
                "force_refresh_search": False,
                "force_refresh_reviews": False,
                "force_refresh_scrape_details": False,
                "force_refresh_build_details": False,
                "force_refresh_aggregate_reviews": False,
                "force_refresh_aggregate_summaries": False,
                "force_refresh_extract_data": False,
                "force_refresh_analyze_correlations": False,
                "force_refresh_analyze_descriptions": False,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager()

    # --- should_run_stage ---

    def test_should_run_stage_resume_when_no_outputs(self, cache_manager):
        """Test that should_run_stage returns 'resume' for a never-run stage."""
        assert cache_manager.should_run_stage("reviews", "97067") == "resume"

    def test_should_run_stage_clear_when_force_refresh(self, tmp_path):
        """Test that should_run_stage returns 'clear_and_run' when force flag is set."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_reviews": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager()

        assert manager.should_run_stage("reviews", "97067") == "clear_and_run"

    def test_should_run_stage_resume_when_cache_disabled(self, tmp_path):
        """Test that disabled cache always returns 'resume'."""
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {"pipeline_cache_enabled": False}
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager()

        assert manager.should_run_stage("reviews", "97067") == "resume"

    # --- clear_stage_for_zipcode ---

    def test_clear_stage_for_zipcode_handles_missing_directory(
        self, cache_manager, tmp_path
    ):
        """Test that clearing with a missing output directory does not raise."""
        missing_dir = str(tmp_path / "outputs" / "nonexistent")
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "reviews": missing_dir,
        }
        cache_manager.clear_stage_for_zipcode("reviews", "97067")

    def test_clear_stage_for_zipcode_details_uses_listing_ids(
        self, cache_manager, tmp_path
    ):
        """Test that details stage clears files by listing ID from search results."""
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_results = [
            {"room_id": "111"},
            {"room_id": "222"},
        ]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)

        details_dir = tmp_path / "outputs" / "04_details_scraped"
        details_dir.mkdir(parents=True)
        (details_dir / "property_details_111.json").write_text("{}")
        (details_dir / "property_details_222.json").write_text("{}")
        (details_dir / "property_details_999.json").write_text("{}")

        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "details": str(details_dir),
            "search": str(search_dir),
        }

        cache_manager.clear_stage_for_zipcode("details", "97067")

        remaining = sorted(f.name for f in details_dir.iterdir())
        assert remaining == ["property_details_999.json"]

    # --- _get_listing_ids_for_zipcode ---

    def test_get_listing_ids_for_zipcode_reads_search_results(
        self, cache_manager, tmp_path
    ):
        """Test that listing IDs are correctly extracted from search results."""
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        search_results = [
            {"room_id": "111", "name": "Cabin A"},
            {"room_id": "222", "name": "Cabin B"},
            {"id": "333", "name": "Cabin C"},
        ]
        with open(str(search_dir / "search_results_97067.json"), "w") as f:
            json.dump(search_results, f)

        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        ids = cache_manager._get_listing_ids_for_zipcode("97067")
        assert sorted(ids) == ["111", "222", "333"]

    def test_get_listing_ids_for_zipcode_missing_file_returns_empty(
        self, cache_manager, tmp_path
    ):
        """Test that missing search results file returns empty list."""
        search_dir = tmp_path / "outputs" / "01_search_results"
        search_dir.mkdir(parents=True)
        cache_manager.STAGE_OUTPUT_DIRS = {
            **cache_manager.STAGE_OUTPUT_DIRS,
            "search": str(search_dir),
        }

        ids = cache_manager._get_listing_ids_for_zipcode("99999")
        assert ids == []

    # --- clear_stage backward compat ---

    def test_clear_stage_still_wipes_full_directory(self, cache_manager, tmp_path):
        """Test that the deprecated clear_stage still does a full wipe."""
        output_dir = tmp_path / "outputs" / "03_reviews_scraped"
        output_dir.mkdir(parents=True)
        (output_dir / "reviews_97067_123.json").write_text("{}")
        (output_dir / "reviews_90210_456.json").write_text("{}")

        cache_manager.STAGE_OUTPUT_DIRS = {"reviews": str(output_dir)}
        cache_manager.clear_stage("reviews")

        assert output_dir.exists()
        assert list(output_dir.iterdir()) == []
