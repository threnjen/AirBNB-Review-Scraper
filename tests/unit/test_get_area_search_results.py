"""Tests for load_search_results() in steps/__init__.py."""

import json
from unittest.mock import MagicMock, patch, mock_open

import pytest


class TestGetAreaSearchResults:
    """load_search_results should load or run AirBnB search."""

    @pytest.fixture
    def config(self):
        return {
            "search_zone_name": "test_zone",
            "start_lat": 45.5155,
            "start_long": -122.6789,
            "search_radius_miles": 20.0,
        }

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

    def test_runs_search_when_cache_miss(self, config, pipeline_cache):
        """When cache says run, airbnb_searcher is called with zone params."""
        from steps import load_search_results

        pipeline_cache.should_run_stage.return_value = "run"

        with patch("steps.airbnb_searcher") as mock_searcher:
            mock_searcher.return_value = [{"room_id": "xyz"}]
            result = load_search_results(config, pipeline_cache)

        mock_searcher.assert_called_once_with(
            start_lat=45.5155,
            start_long=-122.6789,
            search_radius_miles=20.0,
            search_zone_name="test_zone",
        )
        assert result == [{"room_id": "xyz"}]

    def test_uses_zone_name_in_output_path(self, config, pipeline_cache):
        """Output file path uses search_zone_name, not zipcode."""
        from steps import load_search_results

        search_data = [{"room_id": "abc"}]
        opened_paths = []

        original_open = open

        def tracking_open(path, *args, **kwargs):
            opened_paths.append(str(path))
            return mock_open(read_data=json.dumps(search_data))()

        with patch("builtins.open", side_effect=tracking_open):
            load_search_results(config, pipeline_cache)

        assert any("test_zone" in p for p in opened_paths)
        assert not any("97067" in p for p in opened_paths)
