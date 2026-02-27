"""Step 08 — Correlation Results: analyse property attributes vs metrics."""

import logging
import sys

from review_aggregator.correlation_analyzer import CorrelationAnalyzer
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "correlation_results"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Run correlation analysis between property features and revenue metrics."""
    zipcode = config.get("zipcode", "97067")
    metrics = config.get("correlation_metrics", ["adr", "occupancy"])
    top_pct = config.get("correlation_top_percentile", 25)
    bottom_pct = config.get("correlation_bottom_percentile", 25)

    action = pipeline_cache.should_run_stage(STAGE, zipcode)

    if action == "skip":
        logger.info("Skipping correlation analysis — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zipcode(STAGE, zipcode)

    analyzer = CorrelationAnalyzer(
        zipcode=zipcode,
        metrics=metrics,
        top_percentile=top_pct,
        bottom_percentile=bottom_pct,
    )
    analyzer.run_analysis()
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info(f"Correlation analysis for zipcode {zipcode} completed.")
