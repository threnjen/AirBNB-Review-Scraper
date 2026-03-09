"""Step 05 — Details Results: build structured fileset from scraped details."""

import logging
import sys

from scraper.details_fileset_build import DetailsFilesetBuilder
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "details_results"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Parse raw detail JSON into amenities matrix, descriptions, etc."""
    zone_name = config.get("search_zone_name")
    use_categoricals = config.get("dataset_use_categoricals", False)
    min_days_available = config.get("min_days_available", 100)

    action = pipeline_cache.should_run_stage(STAGE, zone_name)

    if action == "skip":
        logger.info("Skipping details fileset build — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zone(STAGE, zone_name)

    comp_set_filepath = f"outputs/03_airdna_data/{zone_name}/comp_set_{zone_name}.json"
    fileset_builder = DetailsFilesetBuilder(
        use_categoricals=use_categoricals,
        comp_set_filepath=comp_set_filepath,
        zone_name=zone_name,
        min_days_available=min_days_available,
    )
    fileset_builder.build_fileset()
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info("Building details fileset completed.")
