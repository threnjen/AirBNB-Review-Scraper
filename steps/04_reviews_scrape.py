"""Step 04 — Reviews Scrape: scrape Airbnb reviews for each listing."""

import logging
import sys

from scraper.reviews_scraper import scrape_reviews
from steps import load_search_results
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "reviews_scrape"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Scrape reviews for each listing, with retry and per-file caching."""
    zipcode = config.get("zipcode", "97067")
    num_listings = config.get("num_listings_to_search", 3)

    action = pipeline_cache.should_run_stage(STAGE, zipcode)

    if action == "skip":
        logger.info("Skipping reviews scraping — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zipcode(STAGE, zipcode)
        pipeline_cache.cascade_force_refresh(STAGE)

    search_results = load_search_results(config, pipeline_cache)
    scrape_reviews(
        zipcode=zipcode,
        search_results=search_results,
        num_listings=num_listings,
        pipeline_cache=pipeline_cache,
    )
    logger.info(f"Reviews scraping for zipcode {zipcode} completed.")
