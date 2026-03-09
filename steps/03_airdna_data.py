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

STAGE = "airdna_data"
OUTPUT_DIR = "outputs/03_airdna_data"


def compile_airdna_data(zone_name: str, output_dir: str = OUTPUT_DIR) -> None:
    """Merge per-listing JSON files into a single master comp set file."""
    merged = {}
    duplicates_skipped = 0
    pattern = os.path.join(output_dir, "listing_*.json")

    for filepath in sorted(glob.glob(pattern)):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        for listing_id, details in data.items():
            if listing_id in merged:
                duplicates_skipped += 1
            else:
                merged[listing_id] = details

    master_path = os.path.join(output_dir, f"comp_set_{zone_name}.json")
    with open(master_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=4)

    logger.info(
        f"Compiled {len(merged)} listings into {master_path} "
        f"({duplicates_skipped} duplicates skipped)."
    )


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Scrape AirDNA rentalizer data and compile into comp set."""
    zone_name = config.get("search_zone_name")
    cdp_url = config.get("airdna_cdp_url", "http://localhost:9222")
    inspect_mode = config.get("airdna_inspect_mode", False)

    action = pipeline_cache.should_run_stage(STAGE, zone_name)

    if action == "skip":
        logger.info("Skipping AirDNA scraping — cached outputs are fresh.")
        return

    search_results = load_search_results(config, pipeline_cache)
    listing_ids = [str(r.get("room_id", r.get("id", ""))) for r in search_results]
    listing_ids = [i for i in listing_ids if i]

    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zone(STAGE, zone_name)

    airdna_scraper = AirDNAScraper(
        cdp_url=cdp_url,
        listing_ids=listing_ids,
        inspect_mode=inspect_mode,
        pipeline_cache=pipeline_cache,
    )
    airdna_scraper.run()
    compile_airdna_data(zone_name)
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info("AirDNA per-listing scraping completed.")
