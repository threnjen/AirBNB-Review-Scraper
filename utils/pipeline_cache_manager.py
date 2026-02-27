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
        "search_results",
        "details_scrape",
        "comp_sets",
        "reviews_scrape",
        "details_results",
        "listing_summaries",
        "area_summary",
        "correlation_results",
        "description_analysis",
    ]

    CASCADE_TARGET_STAGES: set[str] = {
        "area_summary",
        "correlation_results",
        "description_analysis",
    }

    STAGE_OUTPUT_DIRS: dict[str, str] = {
        "search_results": "outputs/01_search_results",
        "details_scrape": "outputs/02_details_scrape",
        "comp_sets": "outputs/03_comp_sets",
        "reviews_scrape": "outputs/04_reviews_scrape",
        "details_results": "outputs/05_details_results",
        "listing_summaries": "outputs/06_listing_summaries",
        "correlation_results": "outputs/08_correlation_results",
        "description_analysis": "outputs/09_description_analysis",
    }

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
                "search_results": config.get("force_refresh_search_results", False),
                "details_scrape": config.get("force_refresh_details_scrape", False),
                "details_results": config.get("force_refresh_details_results", False),
                "reviews_scrape": config.get("force_refresh_reviews_scrape", False),
                "comp_sets": config.get("force_refresh_comp_sets", False),
                "listing_summaries": config.get(
                    "force_refresh_listing_summaries", False
                ),
                "area_summary": config.get("force_refresh_area_summary", False),
                "correlation_results": config.get(
                    "force_refresh_correlation_results", False
                ),
                "description_analysis": config.get(
                    "force_refresh_description_analysis", False
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
        stages (``comp_sets``, ``reviews_scrape``, ``details_scrape``,
        ``listing_summaries``) read the search-results file to enumerate
        listing IDs.

        Args:
            stage_name: Pipeline stage identifier.
            zipcode: Active zipcode.

        Returns:
            List of expected output file paths.  Empty if the stage is unknown
            or prerequisite data (e.g. search results) is missing.
        """
        if stage_name == "search_results":
            search_dir = self.STAGE_OUTPUT_DIRS.get(
                "search_results", "outputs/01_search_results"
            )
            return [os.path.join(search_dir, f"search_results_{zipcode}.json")]

        if stage_name == "comp_sets":
            listing_ids = self._get_listing_ids_for_zipcode(zipcode)
            if not listing_ids:
                return []
            comp_dir = self.STAGE_OUTPUT_DIRS.get("comp_sets", "outputs/03_comp_sets")
            files = [
                os.path.join(comp_dir, f"listing_{lid}.json") for lid in listing_ids
            ]
            files.append(os.path.join(comp_dir, f"comp_set_{zipcode}.json"))
            return files

        if stage_name == "reviews_scrape":
            listing_ids = self._get_listing_ids_for_zipcode(zipcode)
            if not listing_ids:
                return []
            reviews_dir = self.STAGE_OUTPUT_DIRS.get(
                "reviews_scrape", "outputs/04_reviews_scrape"
            )
            return [
                os.path.join(reviews_dir, f"reviews_{zipcode}_{lid}.json")
                for lid in listing_ids
            ]

        if stage_name == "details_scrape":
            listing_ids = self._get_listing_ids_for_zipcode(zipcode)
            if not listing_ids:
                return []
            details_dir = self.STAGE_OUTPUT_DIRS.get(
                "details_scrape", "outputs/02_details_scrape"
            )
            return [
                os.path.join(details_dir, f"property_details_{lid}.json")
                for lid in listing_ids
            ]

        if stage_name == "listing_summaries":
            listing_ids = self._get_review_listing_ids_for_zipcode(zipcode)
            if not listing_ids:
                return []
            summaries_dir = self.STAGE_OUTPUT_DIRS.get(
                "listing_summaries", "outputs/06_listing_summaries"
            )
            return [
                os.path.join(summaries_dir, f"listing_summary_{zipcode}_{lid}.json")
                for lid in listing_ids
            ]

        if stage_name == "details_results":
            dr_dir = self.STAGE_OUTPUT_DIRS.get(
                "details_results", "outputs/05_details_results"
            )
            return [
                os.path.join(dr_dir, f"property_amenities_matrix_{zipcode}.csv"),
                os.path.join(
                    dr_dir, f"property_amenities_matrix_cleaned_{zipcode}.csv"
                ),
                os.path.join(dr_dir, f"house_rules_details_{zipcode}.json"),
                os.path.join(dr_dir, f"property_descriptions_{zipcode}.json"),
                os.path.join(dr_dir, f"neighborhood_highlights_{zipcode}.json"),
            ]

        if stage_name == "area_summary":
            return [
                f"reports/area_summary_{zipcode}.md",
            ]

        if stage_name == "correlation_results":
            cr_dir = self.STAGE_OUTPUT_DIRS.get(
                "correlation_results", "outputs/08_correlation_results"
            )
            files: list[str] = []
            for metric in self.correlation_metrics:
                files.append(
                    os.path.join(cr_dir, f"correlation_stats_{metric}_{zipcode}.json")
                )
                files.append(f"reports/correlation_insights_{metric}_{zipcode}.md")
            return files

        if stage_name == "description_analysis":
            da_dir = self.STAGE_OUTPUT_DIRS.get(
                "description_analysis", "outputs/09_description_analysis"
            )
            return [
                os.path.join(da_dir, f"description_quality_stats_{zipcode}.json"),
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
            stage_name: Pipeline stage identifier (e.g. "reviews_scrape").
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
            stage_name: Pipeline stage identifier (e.g. "comp_sets").
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
        search_dir = self.STAGE_OUTPUT_DIRS.get(
            "search_results", "outputs/01_search_results"
        )
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
            "reviews_scrape", "outputs/04_reviews_scrape"
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

        If any ``force_refresh_*`` flag loaded from config is ``True``, only
        the analysis stages (``CASCADE_TARGET_STAGES``) that come *after* it
        in :pyattr:`STAGE_ORDER` are set to ``True``.  Non-analysis stages
        are never auto-refreshed by upstream flags.
        """
        cascade_active = False
        cascaded: list[str] = []
        for stage in self.STAGE_ORDER:
            if cascade_active:
                if stage in self.CASCADE_TARGET_STAGES:
                    if not self.force_refresh_flags.get(stage, False):
                        cascaded.append(stage)
                    self.force_refresh_flags[stage] = True
            elif self.force_refresh_flags.get(stage, False):
                cascade_active = True

        if cascaded:
            logger.info(
                "Init cascade: auto-set force_refresh for analysis stages: "
                f"{', '.join(cascaded)}"
            )

    def cascade_force_refresh(self, stage_name: str) -> None:
        """Force-refresh analysis stages that come after *stage_name*.

        Only stages in ``CASCADE_TARGET_STAGES`` are affected.  Non-analysis
        stages are never force-refreshed by cascade.

        Args:
            stage_name: The stage whose refresh should cascade downstream.
        """
        if stage_name not in self.STAGE_ORDER:
            logger.warning(f"Unknown stage '{stage_name}' — cascade skipped.")
            return

        stage_index = self.STAGE_ORDER.index(stage_name)
        downstream = self.STAGE_ORDER[stage_index + 1 :]
        targets = [s for s in downstream if s in self.CASCADE_TARGET_STAGES]

        if targets:
            for later_stage in targets:
                self.force_refresh_flags[later_stage] = True
            logger.info(
                f"Stage '{stage_name}' refreshed — cascading force_refresh to: "
                f"{', '.join(targets)}"
            )

    def notify_stage_ran(self, stage_name: str) -> None:
        """Notify the cache that a stage performed actual work.

        Called after any stage completes work (whether ``clear_and_run`` or
        ``resume``).  Forces a refresh of downstream analysis stages in
        ``CASCADE_TARGET_STAGES`` so their outputs reflect the updated data.

        Args:
            stage_name: The stage that just ran.
        """
        if stage_name not in self.STAGE_ORDER:
            logger.warning(f"Unknown stage '{stage_name}' — notify skipped.")
            return

        stage_index = self.STAGE_ORDER.index(stage_name)
        downstream = self.STAGE_ORDER[stage_index + 1 :]
        targets = [s for s in downstream if s in self.CASCADE_TARGET_STAGES]

        if targets:
            for later_stage in targets:
                self.force_refresh_flags[later_stage] = True
            logger.info(
                f"Stage '{stage_name}' ran — marking analysis stages for refresh: "
                f"{', '.join(targets)}"
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
