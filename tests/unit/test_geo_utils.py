"""Tests for manhattan_surface_distance in utils/geo_utils.py."""

import math

import pytest

from utils.geo_utils import manhattan_surface_distance


class TestManhattanSurfaceDistance:
    """Manhattan (L1) surface distance: east/west leg + north/south leg."""

    def test_same_point_returns_zero(self):
        """Distance from a point to itself is 0."""
        assert manhattan_surface_distance(45.0, -121.0, 45.0, -121.0) == 0.0

    def test_purely_north_south_one_degree_at_equator(self):
        """1° latitude at the equator ≈ 69.1 miles."""
        dist = manhattan_surface_distance(0.0, 0.0, 1.0, 0.0)
        assert dist == pytest.approx(69.1, abs=0.2)

    def test_purely_east_west_one_degree_at_equator(self):
        """1° longitude at the equator ≈ 69.1 miles (cos(0)=1)."""
        dist = manhattan_surface_distance(0.0, 0.0, 0.0, 1.0)
        assert dist == pytest.approx(69.1, abs=0.2)

    def test_purely_east_west_shrinks_at_higher_latitude(self):
        """1° longitude at 60°N ≈ 34.6 miles (cos(60°)=0.5)."""
        dist = manhattan_surface_distance(60.0, 0.0, 60.0, 1.0)
        assert dist == pytest.approx(34.7, abs=0.5)

    def test_manhattan_geq_haversine(self):
        """Manhattan distance should be >= straight-line haversine for diagonal movement."""
        # Mt Hood area: two points that differ in both lat and lon
        lat1, lon1 = 45.3735, -121.6960
        lat2, lon2 = 45.3132, -121.8263
        manhattan = manhattan_surface_distance(lat1, lon1, lat2, lon2)
        # Haversine (straight-line) for comparison
        R = 3958.8  # Earth radius in miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        haversine = 2 * R * math.asin(math.sqrt(a))
        assert manhattan >= haversine

    def test_negative_longitudes(self):
        """Works correctly with negative longitudes (western hemisphere)."""
        dist = manhattan_surface_distance(45.0, -122.0, 45.0, -121.0)
        assert dist > 0
        # 1° longitude at 45°N: cos(45°) * 69.1 ≈ 48.9 miles
        assert dist == pytest.approx(48.9, abs=0.5)

    def test_crossing_prime_meridian(self):
        """Handles crossing the prime meridian (negative to positive longitude)."""
        dist = manhattan_surface_distance(51.5, -0.5, 51.5, 0.5)
        assert dist > 0
        # 1° longitude at 51.5°N: cos(51.5°) * 69.1 ≈ 43.0 miles
        assert dist == pytest.approx(43.0, abs=0.5)

    def test_approximately_symmetric(self):
        """A→B and B→A differ only slightly (E/W leg depends on latitude)."""
        d1 = manhattan_surface_distance(45.0, -121.0, 46.0, -122.0)
        d2 = manhattan_surface_distance(46.0, -122.0, 45.0, -121.0)
        assert d1 == pytest.approx(d2, rel=0.01)
