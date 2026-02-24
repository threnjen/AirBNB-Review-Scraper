"""
Unit tests for scraper/location_calculator.py
"""

from unittest.mock import MagicMock, patch


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
        """Test locationer with invalid ISO code returns None."""
        with patch("scraper.location_calculator.pgeocode") as mock_pg:
            mock_pg.Nominatim.side_effect = Exception("xyz is not a known country code")

            from scraper.location_calculator import locationer

            result = locationer("12345", "xyz")

            assert result is None

    def test_locationer_general_exception(self):
        """Test locationer handles general exceptions gracefully."""
        with patch("scraper.location_calculator.pgeocode") as mock_pg:
            mock_pg.Nominatim.side_effect = Exception("Network error")

            from scraper.location_calculator import locationer

            result = locationer("12345", "us")

            assert result is None

    def test_locationer_bounds_precision(self, mock_pgeocode):
        """Test that bounds have correct decimal precision (7 places)."""
        from scraper.location_calculator import locationer

        result = locationer("97224", "us")

        ne_lat, sw_lat, ne_lon, sw_lon = result

        # Check all values have at most 7 decimal places
        for val in [ne_lat, sw_lat, ne_lon, sw_lon]:
            decimal_str = str(val).split(".")[-1] if "." in str(val) else ""
            assert len(decimal_str) <= 7
