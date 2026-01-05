import pyairbnb
import json
import time
import random
import scraper.location_calculator as location_calculator


def airbnb_searcher(zipcode: str, iso_code: str ="us"):
    ne_lat, sw_lat, ne_lon, sw_lon = location_calculator.locationer(
        postal_code=zipcode, iso_code=iso_code
    )

    def boxed_search(ne_lat: float, sw_lat: float, ne_lon: float, sw_lon: float, dimensions: int=2) -> list:
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
    with open(f"results/search_results_{zipcode}.json", "w", encoding="utf-8") as f:
        f.write(
            json.dumps(search_results, ensure_ascii=False)
        )  # Convert results to JSON and write to file

    # print(f"The search results json is printed as {type(search_results)}")

    return search_results