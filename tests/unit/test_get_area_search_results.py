"""Tests for load_search_results() in steps/__init__.py."""

import json
from unittest.mock import MagicMock, patch, mock_open

import pytest


class TestGetAreaSearchResults:
    """load_search_results should load or run AirBnB search."""

    @pytest.fixture
    def config(self):
        return {"zipcode": "97067", "iso_code": "us"}

    @pytest.fixture
    def pipeline_cache(self):
        cache = MagicMock()
        cache.should_run_stage.return_value = "skip"
        cache.force_refresh_flags = {}
        return cache

    def test_loads_cached_search_results(self, config, pipeline_cache):
        """When search results file exists and stage is fresh, load from it."""
        from steps import load_search_results

        search_data = [{"room_id": "abc"}, {"room_id": "def"}]

        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(search_data)),
        ):
            result = load_search_results(config, pipeline_cache)

        assert len(result) == 2
        assert result[0]["room_id"] == "abc"
