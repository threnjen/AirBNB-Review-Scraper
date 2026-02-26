import json
import logging
import os
import random
import sys
import time

import pyairbnb

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def scrape_details(search_results, num_listings, pipeline_cache=None):
    property_ids = [listing["room_id"] for listing in search_results]

    # logger.info(property_ids)
    logger.info(f"There are {len(property_ids)} listings in the area")
    properties_scraped = 0

    if num_listings > len(property_ids):
        num_listings = len(property_ids)

    # for id in property_ids[:num_listings if num_listings > 0 else None]:
    for room_id in property_ids[:num_listings]:
        output_path = f"outputs/04_details_scraped/property_details_{room_id}.json"

        if pipeline_cache and pipeline_cache.is_file_fresh("details", output_path):
            logger.info(f"Skipping listing {room_id} — cached details are fresh.")
            properties_scraped += 1
            continue

        logger.info(
            f"Retrieving details for listing ID {room_id}; property {properties_scraped + 1} of {num_listings}"
        )

        try:
            # Retrieve details for the specified listing
            single_property_details = pyairbnb.get_details(room_id=room_id)

            properties_scraped += 1

            # Save the details data to a JSON file
            os.makedirs("outputs/04_details_scraped", exist_ok=True)
            with open(
                output_path,
                "w",
                encoding="utf-8",
            ) as f:
                f.write(
                    json.dumps(single_property_details, ensure_ascii=False)
                )  # Extract details and save them to a file

            time.sleep(random.uniform(1, 3))

        except Exception as e:
            logger.warning(
                f"An error occurred while retrieving details for listing ID {room_id}: {e}"
            )
            continue

    logger.info(
        f"I scraped a total of {properties_scraped} properties across all listings"
    )
