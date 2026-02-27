"""Step 03 — Comp Sets: scrape AirDNA data and compile comp set files."""

import glob
import json
import logging
import os
import sys

from scraper.airdna_scraper import AirDNAScraper
from steps import load_search_results
from utils.pipeline_cache_manager import PipelineCacheManager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "comp_sets"
OUTPUT_DIR = "outputs/03_comp_sets"


def compile_comp_sets(zipcode: str) -> None:
    """Merge per-listing JSON files into a single master comp set file."""
    merged = {}
    duplicates_skipped = 0
    pattern = os.path.join(OUTPUT_DIR, "listing_*.json")

    for filepath in sorted(glob.glob(pattern)):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        for listing_id, details in data.items():
            if listing_id in merged:
                duplicates_skipped += 1
            else:
                merged[listing_id] = details

    master_path = os.path.join(OUTPUT_DIR, f"comp_set_{zipcode}.json")
    with open(master_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=4)

    logger.info(
        f"Compiled {len(merged)} listings into {master_path} "
        f"({duplicates_skipped} duplicates skipped)."
    )


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Scrape AirDNA rentalizer data and compile into comp set."""
    zipcode = config.get("zipcode", "97067")
    cdp_url = config.get("airdna_cdp_url", "http://localhost:9222")
    inspect_mode = config.get("airdna_inspect_mode", False)

    action = pipeline_cache.should_run_stage(STAGE, zipcode)

    if action == "skip":
        logger.info("Skipping AirDNA scraping — cached outputs are fresh.")
        return

    search_results = load_search_results(config, pipeline_cache)
    listing_ids = [str(r.get("room_id", r.get("id", ""))) for r in search_results]
    listing_ids = [i for i in listing_ids if i]

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zipcode(STAGE, zipcode)

    airdna_scraper = AirDNAScraper(
        cdp_url=cdp_url,
        listing_ids=listing_ids,
        inspect_mode=inspect_mode,
        pipeline_cache=pipeline_cache,
    )
    airdna_scraper.run()
    compile_comp_sets(zipcode)
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info("AirDNA per-listing scraping completed.")
