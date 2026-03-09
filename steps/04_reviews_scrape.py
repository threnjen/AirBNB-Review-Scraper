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
    zone_name = config.get("search_zone_name")
    num_listings = config.get("num_listings_to_search", 3)

    action = pipeline_cache.should_run_stage(STAGE, zone_name)

    if action == "skip":
        logger.info("Skipping reviews scraping — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zone(STAGE, zone_name)

    search_results = load_search_results(config, pipeline_cache)
    scrape_reviews(
        zone_name=zone_name,
        search_results=search_results,
        num_listings=num_listings,
        pipeline_cache=pipeline_cache,
    )
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info(f"Reviews scraping for zone {zone_name} completed.")
