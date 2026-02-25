import json
import logging
import os
import random
import sys
import time

import pyairbnb

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def scrape_reviews(zipcode, search_results, num_listings, pipeline_cache=None):
    property_ids = [listing["room_id"] for listing in search_results]

    # logger.info(property_ids)
    logger.info(f"There are {len(property_ids)} listings in the area")

    total_reviews = 0
    properties_scraped = 0

    if num_listings > len(property_ids):
        num_listings = len(property_ids)

    # for id in property_ids[:num_listings if num_listings > 0 else None]:
    for id in property_ids[:num_listings]:
        output_path = f"outputs/03_reviews_scraped/reviews_{zipcode}_{id}.json"

        if pipeline_cache and pipeline_cache.is_file_fresh("reviews", output_path):
            logger.info(f"Skipping listing {id} — cached reviews are fresh.")
            properties_scraped += 1
            continue

        room_url = f"https://www.airbnb.com/rooms/{id}"  # Listing URL
        logger.info(
            f"Retrieving reviews for listing ID {id}; property {properties_scraped + 1} of {num_listings}"
        )

        try:
            # Retrieve reviews for the specified listing
            single_property_reviews = pyairbnb.get_reviews(room_url=room_url)
            single_property_formatted_reviews = []

            for review in single_property_reviews:
                single_property_formatted_reviews.append(
                    {
                        "review": review.get("comments", ""),
                        "rating": review.get("rating", 0),
                    }
                )

            review_results = {id: single_property_formatted_reviews}

            logger.info(
                f"I scraped {len(single_property_formatted_reviews)} reviews for this listing"
            )
            total_reviews += len(single_property_formatted_reviews)
            properties_scraped += 1

            # Save the reviews data to a JSON file
            os.makedirs("outputs/03_reviews_scraped", exist_ok=True)
            with open(
                output_path,
                "w",
                encoding="utf-8",
            ) as f:
                f.write(
                    json.dumps(review_results, ensure_ascii=False)
                )  # Extract reviews and save them to a file

            if pipeline_cache:
                pipeline_cache.record_output("reviews", output_path)

            time.sleep(random.uniform(1, 3))

        except Exception as e:
            logger.warning(
                f"An error occurred while retrieving reviews for listing ID {id}: {e}"
            )
            properties_scraped += 1
            continue

    logger.info(f"I scraped a total of {total_reviews} reviews across all listings")
