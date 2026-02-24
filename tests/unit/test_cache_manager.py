"""
Unit tests for utils/cache_manager.py
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


class TestCacheManager:
    """Tests for CacheManager class."""

    @pytest.fixture
    def cache_manager(self, tmp_cache_dir):
        """Create a CacheManager with a temporary directory."""
        with patch("utils.cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_caching": True}}

            from utils.cache_manager import CacheManager

            return CacheManager(
                cache_dir=str(tmp_cache_dir), ttl_hours=24, enable_cache=True
            )

    def test_generate_cache_key_consistent(self, cache_manager):
        """Test that same inputs produce same cache key."""
        listing_id = "12345"
        prompt = "Analyze these reviews"
        reviews_hash = "abc123"

        key1 = cache_manager._generate_cache_key(listing_id, prompt, reviews_hash)
        key2 = cache_manager._generate_cache_key(listing_id, prompt, reviews_hash)

        assert key1 == key2

    def test_generate_cache_key_different_inputs(self, cache_manager):
        """Test that different inputs produce different cache keys."""
        reviews_hash = "abc123"

        key1 = cache_manager._generate_cache_key("12345", "prompt1", reviews_hash)
        key2 = cache_manager._generate_cache_key("12345", "prompt2", reviews_hash)
        key3 = cache_manager._generate_cache_key("67890", "prompt1", reviews_hash)

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_generate_reviews_hash_consistent(self, cache_manager):
        """Test that same reviews produce same hash."""
        reviews = ["Great place!", "Loved it!", "Will return!"]

        hash1 = cache_manager._generate_reviews_hash(reviews)
        hash2 = cache_manager._generate_reviews_hash(reviews)

        assert hash1 == hash2

    def test_generate_reviews_hash_order_independent(self, cache_manager):
        """Test that reviews hash is order-independent (sorted)."""
        reviews1 = ["A review", "B review", "C review"]
        reviews2 = ["C review", "A review", "B review"]

        hash1 = cache_manager._generate_reviews_hash(reviews1)
        hash2 = cache_manager._generate_reviews_hash(reviews2)

        assert hash1 == hash2

    def test_is_cache_valid_recent_cache(self, cache_manager):
        """Test that recent cache is considered valid."""
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": "Test summary",
        }

        result = cache_manager._is_cache_valid(cache_data)

        assert result is True

    def test_is_cache_valid_expired_cache(self, cache_manager):
        """Test that expired cache is considered invalid."""
        old_time = datetime.now() - timedelta(hours=48)
        cache_data = {"timestamp": old_time.isoformat(), "summary": "Old summary"}

        # CacheManager has ttl_hours=24 by default
        result = cache_manager._is_cache_valid(cache_data)

        assert result is False

    def test_is_cache_valid_missing_timestamp(self, cache_manager):
        """Test that cache without timestamp is invalid."""
        cache_data = {"summary": "No timestamp summary"}

        result = cache_manager._is_cache_valid(cache_data)

        assert result is False

    def test_cache_summary_creates_file(self, cache_manager, tmp_cache_dir):
        """Test that cache_summary creates a cache file."""
        listing_id = "test123"
        prompt = "Test prompt"
        reviews = ["Review 1", "Review 2"]
        summary = "This is a test summary"

        result = cache_manager.cache_summary(listing_id, prompt, reviews, summary)

        assert result is True

        # Verify file was created
        cache_files = list(tmp_cache_dir.glob("*.json"))
        assert len(cache_files) == 1

    def test_cache_summary_content(self, cache_manager, tmp_cache_dir):
        """Test that cached content is correct."""
        listing_id = "test123"
        prompt = "Test prompt"
        reviews = ["Review 1", "Review 2"]
        summary = "This is a test summary"

        cache_manager.cache_summary(listing_id, prompt, reviews, summary)

        cache_files = list(tmp_cache_dir.glob("*.json"))
        with open(cache_files[0]) as f:
            cached_data = json.load(f)

        assert cached_data["listing_id"] == listing_id
        assert cached_data["summary"] == summary
        assert cached_data["reviews_count"] == 2
        assert "timestamp" in cached_data

    def test_get_cached_summary_cache_hit(self, cache_manager, tmp_cache_dir):
        """Test retrieving an existing cached summary."""
        listing_id = "test123"
        prompt = "Test prompt"
        reviews = ["Review 1", "Review 2"]
        summary = "Cached summary content"

        # First cache the summary
        cache_manager.cache_summary(listing_id, prompt, reviews, summary)

        # Then retrieve it
        result = cache_manager.get_cached_summary(listing_id, prompt, reviews)

        assert result == summary

    def test_get_cached_summary_cache_miss(self, cache_manager):
        """Test that cache miss returns None."""
        result = cache_manager.get_cached_summary(
            "nonexistent", "some prompt", ["some reviews"]
        )

        assert result is None

    def test_cache_disabled_returns_false(self, tmp_cache_dir):
        """Test that caching when disabled returns False."""
        with patch("utils.cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_caching": False}}

            from utils.cache_manager import CacheManager

            manager = CacheManager(cache_dir=str(tmp_cache_dir), enable_cache=False)

            result = manager.cache_summary("123", "prompt", ["review"], "summary")

            assert result is False

    def test_cache_disabled_get_returns_none(self, tmp_cache_dir):
        """Test that get_cached_summary when disabled returns None."""
        with patch("utils.cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"enable_caching": False}}

            from utils.cache_manager import CacheManager

            manager = CacheManager(cache_dir=str(tmp_cache_dir), enable_cache=False)

            result = manager.get_cached_summary("123", "prompt", ["review"])

            assert result is None

    def test_cache_summary_empty_summary(self, cache_manager):
        """Test that empty summary is not cached."""
        result = cache_manager.cache_summary("123", "prompt", ["review"], "")

        assert result is False

    def test_get_cache_stats_with_cached_files(self, cache_manager, tmp_cache_dir):
        """Test get_cache_stats returns correct statistics."""
        # Create some cache files
        cache_manager.cache_summary("listing1", "prompt", ["r1"], "summary1")
        cache_manager.cache_summary("listing2", "prompt", ["r2"], "summary2")

        stats = cache_manager.get_cache_stats()

        assert stats["enabled"] is True
        assert stats["total_cached"] == 2
        assert stats["valid_cache"] == 2
        assert stats["expired_cache"] == 0

    def test_get_cache_stats_empty_cache(self, cache_manager):
        """Test get_cache_stats with no cached files."""
        stats = cache_manager.get_cache_stats()

        assert stats["enabled"] is True
        assert stats["total_cached"] == 0

    def test_get_cache_stats_disabled(self, tmp_cache_dir):
        """Test get_cache_stats when caching is disabled."""
        with patch("utils.cache_manager.load_json_file") as mock_load:
            mock_load.return_value = {}

            from utils.cache_manager import CacheManager

            manager = CacheManager(cache_dir=str(tmp_cache_dir), enable_cache=False)

            stats = manager.get_cache_stats()

            assert stats["enabled"] is False
            assert stats["total_cached"] == 0

    def test_clear_all_cache(self, cache_manager, tmp_cache_dir):
        """Test clearing all cache files."""
        # Create cache files
        cache_manager.cache_summary("listing1", "prompt", ["r1"], "summary1")
        cache_manager.cache_summary("listing2", "prompt", ["r2"], "summary2")

        # Verify files exist
        assert cache_manager.get_cache_stats()["total_cached"] == 2

        # Clear all
        removed = cache_manager.clear_all_cache()

        assert removed == 2
        assert cache_manager.get_cache_stats()["total_cached"] == 0

    def test_clear_expired_cache(self, cache_manager, tmp_cache_dir):
        """Test clearing only expired cache files."""
        # Create a valid cache file
        cache_manager.cache_summary("valid", "prompt", ["r"], "summary")

        # Create an expired cache file manually
        expired_data = {
            "listing_id": "expired",
            "summary": "old summary",
            "timestamp": (datetime.now() - timedelta(hours=200)).isoformat(),
            "reviews_count": 1,
            "prompt_preview": "prompt",
            "cache_key": "expired_key",
        }
        expired_file = tmp_cache_dir / "expired.json"
        with open(expired_file, "w") as f:
            json.dump(expired_data, f)

        # Clear expired only
        removed = cache_manager.clear_expired_cache()

        assert removed == 1
        # Valid cache should remain
        stats = cache_manager.get_cache_stats()
        assert stats["valid_cache"] == 1
