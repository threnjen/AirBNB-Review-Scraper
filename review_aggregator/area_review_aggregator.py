import logging
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from review_aggregator.openai_aggregator import OpenAIAggregator
from utils.tiny_file_handler import load_json_file, save_json_file

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class AreaRagAggregator(BaseModel):
    """Aggregates property summaries into area-level insights."""

    num_listings: int = 3
    review_thresh_to_include_prop: int = 5
    zipcode: str = "00501"
    overall_mean: float = 0.0
    output_dir: str = "reports"
    model_config = ConfigDict(arbitrary_types_allowed=True)
    openai_aggregator: OpenAIAggregator = Field(default_factory=OpenAIAggregator)
    pipeline_cache: Any = Field(default=None)

    def save_results(
        self,
        num_properties: int,
        iso_code: str,
        area_summary: str,
    ):
        """Save JSON stats and Markdown report for the area summary."""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        # Save JSON
        output_data = {
            "zipcode": self.zipcode,
            "num_properties_analyzed": num_properties,
            "area_summary": area_summary,
        }
        json_path = f"{self.output_dir}/area_summary_{self.zipcode}.json"
        save_json_file(filename=json_path, data=output_data)
        logger.info(f"Saved area summary JSON to {json_path}")

        # Save Markdown report
        md_path = f"{self.output_dir}/area_summary_{self.zipcode}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Area Summary: {self.zipcode}\n\n")
            f.write(f"**ISO Code:** {iso_code}\n\n")
            f.write(f"**Properties Analyzed:** {num_properties}\n\n")
            f.write("---\n\n")
            f.write(area_summary)

        logger.info(f"Saved area summary report to {md_path}")

    def rag_description_generation_chain(self):
        """Generate area-level summary from existing property summaries."""

        # Load all property summaries from the output directory
        summary_files = [
            x
            for x in os.listdir("outputs/06_listing_summaries/")
            if x.startswith(f"listing_summary_{self.zipcode}_")
        ]

        if not summary_files:
            logger.info(
                f"No property summaries found for zipcode {self.zipcode}; exiting."
            )
            return

        logger.info(
            f"Found {len(summary_files)} property summaries for zipcode {self.zipcode}"
        )

        # Collect all summaries
        all_summaries = []
        for file in summary_files[: self.num_listings]:
            file_path = f"outputs/06_listing_summaries/{file}"
            summary_data = load_json_file(filename=file_path)
            # Each file is {listing_id: summary_text}
            for listing_id, summary_text in summary_data.items():
                if summary_text:
                    all_summaries.append(f"Listing {listing_id}:\n{summary_text}")

        if not all_summaries:
            logger.info("No valid summaries to aggregate; exiting.")
            return

        logger.info(
            f"Aggregating {len(all_summaries)} property summaries into area summary"
        )

        # Load area-level prompt template
        prompt_data = load_json_file("prompts/zipcode_prompt.json")
        prompt_template = prompt_data.get("gpt4o_mini_generate_prompt_structured", "")

        # Replace placeholders in prompt
        updated_prompt = prompt_template.replace("{ZIP_CODE_HERE}", self.zipcode)
        iso_code = load_json_file("config.json").get("iso_code", "us")
        updated_prompt = updated_prompt.replace("{ISO_CODE_HERE}", iso_code)
        updated_prompt = updated_prompt.replace(
            "{OVERALL_MEAN}", str(self.overall_mean)
        )

        # Generate area summary using OpenAI
        area_summary = self.openai_aggregator.generate_summary(
            reviews=all_summaries,  # Pass summaries as "reviews" input
            prompt=updated_prompt,
            listing_id=f"area_{self.zipcode}",
        )

        # Save area-level summary (JSON + Markdown report)
        self.save_results(
            num_properties=len(all_summaries),
            iso_code=iso_code,
            area_summary=area_summary,
        )

        # Log cost and cache statistics
        self.openai_aggregator.cost_tracker.print_session_summary()
        self.openai_aggregator.cost_tracker.log_session()
