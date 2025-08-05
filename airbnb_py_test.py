import pyairbnb
import json
import location_calculator


def airbnb_scraper():
    ne_lat, sw_lat, ne_lon, sw_lon = location_calculator.locationer(97067)

    # Define search parameters
    check_in = "2025-10-08"  # Check-in date
    check_out = "2025-10-14"  # Check-out date

    # Search listings within specified coordinates and date range using keyword arguments
    search_results = pyairbnb.search_all(
        check_in="",
        check_out="",
        ne_lat=ne_lat,
        ne_long=ne_lon,
        sw_lat=sw_lat,
        sw_long=sw_lon,
        zoom_value=5,
        price_min=0,
        price_max=0
    )

    # Save the search results as a JSON file
    with open('search_results.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(search_results))  # Convert results to JSON and write to file

    #print(f"The search results json is printed as {type(search_results)}")

    room_ids = [listing["room_id"] for listing in search_results]

    #print(room_ids)

    review_results = {}

    for id in room_ids[:2]:

        room_url = f"https://www.airbnb.com/rooms/{id}"  # Listing URL
        # Retrieve reviews for the specified listing
        single_property_reviews = pyairbnb.get_reviews(room_url = room_url)
        single_property_formatted_reviews = []

        for review in single_property_reviews:
            single_property_formatted_reviews.append({
                "review": review.get("comments", ""),
                "rating": review.get("rating", 0)
            })

        review_results[id] = single_property_formatted_reviews

    print(f"The review results dictionary looks like {review_results}")

    # Save the reviews data to a JSON file
    with open('reviews.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(review_results))  # Extract reviews and save them to a file


airbnb_scraper()