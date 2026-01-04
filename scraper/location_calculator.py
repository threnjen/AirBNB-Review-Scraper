import pgeocode

postal_code = "97224"
iso_code = "us"


def locationer(postal_code, iso_code="us"):

    try:
        nomi = pgeocode.Nominatim(iso_code)
        query = nomi.query_postal_code(postal_code)
    except Exception as e:
        if "is not a known country code" in str(
            e
        ):  # Checks if the error is due to an unknown ISO code
            print(
                f"The code {iso_code} has no available data. Please select a different ISO code."
            )
        else:
            print(f"An error occurred: {e}")
        return

    lat = query.get("latitude")
    lon = query.get("longitude")
    query.get("place_name")

    ne_lat, sw_lat = round(lat + 0.14, 7), round(lat - 0.14, 7)
    ne_lon, sw_lon = round(lon + 0.14, 7), round(lon - 0.14, 7)

    # print(f"The latitude is {lat} and the longitude is {lon} for the city {city}")
    # print(f"The northeast bound is at {ne_lat}, {ne_lon} and the southwest bound is at {sw_lat}, {sw_lon}")

    return ne_lat, sw_lat, ne_lon, sw_lon


# locationer(postal_code = postal_code, iso_code = iso_code)
