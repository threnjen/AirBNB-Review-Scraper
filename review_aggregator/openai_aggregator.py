import logging
import os
import sys
import time
from typing import List, Optional

import pandas as pd
import tiktoken
from openai import OpenAI
from pydantic import BaseModel, Field

from utils.cache_manager import CacheManager
from utils.cost_tracker import CostTracker
from utils.tiny_file_handler import load_json_file

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class OpenAIAggregator(BaseModel):
    """
    OpenAI client for aggregating Airbnb reviews using GPT-4.1-mini.
    Handles token management, chunking, and cost-efficient processing.
    """

    client: OpenAI = Field(default_factory=lambda: OpenAI())
    model: str = "gpt-4.1-mini"
    temperature: float = 0.3
    max_tokens: int = 16000
    chunk_size: int = 20  # Reviews per chunk
    max_retries: int = 3
    retry_delay: float = 1.0

    # Integrated utilities
    cache_manager: CacheManager = Field(default_factory=CacheManager)
    cost_tracker: CostTracker = Field(default_factory=CostTracker)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load configuration overrides if available
        try:
            config = load_json_file("config.json")
            openai_config = config.get("openai", {})

            if openai_config:
                self.model = openai_config.get("model", self.model)
                self.temperature = openai_config.get("temperature", self.temperature)
                self.max_tokens = openai_config.get("max_tokens", self.max_tokens)
                self.chunk_size = openai_config.get("chunk_size", self.chunk_size)
        except Exception:
            # Continue with defaults if config loading fails
            pass

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text using tiktoken."""

        # Check for NA/None/empty values
        # Check pd.isna() FIRST before string conversions to catch pandas NA types
        try:
            if pd.isna(text):
                return 0
        except (TypeError, ValueError):
            pass

        # Check for None and empty strings
        if text is None or text == "":
            return 0

        # Check for string representations of NA values (including pandas <NA>)
        text_str_lower = str(text).lower()
        if text_str_lower in ["nan", "na", "none", "<na>"]:
            return 0

        try:
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(str(text)))
        except Exception:
            # Fallback estimation: roughly 4 characters per token
            return len(str(text)) // 4

    def chunk_reviews(self, reviews: List[str], prompt: str) -> List[List[str]]:
        """
        Intelligently chunk reviews to stay within token limits.
        Prioritizes keeping reviews together when possible.
        """
        chunks = []
        current_chunk = []
        current_tokens = self.estimate_tokens(prompt)

        for review in reviews:
            review_tokens = self.estimate_tokens(review)

            # If adding this review would exceed limits or chunk size, start new chunk
            if (
                current_tokens + review_tokens > 120000  # Leave buffer for 128k context
                or len(current_chunk) >= self.chunk_size
            ):
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = [review]
                    current_tokens = self.estimate_tokens(prompt) + review_tokens
                else:
                    # Single review too large, truncate it
                    truncated_review = review[:2000] + "... [truncated]"
                    chunks.append([truncated_review])
                    current_tokens = self.estimate_tokens(prompt)
            else:
                current_chunk.append(review)
                current_tokens += review_tokens

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def create_chunk_prompt(
        self, base_prompt: str, reviews: List[str], chunk_info: str = ""
    ) -> str:
        """Create a prompt for processing a chunk of reviews."""
        reviews_text = "\n".join(
            [f"Review {i + 1}: {review}" for i, review in enumerate(reviews)]
        )

        chunk_prompt = base_prompt + "\n\n"
        if chunk_info:
            chunk_prompt += f"{chunk_info}\n\n"

        chunk_prompt += f"Reviews to analyze:\n{reviews_text}\n\n"
        chunk_prompt += (
            "Please provide the analysis following the exact format specified above."
        )

        return chunk_prompt

    def call_openai_with_retry(self, prompt: str, listing_id: str) -> Optional[str]:
        """Make OpenAI API call with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=60.0,
                )

                return response.choices[0].message.content.strip()

            except Exception as e:
                logger.info(
                    f"OpenAI API error for listing {listing_id} (attempt {attempt + 1}): {str(e)}"
                )

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))  # Exponential backoff
                else:
                    logger.info(
                        f"Failed to process listing {listing_id} after {self.max_retries} attempts"
                    )
                    return None

    def merge_chunk_summaries(
        self, chunk_summaries: List[str], original_prompt: str, listing_id: str
    ) -> str:
        """Merge multiple chunk summaries into a final comprehensive summary."""
        if len(chunk_summaries) == 1:
            return chunk_summaries[0]

        merge_prompt = f"""
You have received multiple partial analyses of Airbnb reviews for the same listing. Please combine them into a single comprehensive summary following the original format requirements.

Original format requirements:
{original_prompt.split("Reviews to analyze:")[0].strip()}

Partial analyses to merge:
"""

        for i, summary in enumerate(chunk_summaries, 1):
            merge_prompt += f"\n--- Analysis {i} ---\n{summary}\n"

        merge_prompt += """
Please provide a single unified analysis that:
1. Maintains the exact 5-section format from the original requirements
2. Combines and reconciles the data from all partial analyses
3. Provides accurate overall percentages and mention counts
4. Creates a coherent final summary

Unified Analysis:"""

        return self.call_openai_with_retry(merge_prompt, f"{listing_id}_merge")

    def generate_summary(
        self, reviews: List[str], prompt: str, listing_id: str
    ) -> Optional[str]:
        """
        Generate aggregated summary from reviews using OpenAI.
        Handles chunking for large review sets, caching, and cost tracking.
        """
        if not reviews:
            logger.info(f"No reviews provided for listing {listing_id}")
            return None

        logger.info(f"Processing {len(reviews)} reviews for listing {listing_id}")

        # Check cache first
        cached_summary = self.cache_manager.get_cached_summary(
            listing_id, prompt, reviews
        )
        if cached_summary:
            # Track cache hit
            self.cost_tracker.track_request(
                listing_id=listing_id,
                prompt=prompt,
                reviews=reviews,
                response=cached_summary,
                success=True,
                cached=True,
            )
            return cached_summary

        # Check if we need to chunk the reviews
        total_tokens = self.estimate_tokens(prompt) + sum(
            self.estimate_tokens(review) for review in reviews
        )

        summary = None

        if total_tokens <= 120000 and len(reviews) <= self.chunk_size:
            # Process all reviews in single request
            full_prompt = self.create_chunk_prompt(prompt, reviews)
            summary = self.call_openai_with_retry(full_prompt, listing_id)

            # Track the API call
            self.cost_tracker.track_request(
                listing_id=listing_id,
                prompt=full_prompt,
                reviews=[],  # Reviews already included in prompt
                response=summary,
                success=summary is not None,
                cached=False,
            )
        else:
            # Need to chunk reviews
            logger.info(
                f"Large review set detected ({total_tokens} tokens), chunking into smaller pieces"
            )
            chunks = self.chunk_reviews(reviews, prompt)
            chunk_summaries = []

            for i, chunk in enumerate(chunks):
                chunk_info = f"Processing chunk {i + 1} of {len(chunks)} (reviews {i * self.chunk_size + 1}-{i * self.chunk_size + len(chunk)})"
                chunk_prompt = self.create_chunk_prompt(prompt, chunk, chunk_info)

                chunk_summary = self.call_openai_with_retry(
                    chunk_prompt, f"{listing_id}_chunk_{i + 1}"
                )

                # Track each chunk API call
                self.cost_tracker.track_request(
                    listing_id=listing_id,
                    prompt=chunk_prompt,
                    reviews=[],  # Reviews already included in prompt
                    response=chunk_summary,
                    success=chunk_summary is not None,
                    cached=False,
                    chunk_info=chunk_info,
                )

                if chunk_summary:
                    chunk_summaries.append(chunk_summary)
                else:
                    logger.info(
                        f"Failed to process chunk {i + 1} for listing {listing_id}"
                    )

            if not chunk_summaries:
                logger.info(f"No successful chunk processing for listing {listing_id}")
                return None

            # Merge chunk summaries if we have multiple
            if len(chunk_summaries) > 1:
                logger.info(
                    f"Merging {len(chunk_summaries)} chunk summaries for listing {listing_id}"
                )
                summary = self.merge_chunk_summaries(
                    chunk_summaries, prompt, listing_id
                )

                # Track the merge API call
                self.cost_tracker.track_request(
                    listing_id=f"{listing_id}_merge",
                    prompt="Merge prompt",  # Simplified for tracking
                    reviews=[],
                    response=summary,
                    success=summary is not None,
                    cached=False,
                    chunk_info="Merging chunks",
                )
            else:
                summary = chunk_summaries[0]

        # Cache the result if we got a valid summary
        if summary:
            self.cache_manager.cache_summary(listing_id, prompt, reviews, summary)

        return summary
