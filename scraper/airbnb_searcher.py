import json
import logging
import math
import os
import random
import sys
import time

import pyairbnb

from scraper.location_calculator import bounding_box_from_center

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

_MILES_PER_LAT_DEGREE = 69.0


def filter_listings_by_radius(
    listings: list, center_lat: float, center_lon: float, radius_miles: float
) -> list:
    """Remove listings outside the Euclidean radius from the search center.

    Handles the pyairbnb typo key 'longitud' (missing final 'e').
    Listings without valid coordinates are excluded.

    Args:
        listings: Raw search results from pyairbnb.
        center_lat: Search center latitude.
        center_lon: Search center longitude.
        radius_miles: Maximum allowed distance from center in miles.

    Returns:
        Subset of listings within the radius.
    """
    within = []
    for listing in listings:
        coords = listing.get("coordinates") or {}
        lat = coords.get("latitude")
        lon = coords.get("longitud")  # pyairbnb typo: missing final 'e'
        if lat is None or lon is None:
            continue

        lat_diff_miles = (lat - center_lat) * _MILES_PER_LAT_DEGREE
        lon_diff_miles = (
            (lon - center_lon)
            * _MILES_PER_LAT_DEGREE
            * math.cos(math.radians(center_lat))
        )
        distance = math.sqrt(lat_diff_miles**2 + lon_diff_miles**2)

        if distance <= radius_miles:
            within.append(listing)

    return within


def airbnb_searcher(
    start_lat: float,
    start_long: float,
    search_radius_miles: float,
    search_zone_name: str,
):
    ne_lat, sw_lat, ne_lon, sw_lon = bounding_box_from_center(
        start_lat, start_long, search_radius_miles
    )

    def boxed_search(
        ne_lat: float, sw_lat: float, ne_lon: float, sw_lon: float, dimensions: int = 2
    ) -> list:
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

    logger.info(f"All of our boxes are {boxed_search(ne_lat, sw_lat, ne_lon, sw_lon)}")

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
        if len(box_search_results) >= 280:
            logger.info(f"Box {box} has hit the request cap, increase dimensions.")
        search_results.extend(box_search_results)
        time.sleep(random.uniform(1, 5))

    search_results = filter_listings_by_radius(
        search_results, start_lat, start_long, search_radius_miles
    )

    os.makedirs("outputs/01_search_results", exist_ok=True)
    with open(
        f"outputs/01_search_results/search_results_{search_zone_name}.json",
        "w",
        encoding="utf-8",
    ) as f:
        f.write(json.dumps(search_results, ensure_ascii=False))

    return search_results
