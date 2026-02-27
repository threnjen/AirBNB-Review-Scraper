"""Pipeline step runners — one module per stage."""

import json
import logging
import sys

from scraper.airbnb_searcher import airbnb_searcher
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def load_search_results(
    config: dict, pipeline_cache: PipelineCacheManager
) -> list[dict]:
    """Load (or run) search results needed by downstream steps.

    Called internally by steps that depend on the search output.
    """
    zipcode = config.get("zipcode", "97067")
    iso_code = config.get("iso_code", "us")
    search_output = f"outputs/01_search_results/search_results_{zipcode}.json"

    action = pipeline_cache.should_run_stage("search_results", zipcode)

    if action == "skip":
        with open(search_output, "r", encoding="utf-8") as f:
            return json.load(f)

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zipcode("search_results", zipcode)

    results = airbnb_searcher(zipcode, iso_code)
    pipeline_cache.notify_stage_ran("search_results")
    return results
