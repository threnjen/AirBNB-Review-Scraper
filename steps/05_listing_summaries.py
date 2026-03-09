"""Step 06 — Listing Summaries: generate per-property LLM summaries."""

import logging
import sys

from review_aggregator.property_review_aggregator import PropertyAggregator
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "listing_summaries"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Generate an LLM summary for each property's reviews."""
    zone_name = config.get("search_zone_name")
    num_listings = config.get("num_listings_to_summarize", 3)
    review_thresh = config.get("review_thresh_to_include_prop", 5)

    action = pipeline_cache.should_run_stage(STAGE, zone_name)

    if action == "skip":
        logger.info("Skipping listing summaries — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zone(STAGE, zone_name)

    rag_property = PropertyAggregator(
        num_listings_to_summarize=num_listings,
        review_thresh_to_include_prop=review_thresh,
        zone_name=zone_name,
        pipeline_cache=pipeline_cache,
    )
    rag_property.task_chain()
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info(f"Listing summaries for zone {zone_name} completed.")
