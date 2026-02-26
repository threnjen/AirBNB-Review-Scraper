import json
import logging
import os
import random
import sys
import time
from typing import Any, Optional

import pyairbnb

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds; doubles each attempt
FAILURE_THRESHOLD = 0.20  # retry entire pass if >20% of listings fail
PASS_RETRY_WAIT_SECONDS = 120  # cooldown between full passes


def scrape_reviews(
    zipcode: str,
    search_results: list[dict[str, Any]],
    num_listings: int,
    pipeline_cache: Optional[Any] = None,
) -> None:
    """Scrape Airbnb reviews for each listing and save to JSON files.

    Retries each listing up to ``MAX_RETRIES`` times with exponential back-off
    on transient errors.  If more than 20% of listings fail after a full pass,
    the entire pass is retried after a cooldown.  Files are **not** written for
    listings that return zero reviews.

    Args:
        zipcode: Target area zip code used in output file names.
        search_results: List of dicts, each containing a ``room_id`` key.
        num_listings: Maximum number of listings to process.
        pipeline_cache: Optional cache manager; fresh files are skipped.
    """
    property_ids = [listing["room_id"] for listing in search_results]

    if num_listings > len(property_ids):
        num_listings = len(property_ids)

    ids_to_scrape = property_ids[:num_listings]
    total = len(ids_to_scrape)
    total_reviews = 0
    resolved: set[str] = set()  # IDs that succeeded or were cached

    # Pre-scan: identify listings with review files already on disk
    for id in ids_to_scrape:
        output_path = f"outputs/03_reviews_scraped/reviews_{zipcode}_{id}.json"
        if os.path.exists(output_path):
            resolved.add(id)

    already_scraped = len(resolved)
    remaining = total - already_scraped
    logger.info(
        f"There are {total} listings in the area"
        f" — {already_scraped} already scraped, {remaining} to scrape"
    )

    pass_number = 0

    while True:
        pass_number += 1
        pass_failed = 0
        remaining = total - len(resolved)
        scrape_index = 0

        logger.info(
            f"--- Pass {pass_number} | "
            f"{remaining} to scrape, {len(resolved)} resolved of {total} total ---"
        )

        for id in ids_to_scrape:
            if id in resolved:
                continue

            output_path = f"outputs/03_reviews_scraped/reviews_{zipcode}_{id}.json"

            room_url = f"https://www.airbnb.com/rooms/{id}"
            scrape_index += 1
            logger.info(
                f"Retrieving reviews for listing ID {id}; "
                f"property {scrape_index} of {remaining}"
            )

            single_property_reviews = _fetch_reviews_with_retry(id, room_url)

            if single_property_reviews is None:
                # All per-request retries exhausted — count as failed for this pass.
                pass_failed += 1
                continue

            single_property_formatted_reviews = [
                {
                    "review": review.get("comments", ""),
                    "rating": review.get("rating", 0),
                }
                for review in single_property_reviews
            ]

            resolved.add(id)

            if len(single_property_formatted_reviews) == 0:
                logger.info(f"No reviews found for listing {id}, skipping file write.")
                continue

            logger.info(
                f"I scraped {len(single_property_formatted_reviews)} reviews "
                f"for this listing"
            )
            total_reviews += len(single_property_formatted_reviews)

            # Save the reviews data to a JSON file
            review_results = {id: single_property_formatted_reviews}
            os.makedirs("outputs/03_reviews_scraped", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(review_results, ensure_ascii=False))

            time.sleep(random.uniform(3, 6))

        # Check if too many listings failed and we should retry the pass
        missing = total - len(resolved)
        logger.info(
            f"Pass {pass_number} complete: "
            f"resolved={len(resolved)}/{total}, "
            f"failed(this pass)={pass_failed}, missing={missing}/{total}"
        )

        if total > 0 and missing / total > FAILURE_THRESHOLD:
            logger.warning(
                f"{missing}/{total} listings still missing "
                f"(>{FAILURE_THRESHOLD:.0%}). "
                f"Waiting {PASS_RETRY_WAIT_SECONDS}s before retrying..."
            )
            time.sleep(PASS_RETRY_WAIT_SECONDS)
        else:
            break

    logger.info(f"I scraped a total of {total_reviews} reviews across all listings")


def _fetch_reviews_with_retry(
    listing_id: str, room_url: str
) -> Optional[list[dict[str, Any]]]:
    """Attempt to fetch reviews, retrying with exponential back-off.

    Args:
        listing_id: The Airbnb listing ID (for logging).
        room_url: Full URL to the listing page.

    Returns:
        List of raw review dicts on success, or ``None`` after all retries
        are exhausted.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return pyairbnb.get_reviews(room_url=room_url)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{MAX_RETRIES} failed for listing "
                    f"{listing_id}: {e}  — retrying in {delay}s"
                )
                time.sleep(delay)
            else:
                logger.warning(
                    f"All {MAX_RETRIES} attempts failed for listing "
                    f"{listing_id}: {e}  — skipping."
                )
    return None
