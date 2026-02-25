"""Tests for get_area_search_results() reading from comp_set_{zipcode}.json."""

import json
import os
from unittest.mock import MagicMock, patch, mock_open

import pytest


class TestGetAreaSearchResultsFromCompSet:
    """get_area_search_results should read comp_set file when it exists."""

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
            agg.pipeline_cache.record_output.return_value = True
            agg.pipeline_cache.record_stage_complete.return_value = True
        return agg

    def test_reads_comp_set_file(self, aggregator):
        """When comp_set_{zipcode}.json exists, listing IDs are extracted."""
        comp_set_data = {
            "listing_1": {"ADR": 100.0},
            "listing_2": {"ADR": 200.0},
        }

        with patch("os.path.isfile", return_value=True):
            with patch(
                "builtins.open",
                mock_open(read_data=json.dumps(comp_set_data)),
            ):
                result = aggregator.get_area_search_results()

        room_ids = {r["room_id"] for r in result}
        assert room_ids == {"listing_1", "listing_2"}

    def test_falls_back_to_search_results(self, aggregator):
        """When no comp_set file exists, falls back to search_results file."""
        search_data = [{"room_id": "abc"}, {"room_id": "def"}]

        def fake_isfile(p):
            if "comp_set_97067" in str(p):
                return False
            if "search_results_97067" in str(p):
                return True
            return False

        with patch("os.path.isfile", side_effect=fake_isfile):
            with patch(
                "builtins.open",
                mock_open(read_data=json.dumps(search_data)),
            ):
                result = aggregator.get_area_search_results()

        assert len(result) == 2
        assert result[0]["room_id"] == "abc"
