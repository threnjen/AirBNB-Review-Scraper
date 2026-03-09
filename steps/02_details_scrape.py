"""Step 02 — Details Scrape: scrape Airbnb listing detail pages."""

import logging
import sys

from scraper.details_scraper import scrape_details
from steps import load_search_results
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "details_scrape"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Scrape property detail pages for each listing found in search results."""
    zone_name = config.get("search_zone_name")
    num_listings = config.get("num_listings_to_search", 3)

    action = pipeline_cache.should_run_stage(STAGE, zone_name)

    if action == "skip":
        logger.info("Skipping details scraping — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zone(STAGE, zone_name)

    search_results = load_search_results(config, pipeline_cache)
    scrape_details(
        search_results=search_results,
        num_listings=num_listings,
        pipeline_cache=pipeline_cache,
    )
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info(f"Details scraping for zone {zone_name} completed.")
