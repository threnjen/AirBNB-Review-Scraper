"""Step 01 — Search Results: find Airbnb listings for a zipcode."""

import logging
import sys

from steps import load_search_results
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "search_results"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> list[dict]:
    """Run the Airbnb search and return the results list.

    Always executes (or loads from cache) because downstream steps need the
    search results as input.
    """
    search_results = load_search_results(config, pipeline_cache)
    logger.info(f"Search results: {len(search_results)} listings found.")
    return search_results
