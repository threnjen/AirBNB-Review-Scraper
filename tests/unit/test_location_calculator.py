"""
Unit tests for scraper/location_calculator.py
"""

import math
from unittest.mock import MagicMock, patch

import pytest


class TestBoundingBoxFromCenter:
    """Tests for bounding_box_from_center function."""

    def test_returns_four_bounds(self):
        """Should return (ne_lat, sw_lat, ne_lon, sw_lon)."""
        from scraper.location_calculator import bounding_box_from_center

        result = bounding_box_from_center(45.5155, -122.6789, 20.0)
        assert len(result) == 4

    def test_ne_lat_greater_than_sw_lat(self):
        """NE latitude must be greater than SW latitude."""
        from scraper.location_calculator import bounding_box_from_center

        ne_lat, sw_lat, ne_lon, sw_lon = bounding_box_from_center(
            45.5155, -122.6789, 20.0
        )
        assert ne_lat > sw_lat

    def test_ne_lon_greater_than_sw_lon(self):
        """NE longitude must be greater than SW longitude."""
        from scraper.location_calculator import bounding_box_from_center

        ne_lat, sw_lat, ne_lon, sw_lon = bounding_box_from_center(
            45.5155, -122.6789, 20.0
        )
        assert ne_lon > sw_lon

    def test_center_is_midpoint(self):
        """Center lat/lon should be the midpoint of the returned bounds."""
        from scraper.location_calculator import bounding_box_from_center

        lat, lon, radius = 45.5155, -122.6789, 25.0
        ne_lat, sw_lat, ne_lon, sw_lon = bounding_box_from_center(lat, lon, radius)

        assert (ne_lat + sw_lat) / 2 == pytest.approx(lat, abs=1e-6)
        assert (ne_lon + sw_lon) / 2 == pytest.approx(lon, abs=1e-6)

    def test_lat_offset_uses_69_miles_per_degree(self):
        """1 degree latitude == 69.0 miles, so offset = radius / 69.0."""
        from scraper.location_calculator import bounding_box_from_center

        radius = 20.0
        lat, lon = 45.5155, -122.6789
        ne_lat, sw_lat, ne_lon, sw_lon = bounding_box_from_center(lat, lon, radius)

        expected_lat_offset = radius / 69.0
        assert ne_lat == pytest.approx(lat + expected_lat_offset, abs=1e-6)
        assert sw_lat == pytest.approx(lat - expected_lat_offset, abs=1e-6)

    def test_lon_offset_accounts_for_latitude(self):
        """Longitude degree width narrows at higher latitudes."""
        from scraper.location_calculator import bounding_box_from_center

        radius = 20.0
        lat, lon = 45.5155, -122.6789
        ne_lat, sw_lat, ne_lon, sw_lon = bounding_box_from_center(lat, lon, radius)

        expected_lon_offset = radius / (69.0 * math.cos(math.radians(lat)))
        assert ne_lon == pytest.approx(lon + expected_lon_offset, abs=1e-6)
        assert sw_lon == pytest.approx(lon - expected_lon_offset, abs=1e-6)

    def test_larger_radius_gives_larger_box(self):
        """A larger radius should produce a larger bounding box."""
        from scraper.location_calculator import bounding_box_from_center

        lat, lon = 45.5155, -122.6789
        ne_lat_small, sw_lat_small, ne_lon_small, sw_lon_small = (
            bounding_box_from_center(lat, lon, 10.0)
        )
        ne_lat_large, sw_lat_large, ne_lon_large, sw_lon_large = (
            bounding_box_from_center(lat, lon, 50.0)
        )

        assert (ne_lat_large - sw_lat_large) > (ne_lat_small - sw_lat_small)
        assert (ne_lon_large - sw_lon_large) > (ne_lon_small - sw_lon_small)

    def test_equator_lon_offset_equals_lat_offset(self):
        """At the equator cos(0) == 1, so lat and lon offsets are equal."""
        from scraper.location_calculator import bounding_box_from_center

        radius = 30.0
        ne_lat, sw_lat, ne_lon, sw_lon = bounding_box_from_center(0.0, 0.0, radius)

        lat_half = ne_lat - 0.0
        lon_half = ne_lon - 0.0
        assert lat_half == pytest.approx(lon_half, abs=1e-6)


class TestLocationer:
    """Tests for locationer function."""

    def test_locationer_valid_postal_code(self, mock_pgeocode):
        """Test locationer with valid US postal code."""
        from scraper.location_calculator import locationer

        result = locationer("97224", "us")

        assert result is not None
        ne_lat, sw_lat, ne_lon, sw_lon = result

        # Verify bounds are calculated correctly (±0.14 from center)
        assert ne_lat == round(45.5155 + 0.14, 7)
        assert sw_lat == round(45.5155 - 0.14, 7)
        assert ne_lon == round(-122.6789 + 0.14, 7)
        assert sw_lon == round(-122.6789 - 0.14, 7)

    def test_locationer_default_iso_code(self, mock_pgeocode):
        """Test locationer uses 'us' as default ISO code."""
        from scraper.location_calculator import locationer

        result = locationer("97224")

        mock_pgeocode.Nominatim.assert_called_with("us")
        assert result is not None

    def test_locationer_different_iso_code(self):
        """Test locationer with different ISO code."""
        with patch("scraper.location_calculator.pgeocode") as mock_pg:
            mock_nomi = MagicMock()
            mock_pg.Nominatim.return_value = mock_nomi

            mock_query_result = MagicMock()
            mock_query_result.get = lambda key: {
                "latitude": 51.5074,
                "longitude": -0.1278,
                "place_name": "London",
            }.get(key)
            mock_nomi.query_postal_code.return_value = mock_query_result

            from scraper.location_calculator import locationer

            result = locationer("SW1A", "gb")

            mock_pg.Nominatim.assert_called_with("gb")
            assert result is not None

    def test_locationer_invalid_iso_code(self):
        """Test locationer with invalid ISO code raises ValueError."""
        with patch("scraper.location_calculator.pgeocode") as mock_pg:
            mock_pg.Nominatim.side_effect = Exception("xyz is not a known country code")

            from scraper.location_calculator import locationer

            with pytest.raises(ValueError, match="Could not geocode"):
                locationer("12345", "xyz")

    def test_locationer_general_exception(self):
        """Test locationer raises ValueError on general exceptions."""
        with patch("scraper.location_calculator.pgeocode") as mock_pg:
            mock_pg.Nominatim.side_effect = Exception("Network error")

            from scraper.location_calculator import locationer

            with pytest.raises(ValueError, match="Could not geocode"):
                locationer("12345", "us")

    def test_locationer_bounds_precision(self, mock_pgeocode):
        """Test that bounds have correct decimal precision (7 places)."""
        from scraper.location_calculator import locationer

        result = locationer("97224", "us")

        ne_lat, sw_lat, ne_lon, sw_lon = result

        # Check all values have at most 7 decimal places
        for val in [ne_lat, sw_lat, ne_lon, sw_lon]:
            decimal_str = str(val).split(".")[-1] if "." in str(val) else ""
            assert len(decimal_str) <= 7
