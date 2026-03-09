"""
Unit tests for scraper/airbnb_searcher.py
"""

import json
from unittest.mock import MagicMock, patch, call

import pytest


class TestFilterListingsByRadius:
    """Tests for the post-search Euclidean radius filter in airbnb_searcher."""

    def _make_listing(self, lat, lon):
        """Build a minimal search-result listing with pyairbnb's 'longitud' typo."""
        return {
            "room_id": f"{lat}_{lon}",
            "coordinates": {"latitude": lat, "longitud": lon},
        }

    def test_listing_at_center_is_kept(self):
        """A listing located exactly at the search center is always within radius."""
        from scraper.airbnb_searcher import filter_listings_by_radius

        listing = self._make_listing(45.5155, -122.6789)
        result = filter_listings_by_radius([listing], 45.5155, -122.6789, 20.0)
        assert listing in result

    def test_listing_far_outside_radius_is_removed(self):
        """A listing hundreds of miles away should be filtered out."""
        from scraper.airbnb_searcher import filter_listings_by_radius

        # Seattle (~170 miles from Portland)
        far_listing = self._make_listing(47.6062, -122.3321)
        result = filter_listings_by_radius([far_listing], 45.5155, -122.6789, 20.0)
        assert far_listing not in result

    def test_listing_just_within_radius_is_kept(self):
        """A listing just inside the radius boundary should be kept."""
        from scraper.airbnb_searcher import filter_listings_by_radius

        # ~10 miles north — within a 20-mile radius
        # 10 miles / 69 miles-per-degree ≈ 0.145 degrees of latitude
        near_listing = self._make_listing(45.5155 + 0.13, -122.6789)
        result = filter_listings_by_radius([near_listing], 45.5155, -122.6789, 20.0)
        assert near_listing in result

    def test_listing_just_outside_radius_is_removed(self):
        """A listing just beyond the radius should be excluded."""
        from scraper.airbnb_searcher import filter_listings_by_radius

        # ~25 miles north — outside a 20-mile radius
        # 25 miles / 69 ≈ 0.362 degrees
        far_listing = self._make_listing(45.5155 + 0.37, -122.6789)
        result = filter_listings_by_radius([far_listing], 45.5155, -122.6789, 20.0)
        assert far_listing not in result

    def test_empty_list_returns_empty(self):
        """Filter on an empty list returns an empty list."""
        from scraper.airbnb_searcher import filter_listings_by_radius

        result = filter_listings_by_radius([], 45.5155, -122.6789, 20.0)
        assert result == []

    def test_all_pass_filter_when_radius_is_large(self):
        """With a huge radius every listing should be kept."""
        from scraper.airbnb_searcher import filter_listings_by_radius

        listings = [
            self._make_listing(45.5155, -122.6789),
            self._make_listing(47.6062, -122.3321),
            self._make_listing(40.7128, -74.0060),
        ]
        result = filter_listings_by_radius(listings, 45.5155, -122.6789, 10000.0)
        assert len(result) == 3

    def test_handles_missing_coordinates_gracefully(self):
        """Listings missing coordinates should be excluded, not raise."""
        from scraper.airbnb_searcher import filter_listings_by_radius

        bad_listing = {"room_id": "no_coords"}
        result = filter_listings_by_radius([bad_listing], 45.5155, -122.6789, 20.0)
        assert bad_listing not in result

    def test_uses_longitud_typo_key(self):
        """Filter reads 'longitud' (pyairbnb typo), not 'longitude'."""
        from scraper.airbnb_searcher import filter_listings_by_radius

        # Listing with correct 'longitude' key but missing 'longitud' — should be dropped
        bad_key_listing = {
            "room_id": "wrong_key",
            "coordinates": {"latitude": 45.5155, "longitude": -122.6789},
        }
        result = filter_listings_by_radius([bad_key_listing], 45.5155, -122.6789, 20.0)
        assert bad_key_listing not in result


class TestAirbnbSearcher:
    """Tests for the refactored airbnb_searcher function."""

    def test_saves_results_with_zone_name(self, tmp_path):
        """Output file is named search_results_{search_zone_name}.json."""
        from scraper.airbnb_searcher import airbnb_searcher

        fake_result = [
            {"room_id": "1", "coordinates": {"latitude": 45.52, "longitud": -122.68}}
        ]

        with (
            patch("scraper.airbnb_searcher.pyairbnb") as mock_pyairbnb,
            patch("scraper.airbnb_searcher.os.makedirs"),
            patch("scraper.airbnb_searcher.time.sleep"),
            patch(
                "scraper.airbnb_searcher.bounding_box_from_center",
                return_value=(45.8, 45.2, -122.3, -123.0),
            ),
        ):
            mock_pyairbnb.search_all.return_value = fake_result

            opened_paths = []
            written_data = []

            import builtins

            original_open = builtins.open

            def fake_open(path, mode="r", *args, **kwargs):
                if "w" in str(mode):
                    opened_paths.append(str(path))
                    m = MagicMock()
                    m.__enter__ = MagicMock(return_value=m)
                    m.__exit__ = MagicMock(return_value=False)
                    m.write = lambda d: written_data.append(d)
                    return m
                return original_open(path, mode, *args, **kwargs)

            with patch("builtins.open", side_effect=fake_open):
                airbnb_searcher(
                    start_lat=45.5155,
                    start_long=-122.6789,
                    search_radius_miles=20.0,
                    search_zone_name="mt_hood",
                )

        assert any("search_results_mt_hood.json" in p for p in opened_paths)

    def test_accepts_new_signature(self):
        """airbnb_searcher must accept start_lat, start_long, search_radius_miles, search_zone_name."""
        from scraper.airbnb_searcher import airbnb_searcher
        import inspect

        sig = inspect.signature(airbnb_searcher)
        params = list(sig.parameters.keys())
        assert "start_lat" in params
        assert "start_long" in params
        assert "search_radius_miles" in params
        assert "search_zone_name" in params
        assert "zipcode" not in params

    def test_calls_bounding_box_from_center(self):
        """airbnb_searcher delegates bounding box calculation to bounding_box_from_center."""
        from scraper.airbnb_searcher import airbnb_searcher

        with (
            patch(
                "scraper.airbnb_searcher.bounding_box_from_center",
                return_value=(45.8, 45.2, -122.3, -123.0),
            ) as mock_bbox,
            patch("scraper.airbnb_searcher.pyairbnb") as mock_pyairbnb,
            patch("scraper.airbnb_searcher.os.makedirs"),
            patch("builtins.open", MagicMock()),
            patch("scraper.airbnb_searcher.time.sleep"),
        ):
            mock_pyairbnb.search_all.return_value = []

            airbnb_searcher(
                start_lat=45.5155,
                start_long=-122.6789,
                search_radius_miles=20.0,
                search_zone_name="test_zone",
            )

        mock_bbox.assert_called_once_with(45.5155, -122.6789, 20.0)
