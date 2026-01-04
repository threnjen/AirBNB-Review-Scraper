import pyairbnb
import json
import time
import random
import os
from scraper.airbnb_searcher import airbnb_searcher


def retrieve_details(search_results, num_listings):
    property_ids = [listing["room_id"] for listing in search_results]

    # print(property_ids)
    print(f"There are {len(property_ids)} listings in the area")
    properties_scraped = 0

    if num_listings > len(property_ids):
        num_listings = len(property_ids)

    # for id in property_ids[:num_listings if num_listings > 0 else None]:
    for room_id in property_ids[:num_listings]:
        print(
            f"Retrieving details for listing ID {room_id}; property {properties_scraped + 1} of {num_listings}"
        )

        try:
            # Retrieve details for the specified listing
            single_property_details = pyairbnb.get_details(room_id=room_id)

            properties_scraped += 1

            # Save the details data to a JSON file
            with open(
                f"results/property_details_{room_id}.json", "w", encoding="utf-8"
            ) as f:
                f.write(
                    json.dumps(single_property_details, ensure_ascii=False)
                )  # Extract details and save them to a file

            time.sleep(random.uniform(1, 3))

        except Exception as e:
            print(
                f"An error occurred while retrieving details for listing ID {room_id}: {e}"
            )
            continue

    print(f"I scraped a total of {properties_scraped} properties across all listings")


def airbnb_scraper(zipcode="97067", iso_code="us", num_listings=3):
    if os.path.isfile("custom_listing_ids.json"):
        with open("custom_listing_ids.json", "r", encoding="utf-8") as f:
            property_ids = json.load(f)
        # print(f"Using {len(property_ids)} custom listing IDs from custom_listing_ids.json")
        search_results = []
        for room_id in property_ids:
            search_results.append({"room_id": room_id})
    else:
        search_results = airbnb_searcher(zipcode, iso_code)
    # print(f"Search results data looks like: {search_results[:1]}")
    print(len(search_results))
    retrieve_details(search_results=search_results, num_listings=num_listings)
