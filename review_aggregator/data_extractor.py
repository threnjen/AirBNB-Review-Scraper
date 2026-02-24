"""
DataExtractor: Extracts and aggregates numeric review data from property summaries.
Uses LLM to parse semi-structured text and cluster topics into categories.
"""

import json
import logging
import os
import sys
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from review_aggregator.openai_aggregator import OpenAIAggregator
from utils.tiny_file_handler import load_json_file, save_json_file

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


# Seed categories for clustering
POSITIVE_CATEGORIES = [
    "Location",
    "Host Communication",
    "Cleanliness",
    "Amenities",
    "Value",
    "Comfort",
    "Character/Ambiance",
    "Accuracy",
]

NEGATIVE_CATEGORIES = [
    "Cleanliness Issues",
    "Noise",
    "Privacy Concerns",
    "Accessibility",
    "Missing Amenities",
    "Communication Issues",
    "Inaccuracy",
    "Maintenance",
]


class DataExtractor(BaseModel):
    """Extracts and aggregates review data from property summaries."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    zipcode: str = "00000"
    summary_dir: str = "property_generated_summaries"
    openai_aggregator: OpenAIAggregator = Field(default_factory=OpenAIAggregator)

    def load_property_summaries(self) -> dict[str, str]:
        """Load all property summaries for this zipcode."""
        summaries = {}

        if not os.path.exists(self.summary_dir):
            logger.warning(f"Summary directory {self.summary_dir} does not exist")
            return summaries

        for filename in os.listdir(self.summary_dir):
            if filename.startswith(f"generated_summaries_{self.zipcode}_"):
                file_path = f"{self.summary_dir}/{filename}"
                data = load_json_file(filename=file_path)
                summaries.update(data)

        logger.info(
            f"Loaded {len(summaries)} property summaries for zipcode {self.zipcode}"
        )
        return summaries

    def extract_data_from_summary(self, listing_id: str, summary_text: str) -> dict:
        """Use LLM to extract structured data from a property summary."""

        extraction_prompt = f"""Extract the numeric review data from this property summary.

For each item mentioned in the Positives and Criticisms sections, extract:
- topic: The name of the topic (e.g., "Location", "Hot Tub")
- sentiment: "positive" or "negative"
- mentions: The number before "of" (e.g., 15 from "15 of 20 Reviews")
- total_reviews: The number after "of" (e.g., 20 from "15 of 20 Reviews")
- description: Brief description from the summary

Categorize each topic into one of these categories:

Positive categories: {POSITIVE_CATEGORIES}
Negative categories: {NEGATIVE_CATEGORIES}

If a topic doesn't fit existing categories, assign it to the closest match or create a specific new category name.

Return a JSON object with this structure:
{{
  "listing_id": "{listing_id}",
  "total_reviews": <total reviews for this property>,
  "items": [
    {{
      "category": "<category name>",
      "original_topic": "<topic from summary>",
      "sentiment": "<positive or negative>",
      "mentions": <number>,
      "total_reviews": <number>,
      "description": "<brief description>"
    }}
  ]
}}

Property Summary:
{summary_text}
"""

        response = self.openai_aggregator.generate_summary(
            reviews=[extraction_prompt],
            prompt="Extract the data as requested and return only valid JSON.",
            listing_id=f"extract_{listing_id}",
        )

        # Parse JSON response
        try:
            # Clean response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction for {listing_id}: {e}")
            return {"listing_id": listing_id, "total_reviews": 0, "items": []}

    def aggregate_extractions(self, extractions: list[dict]) -> dict:
        """Aggregate extracted data across all properties."""

        positive_categories: dict[str, Any] = {}
        negative_categories: dict[str, Any] = {}
        total_reviews = 0

        for extraction in extractions:
            listing_id = extraction.get("listing_id", "unknown")
            listing_reviews = extraction.get("total_reviews", 0)
            total_reviews += listing_reviews

            for item in extraction.get("items", []):
                category = item.get("category", "Other")
                sentiment = item.get("sentiment", "positive")
                mentions = item.get("mentions", 0)
                item_reviews = item.get("total_reviews", listing_reviews)
                description = item.get("description", "")
                original_topic = item.get("original_topic", category)

                # Choose target dict based on sentiment
                target = (
                    positive_categories
                    if sentiment == "positive"
                    else negative_categories
                )

                if category not in target:
                    target[category] = {
                        "total_mentions": 0,
                        "total_reviews": 0,
                        "properties": [],
                    }

                target[category]["total_mentions"] += mentions
                target[category]["total_reviews"] += item_reviews
                target[category]["properties"].append(
                    {
                        "id": listing_id,
                        "mentions": mentions,
                        "reviews": item_reviews,
                        "original_topic": original_topic,
                        "description": description,
                    }
                )

        # Calculate percentages
        for category_dict in [positive_categories, negative_categories]:
            for category, data in category_dict.items():
                if data["total_reviews"] > 0:
                    data["percentage"] = round(
                        (data["total_mentions"] / data["total_reviews"]) * 100, 1
                    )
                else:
                    data["percentage"] = 0.0

        # Sort by total mentions descending
        positive_categories = dict(
            sorted(
                positive_categories.items(),
                key=lambda x: x[1]["total_mentions"],
                reverse=True,
            )
        )
        negative_categories = dict(
            sorted(
                negative_categories.items(),
                key=lambda x: x[1]["total_mentions"],
                reverse=True,
            )
        )

        return {
            "zipcode": self.zipcode,
            "total_properties_analyzed": len(extractions),
            "total_reviews_in_area": total_reviews,
            "positive_categories": positive_categories,
            "negative_categories": negative_categories,
        }

    def run_extraction(self):
        """Main entry point: extract, aggregate, and save."""

        summaries = self.load_property_summaries()

        if not summaries:
            logger.info(
                f"No property summaries found for zipcode {self.zipcode}; exiting."
            )
            return None

        logger.info(f"Extracting data from {len(summaries)} property summaries")

        extractions = []
        for listing_id, summary_text in summaries.items():
            if summary_text:
                extraction = self.extract_data_from_summary(listing_id, summary_text)
                extractions.append(extraction)

        logger.info(f"Extracted data from {len(extractions)} properties")

        # Aggregate across all properties
        aggregated = self.aggregate_extractions(extractions)

        # Save output
        output_path = f"area_data_{self.zipcode}.json"
        save_json_file(filename=output_path, data=aggregated)

        logger.info(f"Area data saved to {output_path}")
        logger.info(f"Positive categories: {len(aggregated['positive_categories'])}")
        logger.info(f"Negative categories: {len(aggregated['negative_categories'])}")

        # Log costs
        self.openai_aggregator.cost_tracker.print_session_summary()
        self.openai_aggregator.cost_tracker.log_session()

        return aggregated
