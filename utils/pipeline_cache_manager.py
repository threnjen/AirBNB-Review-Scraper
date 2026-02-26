import glob
import json
import logging
import os
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from utils.local_file_handler import LocalFileHandler
from utils.tiny_file_handler import load_json_file

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class PipelineCacheManager(BaseModel):
    """Filesystem-driven cache manager for pipeline stage outputs.

    Freshness is determined entirely by ``os.path.getmtime`` — no metadata
    file and no ``_completed`` flags.  Each stage declares its expected
    output files via :meth:`expected_outputs`; a stage is fresh when every
    expected file exists on disk with an mtime within the configured TTL.
    """

    STAGE_ORDER: list[str] = [
        "search",
        "airdna",
        "reviews",
        "details",
        "aggregate_reviews",
        "aggregate_summaries",
        "build_details",
        "extract_data",
        "analyze_correlations",
        "analyze_descriptions",
    ]

    STAGE_OUTPUT_DIRS: dict[str, str] = {
        "search": "outputs/01_search_results",
        "airdna": "outputs/02_comp_sets",
        "reviews": "outputs/03_reviews_scraped",
        "details": "outputs/04_details_scraped",
        "build_details": "outputs/05_details_results",
        "aggregate_reviews": "outputs/06_generated_summaries",
        "aggregate_summaries": "reports",
        "extract_data": "outputs/07_extracted_data",
        "analyze_correlations": "outputs/08_correlation_results",
        "analyze_descriptions": "outputs/09_description_analysis",
    }

    metadata_path: str = "cache/pipeline_metadata.json"
    ttl_hours: int = 24 * 7
    enable_cache: bool = True
    force_refresh_flags: dict[str, bool] = {}
    correlation_metrics: list[str] = ["adr", "occupancy"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        try:
            config = load_json_file("config.json")
            self.enable_cache = config.get("pipeline_cache_enabled", self.enable_cache)
            ttl_days = config.get("pipeline_cache_ttl_days", 7)
            self.ttl_hours = ttl_days * 24
            self.correlation_metrics = config.get(
                "correlation_metrics", self.correlation_metrics
            )

            self.force_refresh_flags = {
                "airdna": config.get("force_refresh_scrape_airdna", False),
                "search": config.get("force_refresh_search", False),
                "reviews": config.get("force_refresh_reviews", False),
                "details": config.get("force_refresh_scrape_details", False),
                "build_details": config.get("force_refresh_build_details", False),
                "aggregate_reviews": config.get(
                    "force_refresh_aggregate_reviews", False
                ),
                "aggregate_summaries": config.get(
                    "force_refresh_aggregate_summaries", False
                ),
                "extract_data": config.get("force_refresh_extract_data", False),
                "analyze_correlations": config.get(
                    "force_refresh_analyze_correlations", False
                ),
                "analyze_descriptions": config.get(
                    "force_refresh_analyze_descriptions", False
                ),
            }
            self._apply_init_cascade()
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to load pipeline cache config, using defaults: {e}")

    # ------------------------------------------------------------------
    # Expected-output enumeration
    # ------------------------------------------------------------------

    def expected_outputs(self, stage_name: str, zipcode: str) -> list[str]:
        """Return the list of file paths a stage should produce for *zipcode*.

        Fixed-count stages derive paths from *zipcode* alone.  Listing-dynamic
        stages (``airdna``, ``reviews``, ``details``, ``aggregate_reviews``)
        read the search-results file to enumerate listing IDs.

        Args:
            stage_name: Pipeline stage identifier.
            zipcode: Active zipcode.

        Returns:
            List of expected output file paths.  Empty if the stage is unknown
            or prerequisite data (e.g. search results) is missing.
        """
        if stage_name == "search":
            search_dir = self.STAGE_OUTPUT_DIRS.get(
                "search", "outputs/01_search_results"
            )
            return [os.path.join(search_dir, f"search_results_{zipcode}.json")]

        if stage_name == "airdna":
            listing_ids = self._get_listing_ids_for_zipcode(zipcode)
            if not listing_ids:
                return []
            airdna_dir = self.STAGE_OUTPUT_DIRS.get("airdna", "outputs/02_comp_sets")
            files = [
                os.path.join(airdna_dir, f"listing_{lid}.json") for lid in listing_ids
            ]
            files.append(os.path.join(airdna_dir, f"comp_set_{zipcode}.json"))
            return files

        if stage_name == "reviews":
            listing_ids = self._get_listing_ids_for_zipcode(zipcode)
            if not listing_ids:
                return []
            reviews_dir = self.STAGE_OUTPUT_DIRS.get(
                "reviews", "outputs/03_reviews_scraped"
            )
            return [
                os.path.join(reviews_dir, f"reviews_{zipcode}_{lid}.json")
                for lid in listing_ids
            ]

        if stage_name == "details":
            listing_ids = self._get_listing_ids_for_zipcode(zipcode)
            if not listing_ids:
                return []
            details_dir = self.STAGE_OUTPUT_DIRS.get(
                "details", "outputs/04_details_scraped"
            )
            return [
                os.path.join(details_dir, f"property_details_{lid}.json")
                for lid in listing_ids
            ]

        if stage_name == "aggregate_reviews":
            listing_ids = self._get_review_listing_ids_for_zipcode(zipcode)
            if not listing_ids:
                return []
            summaries_dir = self.STAGE_OUTPUT_DIRS.get(
                "aggregate_reviews", "outputs/06_generated_summaries"
            )
            return [
                os.path.join(summaries_dir, f"generated_summaries_{zipcode}_{lid}.json")
                for lid in listing_ids
            ]

        if stage_name == "build_details":
            bd_dir = self.STAGE_OUTPUT_DIRS.get(
                "build_details", "outputs/05_details_results"
            )
            return [
                os.path.join(bd_dir, f"property_amenities_matrix_{zipcode}.csv"),
                os.path.join(
                    bd_dir, f"property_amenities_matrix_cleaned_{zipcode}.csv"
                ),
                os.path.join(bd_dir, f"house_rules_details_{zipcode}.json"),
                os.path.join(bd_dir, f"property_descriptions_{zipcode}.json"),
                os.path.join(bd_dir, f"neighborhood_highlights_{zipcode}.json"),
            ]

        if stage_name == "aggregate_summaries":
            return [
                f"reports/area_summary_{zipcode}.json",
                f"reports/area_summary_{zipcode}.md",
            ]

        if stage_name == "extract_data":
            ed_dir = self.STAGE_OUTPUT_DIRS.get(
                "extract_data", "outputs/07_extracted_data"
            )
            return [os.path.join(ed_dir, f"area_data_{zipcode}.json")]

        if stage_name == "analyze_correlations":
            ac_dir = self.STAGE_OUTPUT_DIRS.get(
                "analyze_correlations", "outputs/08_correlation_results"
            )
            files: list[str] = []
            for metric in self.correlation_metrics:
                files.append(
                    os.path.join(ac_dir, f"correlation_stats_{metric}_{zipcode}.json")
                )
                files.append(f"reports/correlation_insights_{metric}_{zipcode}.md")
            return files

        if stage_name == "analyze_descriptions":
            ad_dir = self.STAGE_OUTPUT_DIRS.get(
                "analyze_descriptions", "outputs/09_description_analysis"
            )
            return [
                os.path.join(ad_dir, f"description_quality_stats_{zipcode}.json"),
                f"reports/description_quality_{zipcode}.md",
            ]

        return []

    # ------------------------------------------------------------------
    # Filesystem-based freshness checks
    # ------------------------------------------------------------------

    def _is_file_fresh_by_mtime(self, file_path: str) -> bool:
        """Check if a file exists and its mtime is within the TTL window.

        Args:
            file_path: Path to the file.

        Returns:
            True if the file exists and was modified within TTL.
        """
        if not os.path.exists(file_path):
            return False
        mtime = os.path.getmtime(file_path)
        age_hours = (time.time() - mtime) / 3600
        return age_hours < self.ttl_hours

    def is_file_fresh(self, stage_name: str, file_path: str) -> bool:
        """Check if a single output file is fresh.

        A file is fresh if:
        1. Caching is enabled
        2. The stage's force_refresh flag is False
        3. The file exists on disk with mtime within TTL

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

        return self._is_file_fresh_by_mtime(file_path)

    def is_stage_fresh(self, stage_name: str, zipcode: str | None = None) -> bool:
        """Check if an entire pipeline stage can be skipped.

        A stage is fresh if:
        1. Caching is enabled
        2. The stage's force_refresh flag is False
        3. All expected output files exist on disk with mtime within TTL

        Args:
            stage_name: Pipeline stage identifier (e.g. "airdna").
            zipcode: Zipcode to scope the freshness check.

        Returns:
            True if the entire stage can be skipped.
        """
        if not self.enable_cache:
            return False

        if self.force_refresh_flags.get(stage_name, False):
            logger.info(f"Force refresh enabled for stage '{stage_name}'")
            return False

        if zipcode is None:
            return False

        expected = self.expected_outputs(stage_name, zipcode)
        if not expected:
            return False

        for file_path in expected:
            if not self._is_file_fresh_by_mtime(file_path):
                return False

        return True

    def get_missing_outputs(self, stage_name: str, zipcode: str) -> list[str]:
        """Return expected output files that are missing or stale.

        Args:
            stage_name: Pipeline stage identifier.
            zipcode: Active zipcode.

        Returns:
            List of file paths that need to be (re)generated.
        """
        expected = self.expected_outputs(stage_name, zipcode)
        return [f for f in expected if not self._is_file_fresh_by_mtime(f)]

    # ------------------------------------------------------------------
    # Legacy compatibility stubs
    # ------------------------------------------------------------------

    def record_output(self, stage_name: str, file_path: str) -> bool:
        """No-op retained for backward compatibility.

        With mtime-based caching, output tracking is automatic via the
        filesystem.  This method does nothing and always returns True.

        Args:
            stage_name: Pipeline stage identifier.
            file_path: Path to the output file that was produced.

        Returns:
            True always.
        """
        return True

    def record_stage_complete(
        self, stage_name: str, zipcode: str | None = None
    ) -> bool:
        """No-op retained for backward compatibility.

        With mtime-based caching, stage completion is determined by checking
        expected output files on disk.  This method does nothing.

        Args:
            stage_name: Pipeline stage identifier.
            zipcode: Optional zipcode (unused).

        Returns:
            True always.
        """
        return True

    # ------------------------------------------------------------------
    # Clearing
    # ------------------------------------------------------------------

    def clear_stage(self, stage_name: str) -> None:
        """Remove all files in a stage's output directory.

        .. deprecated::
            Use :meth:`clear_stage_for_zipcode` for zipcode-scoped clearing.

        Args:
            stage_name: Pipeline stage identifier to clear.
        """
        output_dir = self.STAGE_OUTPUT_DIRS.get(stage_name)
        if output_dir:
            LocalFileHandler().clear_directory(output_dir)
            logger.info(
                f"Wiped output directory '{output_dir}' for stage '{stage_name}'"
            )

    def clear_stage_for_zipcode(self, stage_name: str, zipcode: str) -> None:
        """Remove only the expected output files for *zipcode* within a stage.

        Uses :meth:`expected_outputs` to determine exactly which files belong
        to the zipcode, then deletes only those.  Files for other zipcodes are
        never touched.

        Args:
            stage_name: Pipeline stage identifier to clear.
            zipcode: Zipcode whose outputs should be removed.
        """
        expected = self.expected_outputs(stage_name, zipcode)
        removed = 0
        for file_path in expected:
            if os.path.exists(file_path):
                os.remove(file_path)
                removed += 1
        if removed:
            logger.info(
                f"Cleared {removed} files for zipcode {zipcode} in stage '{stage_name}'"
            )

    # ------------------------------------------------------------------
    # Listing-ID helpers
    # ------------------------------------------------------------------

    def _get_listing_ids_for_zipcode(self, zipcode: str) -> list[str]:
        """Derive listing IDs from the search results file for a zipcode.

        Args:
            zipcode: Zipcode whose search results are read.

        Returns:
            List of listing ID strings.  Empty list if the file is missing.
        """
        search_dir = self.STAGE_OUTPUT_DIRS.get("search", "outputs/01_search_results")
        search_path = os.path.join(search_dir, f"search_results_{zipcode}.json")
        if not os.path.isfile(search_path):
            logger.warning(
                f"Search results file not found at {search_path} — "
                "cannot derive listing IDs."
            )
            return []
        try:
            with open(search_path, "r", encoding="utf-8") as f:
                results = json.load(f)
            return [
                str(r.get("room_id", r.get("id", "")))
                for r in results
                if r.get("room_id") or r.get("id")
            ]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read search results for {zipcode}: {e}")
            return []

    def _get_review_listing_ids_for_zipcode(self, zipcode: str) -> list[str]:
        """Derive listing IDs from review files on disk for a zipcode.

        Scans the reviews output directory for files matching
        ``reviews_{zipcode}_*.json`` and extracts listing IDs from filenames.

        Args:
            zipcode: Zipcode to scope by.

        Returns:
            List of listing ID strings.  Empty if no review files found.
        """
        reviews_dir = self.STAGE_OUTPUT_DIRS.get(
            "reviews", "outputs/03_reviews_scraped"
        )
        pattern = os.path.join(reviews_dir, f"reviews_{zipcode}_*.json")
        listing_ids = []
        for filepath in glob.glob(pattern):
            filename = os.path.basename(filepath)
            # reviews_{zipcode}_{listing_id}.json
            parts = filename.replace(".json", "").split("_", 2)
            if len(parts) >= 3:
                listing_ids.append(parts[2])
        return listing_ids

    # ------------------------------------------------------------------
    # Stage decision
    # ------------------------------------------------------------------

    def should_run_stage(self, stage_name: str, zipcode: str) -> str:
        """Determine what action a stage should take.

        Returns one of:
        - ``"skip"``: Stage is fresh, no work needed.
        - ``"resume"``: Stage is incomplete but no force-refresh — resume
          without wiping existing outputs.
        - ``"clear_and_run"``: Force-refresh is active — wipe outputs for
          this zipcode, then run from scratch.

        Args:
            stage_name: Pipeline stage identifier.
            zipcode: Active zipcode.

        Returns:
            Action string: ``"skip"``, ``"resume"``, or ``"clear_and_run"``.
        """
        if self.force_refresh_flags.get(stage_name, False):
            return "clear_and_run"

        if self.is_stage_fresh(stage_name, zipcode):
            return "skip"

        return "resume"

    # ------------------------------------------------------------------
    # Cascade logic
    # ------------------------------------------------------------------

    def _apply_init_cascade(self) -> None:
        """Cascade force-refresh flags at init time.

        If any ``force_refresh_*`` flag loaded from config is ``True``, every
        stage that comes *after* it in :pyattr:`STAGE_ORDER` is also set to
        ``True``.  This guarantees that refreshing an upstream stage always
        invalidates all downstream outputs.
        """
        cascade_active = False
        cascaded: list[str] = []
        for stage in self.STAGE_ORDER:
            if cascade_active:
                if not self.force_refresh_flags.get(stage, False):
                    cascaded.append(stage)
                self.force_refresh_flags[stage] = True
            elif self.force_refresh_flags.get(stage, False):
                cascade_active = True

        if cascaded:
            logger.info(
                "Init cascade: auto-set force_refresh for downstream stages: "
                f"{', '.join(cascaded)}"
            )

    def cascade_force_refresh(self, stage_name: str) -> None:
        """Force-refresh all stages that come after *stage_name* in the pipeline.

        This ensures downstream outputs built from the refreshed stage's data
        are also regenerated.

        Args:
            stage_name: The stage whose refresh should cascade downstream.
        """
        if stage_name not in self.STAGE_ORDER:
            logger.warning(f"Unknown stage '{stage_name}' — cascade skipped.")
            return

        stage_index = self.STAGE_ORDER.index(stage_name)
        downstream = self.STAGE_ORDER[stage_index + 1 :]

        if downstream:
            for later_stage in downstream:
                self.force_refresh_flags[later_stage] = True
            logger.info(
                f"Stage '{stage_name}' refreshed — cascading force_refresh to: "
                f"{', '.join(downstream)}"
            )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_cache_stats(self) -> dict:
        """Get statistics about cached pipeline outputs.

        Returns:
            dict with 'enabled', 'ttl_hours', and per-stage counts
            of fresh/stale/total expected files.
        """
        if not self.enable_cache:
            return {"enabled": False}

        stats: dict[str, Any] = {
            "enabled": True,
            "ttl_hours": self.ttl_hours,
            "stages": {},
        }

        return stats
