import os
import json
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
from pydantic import BaseModel
from utils.tiny_file_handler import load_json_file, save_json_file
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class CacheManager(BaseModel):
    """
    File-based cache manager for OpenAI aggregation results.
    Uses listing_id + prompt_hash as keys to avoid re-processing identical requests.
    """

    cache_dir: str = "cache/summaries"
    ttl_hours: int = 24 * 7  # Cache valid for 7 days
    enable_cache: bool = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load configuration overrides if available
        try:
            config = load_json_file("config.json")
            openai_config = config.get("openai", {})
            self.enable_cache = openai_config.get("enable_caching", self.enable_cache)
        except Exception:
            pass

        # Create cache directory if it doesn't exist
        if self.enable_cache:
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

    def _generate_cache_key(
        self, listing_id: str, prompt: str, reviews_hash: str
    ) -> str:
        """Generate a unique cache key from listing_id, prompt, and reviews."""
        # Create a hash of the prompt to handle long prompts
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:12]

        # Combine components for cache key
        cache_key = f"{listing_id}_{prompt_hash}_{reviews_hash}"
        return cache_key

    def _generate_reviews_hash(self, reviews: list) -> str:
        """Generate a hash representing the review content."""
        # Sort reviews to ensure consistent hashing regardless of order
        sorted_reviews = sorted(reviews)
        reviews_str = "".join(sorted_reviews)
        return hashlib.md5(reviews_str.encode()).hexdigest()[:12]

    def _get_cache_file_path(self, cache_key: str) -> str:
        """Get the full file path for a cache key."""
        return os.path.join(self.cache_dir, f"{cache_key}.json")

    def _is_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
        """Check if cached data is still valid based on TTL."""
        if "timestamp" not in cache_data:
            return False

        cached_time = datetime.fromisoformat(cache_data["timestamp"])
        expiry_time = cached_time + timedelta(hours=self.ttl_hours)

        return datetime.now() < expiry_time

    def get_cached_summary(
        self, listing_id: str, prompt: str, reviews: list
    ) -> Optional[str]:
        """
        Retrieve cached summary if available and valid.
        Returns None if no valid cache exists.
        """
        if not self.enable_cache:
            return None

        try:
            reviews_hash = self._generate_reviews_hash(reviews)
            cache_key = self._generate_cache_key(listing_id, prompt, reviews_hash)
            cache_file = self._get_cache_file_path(cache_key)

            if not os.path.exists(cache_file):
                return None

            cache_data = load_json_file(cache_file)

            if not self._is_cache_valid(cache_data):
                # Remove expired cache
                os.remove(cache_file)
                return None

            logger.info(f"Cache hit for listing {listing_id}")
            return cache_data.get("summary")

        except Exception as e:
            logger.info(f"Error reading cache for listing {listing_id}: {str(e)}")
            return None

    def cache_summary(
        self, listing_id: str, prompt: str, reviews: list, summary: str
    ) -> bool:
        """
        Cache a generated summary for future use.
        Returns True if successfully cached, False otherwise.
        """
        if not self.enable_cache or not summary:
            return False

        try:
            reviews_hash = self._generate_reviews_hash(reviews)
            cache_key = self._generate_cache_key(listing_id, prompt, reviews_hash)
            cache_file = self._get_cache_file_path(cache_key)

            cache_data = {
                "listing_id": listing_id,
                "summary": summary,
                "timestamp": datetime.now().isoformat(),
                "reviews_count": len(reviews),
                "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "cache_key": cache_key,
            }

            save_json_file(cache_file, cache_data)
            logger.info(f"Cached summary for listing {listing_id}")
            return True

        except Exception as e:
            logger.info(f"Error caching summary for listing {listing_id}: {str(e)}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about cached summaries."""
        if not self.enable_cache or not os.path.exists(self.cache_dir):
            return {"enabled": False, "total_cached": 0}

        try:
            cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith(".json")]
            total_cached = len(cache_files)
            valid_cache_count = 0
            expired_cache_count = 0

            for cache_file in cache_files:
                try:
                    cache_data = load_json_file(
                        os.path.join(self.cache_dir, cache_file)
                    )
                    if self._is_cache_valid(cache_data):
                        valid_cache_count += 1
                    else:
                        expired_cache_count += 1
                except Exception:
                    expired_cache_count += 1

            return {
                "enabled": True,
                "total_cached": total_cached,
                "valid_cache": valid_cache_count,
                "expired_cache": expired_cache_count,
                "cache_directory": self.cache_dir,
                "ttl_hours": self.ttl_hours,
            }

        except Exception as e:
            return {"enabled": True, "error": str(e)}

    def clear_expired_cache(self) -> int:
        """Remove all expired cache files. Returns number of files removed."""
        if not self.enable_cache or not os.path.exists(self.cache_dir):
            return 0

        removed_count = 0
        try:
            cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith(".json")]

            for cache_file in cache_files:
                try:
                    cache_path = os.path.join(self.cache_dir, cache_file)
                    cache_data = load_json_file(cache_path)

                    if not self._is_cache_valid(cache_data):
                        os.remove(cache_path)
                        removed_count += 1

                except Exception:
                    # Remove corrupted cache files too
                    try:
                        os.remove(os.path.join(self.cache_dir, cache_file))
                        removed_count += 1
                    except Exception:
                        pass

            logger.info(f"Removed {removed_count} expired cache files")
            return removed_count

        except Exception as e:
            logger.info(f"Error clearing expired cache: {str(e)}")
            return 0

    def clear_all_cache(self) -> int:
        """Remove all cache files. Returns number of files removed."""
        if not self.enable_cache or not os.path.exists(self.cache_dir):
            return 0

        removed_count = 0
        try:
            cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith(".json")]

            for cache_file in cache_files:
                try:
                    os.remove(os.path.join(self.cache_dir, cache_file))
                    removed_count += 1
                except Exception:
                    pass

            logger.info(f"Removed {removed_count} cache files")
            return removed_count

        except Exception as e:
            logger.info(f"Error clearing all cache: {str(e)}")
            return 0
