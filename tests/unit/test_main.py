"""Unit tests for the main.py AirBnbReviewAggregator class."""

from unittest.mock import patch


class TestAirBnbReviewAggregator:
    """Tests for AirBnbReviewAggregator config properties."""

    def test_zipcodes_returns_list_from_config(self):
        """zipcodes property returns the zipcodes list from config."""
        mock_config = {
            "zipcodes": ["97011", "97067"],
            "dest_lat": 45.3131819,
            "dest_long": -121.8263023,
        }
        with patch("main.load_config", return_value=mock_config):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator()
            assert agg.zipcodes == ["97011", "97067"]

    def test_zipcodes_returns_empty_list_when_missing(self):
        """zipcodes property returns empty list when key is absent."""
        mock_config = {}
        with patch("main.load_config", return_value=mock_config):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator()
            assert agg.zipcodes == []

    def test_config_contains_dest_lat_long(self):
        """load_config returns dest_lat and dest_long as floats."""
        mock_config = {
            "zipcodes": ["97067"],
            "dest_lat": 45.3131819,
            "dest_long": -121.8263023,
        }
        with patch("main.load_config", return_value=mock_config):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator()
            assert isinstance(agg.config["dest_lat"], float)
            assert isinstance(agg.config["dest_long"], float)
