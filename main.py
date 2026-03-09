import importlib
import logging
import sys

from utils.pipeline_cache_manager import PipelineCacheManager
from utils.tiny_file_handler import load_config

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Ordered (module_name, config_flag) pairs — executed top-to-bottom.
PIPELINE_STEPS = [
    ("steps.01_search_results", "search_results"),
    ("steps.02_details_scrape", "details_scrape"),
    ("steps.03_comp_sets", "comp_sets"),
    ("steps.04_reviews_scrape", "reviews_scrape"),
    ("steps.05_details_results", "details_results"),
    ("steps.06_listing_summaries", "listing_summaries"),
    ("steps.07_area_summary", "area_summary"),
    ("steps.08_correlation_results", "correlation_results"),
    ("steps.09_description_analysis", "description_analysis"),
]


class AirBnbReviewAggregator:
    def __init__(self):
        self.config: dict = {}
        self.pipeline_cache = PipelineCacheManager()
        self.load_configs()
        logger.info(f"Configuration loaded: {self.config}")

    # --- public properties (kept for backwards compat / tests) ---

    @property
    def zipcode(self) -> str:
        return self.config.get("zipcode", "97067")

    @property
    def iso_code(self) -> str:
        return self.config.get("iso_code", "us")

    def load_configs(self):
        self.config = load_config()
        self.pipeline_cache = PipelineCacheManager()

    # ----- main entry point -----
    def run_tasks_from_config(self):
        """Run each pipeline step whose config flag is enabled."""
        for module_name, flag_name in PIPELINE_STEPS:
            if self.config.get(flag_name, False):
                step_module = importlib.import_module(module_name)
                step_module.run(self.config, self.pipeline_cache)


if __name__ == "__main__":
    aggregator = AirBnbReviewAggregator()
    aggregator.run_tasks_from_config()
