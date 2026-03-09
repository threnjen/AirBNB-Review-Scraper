"""Geo-spatial utility functions for distance calculations."""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_MILES = 3958.8


def manhattan_surface_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Return the Manhattan (L1) surface distance in miles between two points.

    Computes the sum of two great-circle legs:
      1. East/west leg — hold latitude at lat1, move from lon1 to lon2
      2. North/south leg — hold longitude at lon2, move from lat1 to lat2

    This gives the "travel along x then along y" distance on the Earth's
    surface, which is always >= the straight-line haversine distance.
    """
    # East/west leg: same latitude (lat1), different longitudes
    ew_distance = _haversine(lat1, lon1, lat1, lon2)
    # North/south leg: same longitude (lon2), different latitudes
    ns_distance = _haversine(lat1, lon2, lat2, lon2)
    return ew_distance + ns_distance


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two points using haversine formula."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(a))
