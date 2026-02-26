import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import tiktoken
from pydantic import BaseModel, Field

from utils.tiny_file_handler import load_json_file, save_json_file

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class CostTracker(BaseModel):
    """
    Tracks OpenAI API usage and costs for review aggregation.
    Logs token usage, API calls, and provides cost estimates.
    """

    # GPT-4.1-mini pricing (per 1M tokens)
    input_cost_per_million: float = 0.40  # $0.40 per 1M input tokens
    output_cost_per_million: float = 1.60  # $1.60 per 1M output tokens

    model: str = "gpt-4.1-mini"
    enable_tracking: bool = True
    log_file: str = "logs/cost_tracking.json"

    # Session tracking
    session_stats: Dict = Field(default_factory=dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load configuration overrides if available
        try:
            config = load_json_file("config.json")
            openai_config = config.get("openai", {})
            self.enable_tracking = openai_config.get(
                "enable_cost_tracking", self.enable_tracking
            )
        except Exception:
            pass

        # Create logs directory if it doesn't exist
        if self.enable_tracking:
            Path(os.path.dirname(self.log_file)).mkdir(parents=True, exist_ok=True)

        # Initialize session stats
        self.reset_session()

    def reset_session(self):
        """Reset session statistics."""
        self.session_stats = {
            "session_start": datetime.now().isoformat(),
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "listings_processed": [],
            "requests": [],
        }

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text using tiktoken."""
        try:
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except Exception:
            # Fallback estimation: roughly 4 characters per token
            return len(text) // 4

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token usage."""
        input_cost = (input_tokens / 1_000_000) * self.input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_cost_per_million
        return round(input_cost + output_cost, 6)

    def track_request(
        self,
        listing_id: str,
        prompt: str,
        reviews: List[str],
        response: Optional[str] = None,
        success: bool = True,
        cached: bool = False,
        chunk_info: Optional[str] = None,
    ) -> Dict:
        """
        Track an OpenAI API request and return cost information.
        """
        if not self.enable_tracking:
            return {}

        # Calculate token usage
        input_text = prompt + "\n".join(reviews) if reviews else prompt
        input_tokens = self.estimate_tokens(input_text)
        output_tokens = self.estimate_tokens(response) if response else 0

        # Calculate cost
        request_cost = (
            0.0 if cached else self.calculate_cost(input_tokens, output_tokens)
        )

        # Create request record
        request_record = {
            "timestamp": datetime.now().isoformat(),
            "listing_id": listing_id,
            "success": success,
            "cached": cached,
            "chunk_info": chunk_info,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": request_cost,
            "reviews_count": len(reviews) if reviews else 0,
            "prompt_length": len(prompt),
            "response_length": len(response) if response else 0,
        }

        # Update session stats
        self.session_stats["total_requests"] += 1

        if success:
            self.session_stats["successful_requests"] += 1
        else:
            self.session_stats["failed_requests"] += 1

        if cached:
            self.session_stats["cache_hits"] += 1
        else:
            self.session_stats["total_input_tokens"] += input_tokens
            self.session_stats["total_output_tokens"] += output_tokens
            self.session_stats["total_cost"] += request_cost

        if listing_id not in self.session_stats["listings_processed"]:
            self.session_stats["listings_processed"].append(listing_id)

        self.session_stats["requests"].append(request_record)

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": request_cost,
            "cached": cached,
        }

    def get_session_summary(self) -> Dict:
        """Get summary of current session costs and usage."""
        if not self.enable_tracking:
            return {"tracking_enabled": False}

        session_duration = (
            datetime.now() - datetime.fromisoformat(self.session_stats["session_start"])
        ).total_seconds()

        return {
            "tracking_enabled": True,
            "session_duration_minutes": round(session_duration / 60, 2),
            "total_requests": self.session_stats["total_requests"],
            "successful_requests": self.session_stats["successful_requests"],
            "failed_requests": self.session_stats["failed_requests"],
            "cache_hits": self.session_stats["cache_hits"],
            "cache_hit_rate": (
                round(
                    self.session_stats["cache_hits"]
                    / max(1, self.session_stats["total_requests"])
                    * 100,
                    1,
                )
            ),
            "unique_listings": len(self.session_stats["listings_processed"]),
            "total_input_tokens": self.session_stats["total_input_tokens"],
            "total_output_tokens": self.session_stats["total_output_tokens"],
            "total_tokens": self.session_stats["total_input_tokens"]
            + self.session_stats["total_output_tokens"],
            "total_cost": round(self.session_stats["total_cost"], 4),
            "average_cost_per_listing": (
                round(
                    self.session_stats["total_cost"]
                    / max(1, len(self.session_stats["listings_processed"])),
                    4,
                )
            ),
            "estimated_cost_per_100_listings": (
                round(
                    self.session_stats["total_cost"]
                    * 100
                    / max(1, len(self.session_stats["listings_processed"])),
                    2,
                )
            ),
        }

    def log_session(self) -> bool:
        """Save session data to log file."""
        if not self.enable_tracking:
            return False

        try:
            # Load existing logs
            logs = []
            if os.path.exists(self.log_file):
                logs = load_json_file(self.log_file)

            # Add current session
            session_log = {
                **self.session_stats,
                "session_end": datetime.now().isoformat(),
                "summary": self.get_session_summary(),
            }

            logs.append(session_log)

            # Keep only last 100 sessions to prevent file from getting too large
            if len(logs) > 100:
                logs = logs[-100:]

            save_json_file(self.log_file, logs)
            logger.info(f"Session costs logged to {self.log_file}")
            return True

        except Exception as e:
            logger.info(f"Error logging session: {str(e)}")
            return False

    def print_session_summary(self):
        """logger.info a formatted summary of the current session."""
        summary = self.get_session_summary()

        if not summary.get("tracking_enabled"):
            logger.info("Cost tracking is disabled")
            return

        logger.info("\n" + "=" * 50)
        logger.info("        OpenAI COST TRACKING SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Session Duration: {summary['session_duration_minutes']} minutes")
        logger.info(f"Model: {self.model}")

        logger.info("API USAGE:")
        logger.info(f"  Total Requests: {summary['total_requests']}")
        logger.info(f"  Successful: {summary['successful_requests']}")
        logger.info(f"  Failed: {summary['failed_requests']}")
        logger.info(
            f"  Cache Hits: {summary['cache_hits']} ({summary['cache_hit_rate']}%)"
        )

        logger.info("PROCESSING:")
        logger.info(f"  Unique Listings: {summary['unique_listings']}")
        logger.info(f"  Avg Cost per Listing: ${summary['average_cost_per_listing']}")
        logger.info(
            f"  Est. Cost per 100 Listings: ${summary['estimated_cost_per_100_listings']}"
        )

        logger.info("TOKEN USAGE:")
        logger.info(f"  Input Tokens: {summary['total_input_tokens']:,}")
        logger.info(f"  Output Tokens: {summary['total_output_tokens']:,}")
        logger.info(f"  Total Tokens: {summary['total_tokens']:,}")

        logger.info("COSTS:")
        logger.info(f"  Total Session Cost: ${summary['total_cost']}")
        logger.info("=" * 50)

    def get_historical_stats(self, days: int = 30) -> Dict:
        """Get historical cost statistics from log file."""
        if not self.enable_tracking or not os.path.exists(self.log_file):
            return {"tracking_enabled": False}

        try:
            logs = load_json_file(self.log_file)
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

            recent_logs = []
            for log in logs:
                try:
                    log_date = datetime.fromisoformat(log["session_start"]).timestamp()
                    if log_date >= cutoff_date:
                        recent_logs.append(log)
                except Exception:
                    continue

            if not recent_logs:
                return {"tracking_enabled": True, "no_data": True, "days": days}

            total_cost = sum(log.get("total_cost", 0) for log in recent_logs)
            total_listings = sum(
                len(log.get("listings_processed", [])) for log in recent_logs
            )
            total_requests = sum(log.get("total_requests", 0) for log in recent_logs)

            return {
                "tracking_enabled": True,
                "days": days,
                "sessions": len(recent_logs),
                "total_cost": round(total_cost, 4),
                "total_listings": total_listings,
                "total_requests": total_requests,
                "average_cost_per_listing": round(
                    total_cost / max(1, total_listings), 4
                ),
                "average_cost_per_session": round(
                    total_cost / max(1, len(recent_logs)), 4
                ),
            }

        except Exception as e:
            return {"tracking_enabled": True, "error": str(e)}
