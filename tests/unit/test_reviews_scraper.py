"""
Unit tests for scraper/reviews_scraper.py — Airbnb review scraping with retry.

All tests use a temporary working directory (via ``monkeypatch.chdir``) so that
the scraper's relative output paths never touch real project outputs.
"""

import json
import os
from unittest.mock import call, patch

import pytest

from scraper.reviews_scraper import (
    FAILURE_THRESHOLD,
    PASS_RETRY_WAIT_SECONDS,
    scrape_reviews,
)

ZIPCODE = "97067"
LISTING_ID = "123456789"
SEARCH_RESULTS = [{"room_id": LISTING_ID}]
OUTPUT_DIR = "outputs/04_reviews_scrape"
OUTPUT_PATH = f"{OUTPUT_DIR}/reviews_{ZIPCODE}_{LISTING_ID}.json"


def _make_search_results(n: int) -> list[dict]:
    """Create n search result entries with sequential IDs."""
    return [{"room_id": str(i)} for i in range(1, n + 1)]


def _output_path_for(listing_id: str) -> str:
    return f"{OUTPUT_DIR}/reviews_{ZIPCODE}_{listing_id}.json"


@pytest.fixture(autouse=True)
def _use_tmp_workdir(tmp_path, monkeypatch):
    """Run every test inside a disposable temp directory.

    This prevents the scraper from reading or writing to the real
    ``outputs/04_reviews_scrape/`` directory in the project root.
    """
    monkeypatch.chdir(tmp_path)


class TestSkipEmptyReviews:
    """File should NOT be written when a listing has 0 reviews."""

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews", return_value=[])
    def test_no_file_written_for_zero_reviews(self, mock_get, mock_sleep):
        """When pyairbnb returns an empty list, no file is created."""
        scrape_reviews(ZIPCODE, SEARCH_RESULTS, num_listings=1)

        assert not os.path.exists(OUTPUT_PATH)

    @patch("scraper.reviews_scraper.time.sleep")
    @patch(
        "scraper.reviews_scraper.pyairbnb.get_reviews",
        return_value=[{"comments": "Great!", "rating": 5}],
    )
    def test_file_written_when_reviews_exist(self, mock_get, mock_sleep):
        """When pyairbnb returns reviews, the file is created."""
        scrape_reviews(ZIPCODE, SEARCH_RESULTS, num_listings=1)

        assert os.path.exists(OUTPUT_PATH)
        with open(OUTPUT_PATH) as f:
            data = json.load(f)
        assert LISTING_ID in data
        assert len(data[LISTING_ID]) == 1
        assert data[LISTING_ID][0]["review"] == "Great!"
        assert data[LISTING_ID][0]["rating"] == 5


class TestRetryOnFailure:
    """scrape_reviews retries up to 3 times per listing on transient errors."""

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_retries_up_to_max_then_continues(self, mock_get, mock_sleep):
        """After 3 consecutive failures the listing is skipped (no crash)."""
        mock_get.side_effect = Exception("curl: (23) Failure writing output")

        # Disable pass-level retry so we only test per-request retry.
        with patch("scraper.reviews_scraper.FAILURE_THRESHOLD", 1.0):
            scrape_reviews(ZIPCODE, SEARCH_RESULTS, num_listings=1)

        assert mock_get.call_count == 3
        assert not os.path.exists(OUTPUT_PATH)

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_succeeds_on_second_attempt(self, mock_get, mock_sleep):
        """If the first attempt fails but the second succeeds, reviews are saved."""
        mock_get.side_effect = [
            Exception("Temporary failure"),
            [{"comments": "Nice place", "rating": 4}],
        ]

        scrape_reviews(ZIPCODE, SEARCH_RESULTS, num_listings=1)

        assert mock_get.call_count == 2
        assert os.path.exists(OUTPUT_PATH)
        with open(OUTPUT_PATH) as f:
            data = json.load(f)
        assert len(data[LISTING_ID]) == 1

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_retry_uses_exponential_backoff(self, mock_get, mock_sleep):
        """Backoff delays increase between retry attempts."""
        # Use a single listing that always fails — check for backoff sleeps.
        # Limit passes by patching FAILURE_THRESHOLD to 1.0 (never retry pass).
        mock_get.side_effect = Exception("persistent error")

        with patch("scraper.reviews_scraper.FAILURE_THRESHOLD", 1.0):
            scrape_reviews(ZIPCODE, SEARCH_RESULTS, num_listings=1)

        # Collect the sleep calls made for retry backoff (2s, 4s).
        backoff_calls = [
            c for c in mock_sleep.call_args_list if c == call(2) or c == call(4)
        ]
        assert len(backoff_calls) == 2


class TestInterRequestDelay:
    """Delay between successful requests should be 3–6 seconds."""

    @patch("scraper.reviews_scraper.random.uniform", return_value=4.5)
    @patch("scraper.reviews_scraper.time.sleep")
    @patch(
        "scraper.reviews_scraper.pyairbnb.get_reviews",
        return_value=[{"comments": "Fine", "rating": 3}],
    )
    def test_sleep_range_is_3_to_6(self, mock_get, mock_sleep, mock_uniform):
        """random.uniform is called with (3, 6) for inter-request delay."""
        scrape_reviews(ZIPCODE, SEARCH_RESULTS, num_listings=1)

        mock_uniform.assert_called_with(3, 6)


class TestPassLevelRetry:
    """When >20% of listings fail, the entire pass is retried after a cooldown."""

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_pass_retried_when_failure_rate_exceeds_threshold(
        self, mock_get, mock_sleep
    ):
        """With 5 listings and 2 always failing (40% > 20%), a second pass runs."""
        results = _make_search_results(5)

        # Listings 1-3 succeed immediately; listings 4-5 always fail.
        def side_effect(room_url):
            listing_id = room_url.split("/")[-1]
            if listing_id in ("4", "5"):
                raise Exception("curl error")
            return [{"comments": f"Review for {listing_id}", "rating": 5}]

        mock_get.side_effect = side_effect

        # Allow only 1 extra pass by patching threshold to 1.0 after first retry.
        original_threshold = FAILURE_THRESHOLD
        call_count = {"passes": 0}
        original_sleep = mock_sleep.side_effect

        def counting_sleep(seconds):
            if seconds == PASS_RETRY_WAIT_SECONDS:
                call_count["passes"] += 1

        mock_sleep.side_effect = counting_sleep

        # Since listings 4 & 5 always fail, this will loop. Limit with max
        # pass checking: patch FAILURE_THRESHOLD to 1.0 after first cooldown.
        pass_waits = []

        def sleep_side_effect(seconds):
            if seconds == PASS_RETRY_WAIT_SECONDS:
                pass_waits.append(seconds)
                # After first pass retry, prevent infinite loop
                import scraper.reviews_scraper as mod

                mod.FAILURE_THRESHOLD = 1.0

        mock_sleep.side_effect = sleep_side_effect

        import scraper.reviews_scraper as mod

        original = mod.FAILURE_THRESHOLD
        try:
            scrape_reviews(ZIPCODE, results, num_listings=5)
        finally:
            mod.FAILURE_THRESHOLD = original

        # The cooldown sleep was called at least once
        assert len(pass_waits) >= 1

        # Listings 1-3 should have files
        for lid in ("1", "2", "3"):
            assert os.path.exists(_output_path_for(lid))

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_no_pass_retry_when_failure_rate_below_threshold(
        self, mock_get, mock_sleep
    ):
        """With 10 listings and only 1 failing (10% < 20%), no second pass runs."""
        results = _make_search_results(10)

        def side_effect(room_url):
            listing_id = room_url.split("/")[-1]
            if listing_id == "5":
                raise Exception("curl error")
            return [{"comments": f"Review for {listing_id}", "rating": 5}]

        mock_get.side_effect = side_effect

        scrape_reviews(ZIPCODE, results, num_listings=10)

        # No PASS_RETRY_WAIT_SECONDS sleep should have occurred
        cooldown_calls = [
            c for c in mock_sleep.call_args_list if c == call(PASS_RETRY_WAIT_SECONDS)
        ]
        assert len(cooldown_calls) == 0

        # 9 out of 10 should have files
        for lid in ("1", "2", "3", "4", "6", "7", "8", "9", "10"):
            assert os.path.exists(_output_path_for(lid))

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_pass_retry_resolves_transient_failures(self, mock_get, mock_sleep):
        """Listing fails on pass 1 but succeeds on pass 2 — file is written."""
        results = _make_search_results(3)
        attempt_tracker: dict[str, int] = {}

        def side_effect(room_url):
            listing_id = room_url.split("/")[-1]
            attempt_tracker.setdefault(listing_id, 0)
            attempt_tracker[listing_id] += 1

            # Listing 1 fails on first 3 attempts (exhausting per-request retries
            # in pass 1), then succeeds on pass 2.
            if listing_id == "1" and attempt_tracker[listing_id] <= 3:
                raise Exception("transient curl error")
            return [{"comments": f"Review for {listing_id}", "rating": 5}]

        mock_get.side_effect = side_effect

        scrape_reviews(ZIPCODE, results, num_listings=3)

        # All 3 listings should be resolved
        for lid in ("1", "2", "3"):
            assert os.path.exists(_output_path_for(lid))


class TestCacheSkip:
    """Listings with existing review files on disk are skipped."""

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_existing_file_is_skipped(self, mock_get, mock_sleep):
        """When review file already exists on disk, pyairbnb is not called."""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump({LISTING_ID: [{"review": "Old", "rating": 5}]}, f)

        scrape_reviews(ZIPCODE, SEARCH_RESULTS, num_listings=1)

        mock_get.assert_not_called()

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_mixed_cached_and_uncached(self, mock_get, mock_sleep):
        """With 3 listings and 1 already on disk, only 2 are scraped."""
        results = _make_search_results(3)

        # Create review file for listing "2" only
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(_output_path_for("2"), "w") as f:
            json.dump({"2": [{"review": "Old", "rating": 5}]}, f)

        mock_get.return_value = [{"comments": "Nice", "rating": 5}]

        scrape_reviews(ZIPCODE, results, num_listings=3)

        assert mock_get.call_count == 2


class TestProgressCounter:
    """Counter should report already-scraped and remaining, not total."""

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_initial_log_reports_already_scraped_and_remaining(
        self, mock_get, mock_sleep, caplog
    ):
        """Log should include total, already scraped, and remaining counts."""
        results = _make_search_results(5)

        # Create review files for listings 1 and 3
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        for lid in ("1", "3"):
            with open(_output_path_for(lid), "w") as f:
                json.dump({lid: [{"review": "Old", "rating": 5}]}, f)

        mock_get.return_value = [{"comments": "OK", "rating": 4}]

        import logging

        with caplog.at_level(logging.INFO, logger="scraper.reviews_scraper"):
            scrape_reviews(ZIPCODE, results, num_listings=5)

        log_text = caplog.text
        assert "5 listings in the area" in log_text
        assert "2 already scraped" in log_text
        assert "3 to scrape" in log_text

    @patch("scraper.reviews_scraper.time.sleep")
    @patch("scraper.reviews_scraper.pyairbnb.get_reviews")
    def test_counter_counts_out_of_remaining_not_total(
        self, mock_get, mock_sleep, caplog
    ):
        """'property X of Y' should use remaining count, not total."""
        results = _make_search_results(5)

        # Create review files for listings 1, 2, 3 — only 4 and 5 remain
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        for lid in ("1", "2", "3"):
            with open(_output_path_for(lid), "w") as f:
                json.dump({lid: [{"review": "Old", "rating": 5}]}, f)

        mock_get.return_value = [{"comments": "OK", "rating": 4}]

        import logging

        with caplog.at_level(logging.INFO, logger="scraper.reviews_scraper"):
            scrape_reviews(ZIPCODE, results, num_listings=5)

        log_text = caplog.text
        # Counter should be "property 1 of 2" and "property 2 of 2"
        assert "property 1 of 2" in log_text
        assert "property 2 of 2" in log_text
        # Should NOT show "of 5" in property counter
        assert "property 1 of 5" not in log_text
