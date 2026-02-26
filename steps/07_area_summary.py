"""Step 07 — Area Summary: generate area-level prose + extract structured data."""

import logging
import sys

from review_aggregator.area_review_aggregator import AreaRagAggregator
from review_aggregator.data_extractor import DataExtractor
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "area_summary"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Generate area-level prose summary and extract structured category data.

    Combines the former ``aggregate_summaries`` and ``extract_data`` steps.
    """
    zipcode = config.get("zipcode", "97067")
    num_summaries = config.get("num_summary_to_process", 3)
    review_thresh = config.get("review_thresh_to_include_prop", 5)

    action = pipeline_cache.should_run_stage(STAGE, zipcode)

    if action == "skip":
        logger.info("Skipping area summary — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zipcode(STAGE, zipcode)
        pipeline_cache.cascade_force_refresh(STAGE)

    # Part A: generate prose area summary (reports/*.json + *.md)
    rag_area = AreaRagAggregator(
        num_listings=num_summaries,
        review_thresh_to_include_prop=review_thresh,
        zipcode=zipcode,
        pipeline_cache=pipeline_cache,
    )
    rag_area.rag_description_generation_chain()
    logger.info(f"Area prose summary for zipcode {zipcode} completed.")

    # Part B: extract structured category data (outputs/07_area_summary/)
    extractor = DataExtractor(zipcode=zipcode)
    extractor.run_extraction()
    logger.info(f"Area data extraction for zipcode {zipcode} completed.")
