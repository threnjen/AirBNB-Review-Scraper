import pyairbnb
import json
import time
import random
import location_calculator
import sys


def airbnb_scraper(zipcode, iso_code = "us", num_listings = 0):
    ne_lat, sw_lat, ne_lon, sw_lon = location_calculator.locationer(postal_code = zipcode, iso_code = iso_code)

    def boxed_search(ne_lat, sw_lat, ne_lon, sw_lon, dimensions=2):

        boxes = []

        lat_step = (ne_lat - sw_lat) / dimensions
        lon_step = (ne_lon - sw_lon) / dimensions

        for i in range(dimensions):
            for j in range(dimensions):
                box_sw_lat = sw_lat + i * lat_step
                box_sw_lon = sw_lon + j * lon_step
                box_ne_lat = box_sw_lat + lat_step
                box_ne_lon = box_sw_lon + lon_step
                boxes.append((box_sw_lat, box_sw_lon, box_ne_lat, box_ne_lon))

        return boxes

    # print(f"All of our boxes are {boxed_search(ne_lat, sw_lat, ne_lon, sw_lon)}")
    # print(f"The first box is {boxed_search(ne_lat, sw_lat, ne_lon, sw_lon)[0]}")

    search_results = []

    for box in boxed_search(ne_lat, sw_lat, ne_lon, sw_lon):
        box_search_results = pyairbnb.search_all(
            check_in="",
            check_out="",
            ne_lat=box[2],
            ne_long=box[3],
            sw_lat=box[0],
            sw_long=box[1],
            zoom_value=2,
            price_min=0,
            price_max=0,
        )
        # print(f"Searching with coordinates: NE({box[2]}, {box[3]}), SW({box[0]}, {box[1]})")
        # print(f"There are {len(box_search_results)} listings in this box")
        if len(box_search_results) >= 280:
            print(f"Box {box} has hit the request cap, increase dimensions.")
        search_results.extend(box_search_results)
        time.sleep(random.uniform(1, 5))

    # Save the search results as a JSON file
    with open(f"search_results_{zipcode}.json", "w", encoding="utf-8") as f:
        f.write(
            json.dumps(search_results, ensure_ascii=False)
        )  # Convert results to JSON and write to file

    # print(f"The search results json is printed as {type(search_results)}")

    room_ids = [listing["room_id"] for listing in search_results]

    # print(room_ids)
    print(f"There are {len(room_ids)} listings in the area")

    review_results = {}
    total_reviews = 0

    for id in room_ids[:num_listings if num_listings > 0 else None]:

        room_url = f"https://www.airbnb.com/rooms/{id}"  # Listing URL
        print(f"Retrieving reviews for listing ID {id}")
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

        print(
            f"I scraped {len(single_property_formatted_reviews)} reviews for this listing"
        )
        total_reviews += len(single_property_formatted_reviews)

        time.sleep(random.uniform(1, 3))

    print(f"I scraped a total of {total_reviews} reviews across all listings")

    # Save the reviews data to a JSON file
    with open(f"reviews_{zipcode}.json", "w", encoding="utf-8") as f:
        f.write(
            json.dumps(review_results, ensure_ascii=False)
        )  # Extract reviews and save them to a file

# airbnb_scraper(zipcode = sys.argv[1], iso_code = sys.argv[2])

# Scraper steps:
# Make a zip code variable to locate an area - Done
# This specifically means I need to turn a zip code into all the listing ids in that area (store as a list)
# Start by scraping one of the found listing ids
# Loop that code to scrape all listings in the area
# Scrape all reviews for listings in the area
# Use AI to summarize pros and cons
# Spend hundreds of thousands of dollars on a house
