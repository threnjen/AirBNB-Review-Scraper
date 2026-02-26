"""
Unit tests for utils/pipeline_cache_manager.py
"""

import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from freezegun import freeze_time


class TestPipelineCacheManager:
    """Tests for PipelineCacheManager class."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a PipelineCacheManager with a temporary directory."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
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

            return PipelineCacheManager(metadata_path=metadata_path)

    @pytest.fixture
    def disabled_cache_manager(self, tmp_path):
        """Create a PipelineCacheManager with caching disabled."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": False,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            return PipelineCacheManager(metadata_path=metadata_path)

    def test_is_file_fresh_within_ttl(self, cache_manager, tmp_path):
        """Test that a file recorded within TTL is considered fresh."""
        test_file = str(tmp_path / "test_output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)

        cache_manager.record_output("reviews", test_file)

        assert cache_manager.is_file_fresh("reviews", test_file) is True

    def test_is_file_fresh_expired(self, cache_manager, tmp_path):
        """Test that a file recorded beyond TTL is considered stale."""
        test_file = str(tmp_path / "test_output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)

        old_time = (datetime.now() - timedelta(days=10)).isoformat()
        metadata = cache_manager._load_metadata()
        metadata.setdefault("reviews", {})[test_file] = old_time
        cache_manager._save_metadata(metadata)

        assert cache_manager.is_file_fresh("reviews", test_file) is False

    def test_is_file_fresh_missing(self, cache_manager, tmp_path):
        """Test that an unrecorded file returns False."""
        test_file = str(tmp_path / "nonexistent.json")

        assert cache_manager.is_file_fresh("reviews", test_file) is False

    def test_is_file_fresh_metadata_exists_but_file_deleted(
        self, cache_manager, tmp_path
    ):
        """Test that a recorded file that no longer exists on disk returns False."""
        test_file = str(tmp_path / "deleted_output.json")

        metadata = cache_manager._load_metadata()
        metadata.setdefault("reviews", {})[test_file] = datetime.now().isoformat()
        cache_manager._save_metadata(metadata)

        assert cache_manager.is_file_fresh("reviews", test_file) is False

    def test_is_stage_fresh_all_fresh(self, cache_manager, tmp_path):
        """Test that a stage with all fresh outputs is considered fresh."""
        files = []
        for i in range(3):
            test_file = str(tmp_path / f"output_{i}.json")
            with open(test_file, "w") as f:
                json.dump({}, f)
            files.append(test_file)
            cache_manager.record_output("reviews", test_file)

        cache_manager.record_stage_complete("reviews")

        assert cache_manager.is_stage_fresh("reviews") is True

    def test_is_stage_fresh_some_stale(self, cache_manager, tmp_path):
        """Test that a stage with any stale output returns False."""
        fresh_file = str(tmp_path / "fresh.json")
        with open(fresh_file, "w") as f:
            json.dump({}, f)
        cache_manager.record_output("reviews", fresh_file)

        stale_file = str(tmp_path / "stale.json")
        with open(stale_file, "w") as f:
            json.dump({}, f)
        old_time = (datetime.now() - timedelta(days=10)).isoformat()
        metadata = cache_manager._load_metadata()
        metadata.setdefault("reviews", {})[stale_file] = old_time
        cache_manager._save_metadata(metadata)

        cache_manager.record_stage_complete("reviews")

        assert cache_manager.is_stage_fresh("reviews") is False

    def test_is_stage_fresh_empty(self, cache_manager):
        """Test that a stage with no recorded outputs returns False."""
        assert cache_manager.is_stage_fresh("reviews") is False

    def test_record_output_writes_metadata(self, cache_manager, tmp_path):
        """Test that record_output writes correct metadata."""
        test_file = str(tmp_path / "output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)

        cache_manager.record_output("details", test_file)

        metadata = cache_manager._load_metadata()
        assert "details" in metadata
        assert test_file in metadata["details"]

        recorded_time = datetime.fromisoformat(metadata["details"][test_file])
        assert (datetime.now() - recorded_time).total_seconds() < 5

    def test_record_stage_complete(self, cache_manager, tmp_path):
        """Test that record_stage_complete marks completion timestamp."""
        test_file = str(tmp_path / "output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)
        cache_manager.record_output("airdna", test_file)

        cache_manager.record_stage_complete("airdna")

        metadata = cache_manager._load_metadata()
        assert "_completed" in metadata["airdna"]

        completed_time = datetime.fromisoformat(metadata["airdna"]["_completed"])
        assert (datetime.now() - completed_time).total_seconds() < 5

    def test_clear_stage_removes_only_target(self, cache_manager, tmp_path):
        """Test that clear_stage removes only the targeted stage."""
        for stage in ["reviews", "details"]:
            test_file = str(tmp_path / f"{stage}_output.json")
            with open(test_file, "w") as f:
                json.dump({}, f)
            cache_manager.record_output(stage, test_file)

        cache_manager.clear_stage("reviews")

        metadata = cache_manager._load_metadata()
        assert "reviews" not in metadata
        assert "details" in metadata

    def test_force_refresh_overrides_freshness(self, tmp_path):
        """Test that is_stage_fresh returns False when force flag is True."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_reviews": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        test_file = str(tmp_path / "output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)
        manager.record_output("reviews", test_file)
        manager.record_stage_complete("reviews")

        assert manager.is_stage_fresh("reviews") is False

    def test_cache_disabled_returns_false(self, disabled_cache_manager, tmp_path):
        """Test that disabled cache always reports stale."""
        test_file = str(tmp_path / "output.json")

        assert disabled_cache_manager.is_file_fresh("reviews", test_file) is False
        assert disabled_cache_manager.is_stage_fresh("reviews") is False

    def test_get_cache_stats(self, cache_manager, tmp_path):
        """Test that get_cache_stats returns correct counts."""
        fresh_file = str(tmp_path / "fresh.json")
        with open(fresh_file, "w") as f:
            json.dump({}, f)
        cache_manager.record_output("reviews", fresh_file)

        stale_file = str(tmp_path / "stale.json")
        with open(stale_file, "w") as f:
            json.dump({}, f)
        old_time = (datetime.now() - timedelta(days=10)).isoformat()
        metadata = cache_manager._load_metadata()
        metadata.setdefault("reviews", {})[stale_file] = old_time
        cache_manager._save_metadata(metadata)

        stats = cache_manager.get_cache_stats()

        assert stats["enabled"] is True
        assert stats["stages"]["reviews"]["fresh"] == 1
        assert stats["stages"]["reviews"]["stale"] == 1
        assert stats["stages"]["reviews"]["total"] == 2

    def test_get_cache_stats_disabled(self, disabled_cache_manager):
        """Test that get_cache_stats reports disabled."""
        stats = disabled_cache_manager.get_cache_stats()

        assert stats["enabled"] is False

    @freeze_time("2026-02-25 12:00:00")
    def test_metadata_persistence(self, tmp_path):
        """Test that metadata survives re-instantiation."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")

        test_file = str(tmp_path / "output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)

        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager1 = PipelineCacheManager(metadata_path=metadata_path)
            manager1.record_output("reviews", test_file)

        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager2 = PipelineCacheManager(metadata_path=metadata_path)

        assert manager2.is_file_fresh("reviews", test_file) is True

    def test_record_output_disabled(self, disabled_cache_manager, tmp_path):
        """Test that record_output is a no-op when disabled."""
        test_file = str(tmp_path / "output.json")

        result = disabled_cache_manager.record_output("reviews", test_file)

        assert result is False

    def test_multiple_stages_independent(self, cache_manager, tmp_path):
        """Test that stages track independently."""
        review_file = str(tmp_path / "review.json")
        detail_file = str(tmp_path / "detail.json")
        for f in [review_file, detail_file]:
            with open(f, "w") as fh:
                json.dump({}, fh)

        cache_manager.record_output("reviews", review_file)
        cache_manager.record_output("details", detail_file)
        cache_manager.record_stage_complete("reviews")
        cache_manager.record_stage_complete("details")

        assert cache_manager.is_stage_fresh("reviews") is True
        assert cache_manager.is_stage_fresh("details") is True

        cache_manager.clear_stage("reviews")

        assert cache_manager.is_stage_fresh("reviews") is False
        assert cache_manager.is_stage_fresh("details") is True

    def test_corrupted_metadata_returns_empty(self, cache_manager):
        """Test that corrupted metadata JSON is handled gracefully."""
        os.makedirs(os.path.dirname(cache_manager.metadata_path), exist_ok=True)
        with open(cache_manager.metadata_path, "w") as f:
            f.write("{invalid json!!!")

        metadata = cache_manager._load_metadata()
        assert metadata == {}

    def test_is_timestamp_fresh_invalid_string(self, cache_manager):
        """Test that invalid timestamp strings return False."""
        assert cache_manager._is_timestamp_fresh("not-a-date") is False
        assert cache_manager._is_timestamp_fresh("") is False
        assert cache_manager._is_timestamp_fresh(None) is False

    def test_save_metadata_permission_error(self, cache_manager, tmp_path):
        """Test that save failure logs warning and doesn't raise."""
        # Use a path under a read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        cache_manager.metadata_path = str(readonly_dir / "subdir" / "metadata.json")
        os.chmod(str(readonly_dir), 0o444)

        # Should not raise — logs a warning instead
        cache_manager._save_metadata({"test": {"file.json": "2026-01-01T00:00:00"}})

        # Restore permissions for cleanup
        os.chmod(str(readonly_dir), 0o755)

    def test_config_load_failure_uses_defaults(self, tmp_path):
        """Test that config load failure falls back to defaults with warning."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.side_effect = FileNotFoundError("config.json not found")
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        # Should fall back to defaults
        assert manager.enable_cache is True
        assert manager.ttl_hours == 24 * 7

    def test_is_file_fresh_with_corrupted_metadata(self, cache_manager, tmp_path):
        """Test is_file_fresh after metadata corruption returns False gracefully."""
        test_file = str(tmp_path / "output.json")
        with open(test_file, "w") as f:
            json.dump({}, f)

        # Write corrupted metadata
        os.makedirs(os.path.dirname(cache_manager.metadata_path), exist_ok=True)
        with open(cache_manager.metadata_path, "w") as f:
            f.write("<<<corrupted>>>")

        assert cache_manager.is_file_fresh("reviews", test_file) is False

    def test_force_refresh_search_bypasses_file_freshness(self, tmp_path):
        """Test that force_refresh flag causes is_file_fresh to return False."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_search": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        test_file = str(tmp_path / "search_results.json")
        with open(test_file, "w") as f:
            json.dump([{"room_id": "123"}], f)
        manager.record_output("search", test_file)
        manager.record_stage_complete("search")

        # Both file and stage freshness should be overridden by force_refresh
        assert manager.is_file_fresh("search", test_file) is False
        assert manager.force_refresh_flags.get("search", False) is True
        assert manager.is_stage_fresh("search") is False

    def test_force_refresh_reviews_bypasses_file_freshness(self, tmp_path):
        """Test that force_refresh_reviews causes per-file cache to be bypassed."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_reviews": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        test_file = str(tmp_path / "reviews_97067_12345.json")
        with open(test_file, "w") as f:
            json.dump({"12345": [{"review": "Great", "rating": 5}]}, f)
        manager.record_output("reviews", test_file)

        assert manager.is_file_fresh("reviews", test_file) is False

    def test_is_file_fresh_without_force_flag_still_works(
        self, cache_manager, tmp_path
    ):
        """Test that is_file_fresh returns True when force flag is False and file is cached."""
        test_file = str(tmp_path / "reviews_97067_99999.json")
        with open(test_file, "w") as f:
            json.dump({}, f)
        cache_manager.record_output("reviews", test_file)

        # cache_manager fixture has all force flags False
        assert cache_manager.is_file_fresh("reviews", test_file) is True

    def test_save_metadata_failure_propagates_to_record_output(self, tmp_path):
        """Test that record_output returns False when _save_metadata fails."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {"pipeline_cache_enabled": True}
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        test_file = str(tmp_path / "output.json")
        with patch.object(manager, "_save_metadata", return_value=False):
            result = manager.record_output("reviews", test_file)

        assert result is False

    def test_save_metadata_failure_propagates_to_record_stage_complete(self, tmp_path):
        """Test that record_stage_complete returns False when _save_metadata fails."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {"pipeline_cache_enabled": True}
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        with patch.object(manager, "_save_metadata", return_value=False):
            result = manager.record_stage_complete("reviews")

        assert result is False

    def test_get_cache_stats_excludes_deleted_files(self, cache_manager, tmp_path):
        """Test that get_cache_stats counts deleted files as stale, not fresh."""
        existing_file = str(tmp_path / "exists.json")
        with open(existing_file, "w") as f:
            json.dump({}, f)
        cache_manager.record_output("reviews", existing_file)

        deleted_file = str(tmp_path / "deleted.json")
        with open(deleted_file, "w") as f:
            json.dump({}, f)
        cache_manager.record_output("reviews", deleted_file)
        os.remove(deleted_file)

        stats = cache_manager.get_cache_stats()

        assert stats["stages"]["reviews"]["fresh"] == 1
        assert stats["stages"]["reviews"]["stale"] == 1
        assert stats["stages"]["reviews"]["total"] == 2

    def test_clear_stage_nonexistent_is_noop(self, cache_manager):
        """Test that clearing a nonexistent stage does not raise."""
        cache_manager.clear_stage("nonexistent_stage")

        metadata = cache_manager._load_metadata()
        assert "nonexistent_stage" not in metadata

    def test_clear_stage_wipes_output_directory(self, cache_manager, tmp_path):
        """Test that clear_stage wipes the output directory contents."""
        # Create a fake output directory with files
        output_dir = tmp_path / "outputs" / "03_reviews_scraped"
        output_dir.mkdir(parents=True)
        (output_dir / "reviews_97067_123.json").write_text("{}")
        (output_dir / "reviews_97067_456.json").write_text("{}")

        # Point stage output dirs to our tmp dir
        cache_manager.STAGE_OUTPUT_DIRS = {"reviews": str(output_dir)}
        cache_manager.clear_stage("reviews")

        # Directory still exists but is empty
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
        """Test that clear_stage doesn't raise when output dir doesn't exist."""
        missing_dir = str(tmp_path / "outputs" / "nonexistent")

        cache_manager.STAGE_OUTPUT_DIRS = {"reviews": missing_dir}
        # Should not raise
        cache_manager.clear_stage("reviews")

    def test_cascade_force_refresh_sets_all_later_stages(self, cache_manager):
        """Test that cascade_force_refresh sets all downstream stages to True."""
        cache_manager.cascade_force_refresh("reviews")

        # Upstream stages should be unchanged (False)
        assert cache_manager.force_refresh_flags.get("airdna") is False
        assert cache_manager.force_refresh_flags.get("search") is False

        # The triggering stage itself should NOT be changed
        assert cache_manager.force_refresh_flags.get("reviews") is False

        # All downstream stages should be True
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
        cache_manager.cascade_force_refresh("airdna")

        # airdna itself unchanged
        assert cache_manager.force_refresh_flags.get("airdna") is False

        # All others set to True
        for stage in [
            "search",
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
                f"Expected {stage} to be True after cascade from airdna"
            )

    def test_cascade_unknown_stage_is_noop(self, cache_manager):
        """Test that cascade with an unknown stage name does nothing."""
        original_flags = dict(cache_manager.force_refresh_flags)

        cache_manager.cascade_force_refresh("nonexistent_stage")

        assert cache_manager.force_refresh_flags == original_flags

    def test_new_force_refresh_flags_loaded_from_config(self, tmp_path):
        """Test that the 3 new force_refresh flags are loaded from config.

        With init-time cascade, setting extract_data=True auto-sets all
        downstream flags (analyze_correlations, analyze_descriptions) to True.
        """
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_extract_data": True,
                "force_refresh_analyze_correlations": False,
                "force_refresh_analyze_descriptions": False,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        assert manager.force_refresh_flags["extract_data"] is True
        # Cascade: both downstream flags auto-set to True
        assert manager.force_refresh_flags["analyze_correlations"] is True
        assert manager.force_refresh_flags["analyze_descriptions"] is True

    def test_init_cascade_sets_downstream_flags(self, tmp_path):
        """Test that on init, a True flag cascades to all later stages."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
                "force_refresh_reviews": True,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        # Upstream stages stay False
        assert manager.force_refresh_flags["airdna"] is False
        assert manager.force_refresh_flags["search"] is False

        # Triggering stage is True (from config)
        assert manager.force_refresh_flags["reviews"] is True

        # All downstream stages auto-set to True
        assert manager.force_refresh_flags["details"] is True
        assert manager.force_refresh_flags["build_details"] is True
        assert manager.force_refresh_flags["aggregate_reviews"] is True
        assert manager.force_refresh_flags["aggregate_summaries"] is True
        assert manager.force_refresh_flags["extract_data"] is True
        assert manager.force_refresh_flags["analyze_correlations"] is True
        assert manager.force_refresh_flags["analyze_descriptions"] is True

    def test_init_no_cascade_when_no_flags_set(self, tmp_path):
        """Test that no cascade occurs when all force_refresh flags are False."""
        metadata_path = str(tmp_path / "cache" / "pipeline_metadata.json")
        with patch("utils.pipeline_cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {
                "pipeline_cache_enabled": True,
                "pipeline_cache_ttl_days": 7,
            }
            from utils.pipeline_cache_manager import PipelineCacheManager

            manager = PipelineCacheManager(metadata_path=metadata_path)

        for stage in manager.STAGE_ORDER:
            assert manager.force_refresh_flags[stage] is False, (
                f"Expected {stage} to be False when no flags are set"
            )
