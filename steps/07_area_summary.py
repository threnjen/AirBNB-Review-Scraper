"""Step 07 — Area Summary: generate area-level prose summary."""

import logging
import sys

from review_aggregator.area_review_aggregator import AreaRagAggregator
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "area_summary"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Generate area-level prose summary from property listing summaries."""
    zipcode = config.get("zipcode", "97067")
    num_summaries = config.get("num_summary_to_process", 3)
    review_thresh = config.get("review_thresh_to_include_prop", 5)

    action = pipeline_cache.should_run_stage(STAGE, zipcode)

    if action == "skip":
        logger.info("Skipping area summary — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zipcode(STAGE, zipcode)

    rag_area = AreaRagAggregator(
        num_listings=num_summaries,
        review_thresh_to_include_prop=review_thresh,
        zipcode=zipcode,
        pipeline_cache=pipeline_cache,
    )
    rag_area.rag_description_generation_chain()
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info(f"Area prose summary for zipcode {zipcode} completed.")
