"""Tests for get_area_search_results() in main.py."""

import json
import os
from unittest.mock import MagicMock, patch, mock_open

import pytest


class TestGetAreaSearchResults:
    """get_area_search_results should load or run AirBnB search."""

    @pytest.fixture
    def aggregator(self):
        """Create an AirBnbReviewAggregator without loading real config."""
        with patch("main.AirBnbReviewAggregator.load_configs"):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator.__new__(AirBnbReviewAggregator)
            agg.config = {}
            agg.zipcode = "97067"
            agg.iso_code = "us"
            agg.num_listings_to_search = 30000
            agg.pipeline_cache = MagicMock()
            agg.pipeline_cache.is_file_fresh.return_value = False
            agg.pipeline_cache.should_run_stage.return_value = "skip"
            agg.pipeline_cache.force_refresh_flags = {}
        return agg

    def test_loads_cached_search_results(self, aggregator):
        """When search results file exists and stage is fresh, load from it."""
        search_data = [{"room_id": "abc"}, {"room_id": "def"}]

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(search_data)),
        ):
            result = aggregator.get_area_search_results()

        assert len(result) == 2
        assert result[0]["room_id"] == "abc"
