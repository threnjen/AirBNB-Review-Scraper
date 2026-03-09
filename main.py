import importlib
import logging
import sys

from utils.pipeline_cache_manager import PipelineCacheManager
from utils.tiny_file_handler import load_config, validate_config

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Scraping steps run first (01–04); processing steps run after (05–09).
SCRAPING_STEPS = [
    ("steps.01_search_results", "search_results"),
    ("steps.02_details_scrape", "details_scrape"),
    ("steps.03_airdna_data", "airdna_data"),
    ("steps.04_reviews_scrape", "reviews_scrape"),
]

PROCESSING_STEPS = [
    ("steps.06_details_results", "details_results"),
    ("steps.05_listing_summaries", "listing_summaries"),
    ("steps.07_area_summary", "area_summary"),
    ("steps.08_correlation_results", "correlation_results"),
    ("steps.09_description_analysis", "description_analysis"),
]

# Ordered (module_name, config_flag) pairs — executed top-to-bottom.
PIPELINE_STEPS = SCRAPING_STEPS + PROCESSING_STEPS


class AirBnbReviewAggregator:
    def __init__(self):
        self.config: dict = {}
        self.pipeline_cache = PipelineCacheManager()
        self.load_configs()
        logger.info(f"Configuration loaded: {self.config}")

    # --- public properties ---

    @property
    def search_zone_name(self) -> str:
        return self.config.get("search_zone_name", "")

    @property
    def iso_code(self) -> str:
        return self.config.get("iso_code", "us")

    def load_configs(self):
        self.config = load_config()
        self.pipeline_cache = PipelineCacheManager()

    # ----- main entry point -----
    def run_tasks_from_config(self):
        """Validate config then run each pipeline step whose config flag is enabled."""
        validate_config(self.config)
        for module_name, flag_name in PIPELINE_STEPS:
            if self.config.get(flag_name, False):
                step_module = importlib.import_module(module_name)
                step_module.run(self.config, self.pipeline_cache)


if __name__ == "__main__":
    aggregator = AirBnbReviewAggregator()
    aggregator.run_tasks_from_config()
