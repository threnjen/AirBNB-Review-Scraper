import pyairbnb
import json
import time
import random
import os
from scraper.airbnb_searcher import airbnb_searcher
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def retrieve_reviews(zipcode, search_results, num_listings):
    property_ids = [listing["room_id"] for listing in search_results]

    # logger.info(property_ids)
    logger.info(f"There are {len(property_ids)} listings in the area")

    review_results = {}
    total_reviews = 0
    properties_scraped = 0

    if num_listings > len(property_ids):
        num_listings = len(property_ids)

    # for id in property_ids[:num_listings if num_listings > 0 else None]:
    for id in property_ids[:num_listings]:
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

            review_results[id] = single_property_formatted_reviews

            logger.info(
                f"I scraped {len(single_property_formatted_reviews)} reviews for this listing"
            )
            total_reviews += len(single_property_formatted_reviews)
            properties_scraped += 1

            # Save the reviews data to a JSON file
            with open(f"results/reviews_{zipcode}.json", "w", encoding="utf-8") as f:
                f.write(
                    json.dumps(review_results, ensure_ascii=False)
                )  # Extract reviews and save them to a file

            time.sleep(random.uniform(1, 3))

        except Exception as e:
            logger.info(
                f"An error occurred while retrieving reviews for listing ID {id}: {e}"
            )
            properties_scraped += 1
            continue

    logger.info(f"I scraped a total of {total_reviews} reviews across all listings")


def airbnb_scraper(zipcode="97067", iso_code="us", num_listings=3):
    if os.path.isfile("custom_listing_ids.json"):
        with open("custom_listing_ids.json", "r", encoding="utf-8") as f:
            property_ids = json.load(f).keys()
        # logger.info(f"Using {len(property_ids)} custom listing IDs from custom_listing_ids.json")
        search_results = []
        for room_id in property_ids:
            search_results.append({"room_id": room_id})
    else:
        search_results = airbnb_searcher(zipcode, iso_code)
    # logger.info(f"Search results data looks like: {search_results[:1]}")
    retrieve_reviews(
        zipcode=zipcode, search_results=search_results, num_listings=num_listings
    )
