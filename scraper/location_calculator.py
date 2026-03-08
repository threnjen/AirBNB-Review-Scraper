import pgeocode
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def locationer(postal_code, iso_code="us"):
    try:
        nomi = pgeocode.Nominatim(iso_code)
        query = nomi.query_postal_code(postal_code)
    except Exception as e:
        raise ValueError(
            f"Could not geocode postal_code={postal_code}, iso_code={iso_code}: {e}"
        ) from e

    lat = query.get("latitude")
    lon = query.get("longitude")

    ne_lat, sw_lat = round(lat + 0.14, 7), round(lat - 0.14, 7)
    ne_lon, sw_lon = round(lon + 0.14, 7), round(lon - 0.14, 7)

    # logger.info(f"The latitude is {lat} and the longitude is {lon} for the city {city}")
    # logger.info(f"The northeast bound is at {ne_lat}, {ne_lon} and the southwest bound is at {sw_lat}, {sw_lon}")

    return ne_lat, sw_lat, ne_lon, sw_lon
