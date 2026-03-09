"""Unit tests for the main.py AirBnbReviewAggregator class."""

from unittest.mock import patch

BASE_CONFIG = {
    "search_zone_name": "mt_hood_corridor",
    "start_lat": 45.33,
    "start_long": -121.87,
    "search_radius_miles": 25.0,
    "dest_lat": 45.3131819,
    "dest_long": -121.8263023,
}


class TestAirBnbReviewAggregator:
    """Tests for AirBnbReviewAggregator config properties."""

    def test_search_zone_name_returns_from_config(self):
        """search_zone_name property returns value from config."""
        with patch("main.load_config", return_value=BASE_CONFIG):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator()
            assert agg.search_zone_name == "mt_hood_corridor"

    def test_search_zone_name_default_is_empty_string(self):
        """search_zone_name returns empty string when key is absent."""
        with patch("main.load_config", return_value={}):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator()
            assert agg.search_zone_name == ""

    def test_config_contains_dest_lat_long(self):
        """config has dest_lat and dest_long as floats."""
        with patch("main.load_config", return_value=BASE_CONFIG):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator()
            assert isinstance(agg.config["dest_lat"], float)
            assert isinstance(agg.config["dest_long"], float)

    def test_config_contains_start_lat_long(self):
        """config has start_lat and start_long as floats."""
        with patch("main.load_config", return_value=BASE_CONFIG):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator()
            assert isinstance(agg.config["start_lat"], float)
            assert isinstance(agg.config["start_long"], float)

    def test_config_contains_search_radius(self):
        """config has search_radius_miles as a positive number."""
        with patch("main.load_config", return_value=BASE_CONFIG):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator()
            assert agg.config["search_radius_miles"] > 0
