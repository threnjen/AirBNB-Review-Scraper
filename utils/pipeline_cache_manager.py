import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from utils.tiny_file_handler import load_json_file

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class PipelineCacheManager(BaseModel):
    """TTL-based cache manager for pipeline stage outputs.

    Tracks when each stage's output files were produced and skips
    re-execution if all outputs are still fresh within the configured TTL.
    """

    metadata_path: str = "cache/pipeline_metadata.json"
    ttl_hours: int = 24 * 7
    enable_cache: bool = True
    force_refresh_flags: dict[str, bool] = {}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        try:
            config = load_json_file("config.json")
            self.enable_cache = config.get("pipeline_cache_enabled", self.enable_cache)
            ttl_days = config.get("pipeline_cache_ttl_days", 7)
            self.ttl_hours = ttl_days * 24

            self.force_refresh_flags = {
                "airdna": config.get("force_refresh_airdna", False),
                "search": config.get("force_refresh_search", False),
                "reviews": config.get("force_refresh_reviews", False),
                "details": config.get("force_refresh_details", False),
                "build_details": config.get("force_refresh_build_details", False),
                "aggregate_reviews": config.get(
                    "force_refresh_aggregate_reviews", False
                ),
                "aggregate_summaries": config.get(
                    "force_refresh_aggregate_summaries", False
                ),
            }
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to load pipeline cache config, using defaults: {e}")

        if self.enable_cache:
            Path(self.metadata_path).parent.mkdir(parents=True, exist_ok=True)

    def _load_metadata(self) -> dict:
        """Load pipeline metadata from disk.

        Returns:
            dict: Stage-keyed metadata with file paths mapped to timestamps.
        """
        if not os.path.exists(self.metadata_path):
            return {}
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load pipeline metadata: {e}")
            return {}

    def _save_metadata(self, metadata: dict) -> bool:
        """Save pipeline metadata to disk atomically.

        Args:
            metadata: Stage-keyed metadata dict to persist.

        Returns:
            True if metadata was saved successfully, False otherwise.
        """
        try:
            Path(self.metadata_path).parent.mkdir(parents=True, exist_ok=True)
            dir_name = os.path.dirname(self.metadata_path)
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            os.replace(tmp_path, self.metadata_path)
            return True
        except OSError as e:
            logger.warning(f"Failed to save pipeline metadata: {e}")
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError as cleanup_err:
                    logger.warning(
                        f"Failed to clean up temp file {tmp_path}: {cleanup_err}"
                    )
            return False

    def _is_timestamp_fresh(self, timestamp_str: str) -> bool:
        """Check if a recorded timestamp is within the TTL window.

        Args:
            timestamp_str: ISO-format datetime string.

        Returns:
            True if the timestamp is within TTL, False otherwise.
        """
        try:
            recorded_time = datetime.fromisoformat(timestamp_str)
            expiry_time = recorded_time + timedelta(hours=self.ttl_hours)
            return datetime.now() < expiry_time
        except (ValueError, TypeError):
            return False

    def is_file_fresh(self, stage_name: str, file_path: str) -> bool:
        """Check if a single output file is fresh.

        A file is fresh if:
        1. Caching is enabled
        2. The stage's force_refresh flag is False
        3. The file is recorded in metadata with a timestamp within TTL
        4. The file still exists on disk

        Args:
            stage_name: Pipeline stage identifier (e.g. "reviews").
            file_path: Path to the output file.

        Returns:
            True if the file is fresh and can be skipped.
        """
        if not self.enable_cache:
            return False

        if self.force_refresh_flags.get(stage_name, False):
            return False

        metadata = self._load_metadata()
        stage_data = metadata.get(stage_name, {})
        timestamp = stage_data.get(file_path)

        if timestamp is None:
            return False

        if not os.path.exists(file_path):
            return False

        return self._is_timestamp_fresh(timestamp)

    def is_stage_fresh(self, stage_name: str) -> bool:
        """Check if an entire pipeline stage can be skipped.

        A stage is fresh if:
        1. Caching is enabled
        2. The stage's force_refresh flag is False
        3. The stage has a completion timestamp within TTL
        4. All recorded output files are still fresh

        Args:
            stage_name: Pipeline stage identifier (e.g. "airdna").

        Returns:
            True if the entire stage can be skipped.
        """
        if not self.enable_cache:
            return False

        if self.force_refresh_flags.get(stage_name, False):
            logger.info(f"Force refresh enabled for stage '{stage_name}'")
            return False

        metadata = self._load_metadata()
        stage_data = metadata.get(stage_name, {})

        if not stage_data:
            return False

        completed = stage_data.get("_completed")
        if not completed or not self._is_timestamp_fresh(completed):
            return False

        output_files = {k: v for k, v in stage_data.items() if k != "_completed"}

        if not output_files:
            return False

        for file_path, timestamp in output_files.items():
            if not os.path.exists(file_path):
                return False
            if not self._is_timestamp_fresh(timestamp):
                return False

        return True

    def record_output(self, stage_name: str, file_path: str) -> bool:
        """Record that an output file was produced.

        Args:
            stage_name: Pipeline stage identifier.
            file_path: Path to the output file that was produced.

        Returns:
            True if recorded successfully, False if caching is disabled or save failed.
        """
        if not self.enable_cache:
            return False

        metadata = self._load_metadata()
        metadata.setdefault(stage_name, {})[file_path] = datetime.now().isoformat()
        return self._save_metadata(metadata)

    def record_stage_complete(self, stage_name: str) -> bool:
        """Record that a pipeline stage completed successfully.

        Args:
            stage_name: Pipeline stage identifier.

        Returns:
            True if recorded successfully, False if caching is disabled or save failed.
        """
        if not self.enable_cache:
            return False

        metadata = self._load_metadata()
        metadata.setdefault(stage_name, {})["_completed"] = datetime.now().isoformat()
        saved = self._save_metadata(metadata)
        if saved:
            logger.info(f"Stage '{stage_name}' completed and cached")
        return saved

    def clear_stage(self, stage_name: str) -> None:
        """Remove all cached metadata for a stage.

        Args:
            stage_name: Pipeline stage identifier to clear.
        """
        metadata = self._load_metadata()
        if stage_name in metadata:
            del metadata[stage_name]
            self._save_metadata(metadata)
            logger.info(f"Cleared cache metadata for stage '{stage_name}'")

    def get_cache_stats(self) -> dict:
        """Get statistics about cached pipeline outputs.

        Returns:
            dict with 'enabled', 'ttl_hours', and per-stage counts
            of fresh/stale/total files.
        """
        if not self.enable_cache:
            return {"enabled": False}

        metadata = self._load_metadata()
        stats: dict[str, Any] = {
            "enabled": True,
            "ttl_hours": self.ttl_hours,
            "stages": {},
        }

        for stage_name, stage_data in metadata.items():
            output_files = {k: v for k, v in stage_data.items() if k != "_completed"}
            fresh_count = sum(
                1
                for fp, ts in output_files.items()
                if self._is_timestamp_fresh(ts) and os.path.exists(fp)
            )
            stale_count = len(output_files) - fresh_count

            stats["stages"][stage_name] = {
                "fresh": fresh_count,
                "stale": stale_count,
                "total": len(output_files),
            }

        return stats
