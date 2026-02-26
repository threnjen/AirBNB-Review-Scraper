"""Step 06 — Listing Summaries: generate per-property LLM summaries."""

import logging
import sys

from review_aggregator.property_review_aggregator import PropertyRagAggregator
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "listing_summaries"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Generate an LLM summary for each property's reviews."""
    zipcode = config.get("zipcode", "97067")
    num_listings = config.get("num_listings_to_summarize", 3)
    review_thresh = config.get("review_thresh_to_include_prop", 5)

    action = pipeline_cache.should_run_stage(STAGE, zipcode)

    if action == "skip":
        logger.info("Skipping listing summaries — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zipcode(STAGE, zipcode)
        pipeline_cache.cascade_force_refresh(STAGE)

    rag_property = PropertyRagAggregator(
        num_listings_to_summarize=num_listings,
        review_thresh_to_include_prop=review_thresh,
        zipcode=zipcode,
        pipeline_cache=pipeline_cache,
    )
    rag_property.rag_description_generation_chain()
    logger.info(f"Listing summaries for zipcode {zipcode} completed.")
