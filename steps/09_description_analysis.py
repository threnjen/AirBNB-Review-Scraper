"""Step 09 — Description Analysis: evaluate listing description quality vs ADR."""

import logging
import sys

from review_aggregator.description_analyzer import DescriptionAnalyzer
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "description_analysis"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Score listing descriptions on quality dimensions and correlate with ADR."""
    zone_name = config.get("search_zone_name")

    action = pipeline_cache.should_run_stage(STAGE, zone_name)

    if action == "skip":
        logger.info("Skipping description analysis — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zone(STAGE, zone_name)

    desc_analyzer = DescriptionAnalyzer(zone_name=zone_name)
    desc_analyzer.run_analysis()
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info(f"Description quality analysis for zone {zone_name} completed.")
