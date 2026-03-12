"""Step 10 = Train Model on all available data."""

import logging
import sys

from utils.pipeline_cache_manager import PipelineCacheManager
from ml.train_2_level import main

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

STAGE = "machine_learning_model"


def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    """Score listing descriptions on quality dimensions and correlate with ADR."""
    zone_name = config.get("search_zone_name")

    action = pipeline_cache.should_run_stage(STAGE, zone_name)

    if action == "skip":
        logger.info("Skipping ML training — cached outputs are fresh.")
        return

    if action == "clear_and_run":
        pass

    main()
    pipeline_cache.notify_stage_ran(STAGE)
    logger.info(f"ML Training for zone {zone_name} completed.")
