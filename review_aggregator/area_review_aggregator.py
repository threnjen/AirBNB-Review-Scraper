import os

# import weaviate.classes as wvc
from utils.tiny_file_handler import load_json_file, save_json_file

from pydantic import BaseModel, ConfigDict, Field

# from review_aggregator.weaviate_client import WeaviateClient
from review_aggregator.openai_aggregator import OpenAIAggregator

# from utils.nlp_functions import filter_stopwords
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class AreaRagAggregator(BaseModel):
    """Aggregates property summaries into area-level insights."""

    num_listings: int = 3
    review_thresh_to_include_prop: int = 5
    zipcode: str = "00501"
    overall_mean: float = 0.0
    model_config = ConfigDict(arbitrary_types_allowed=True)
    openai_aggregator: OpenAIAggregator = Field(default_factory=OpenAIAggregator)
    # weaviate_client: WeaviateClient = Field(default_factory=WeaviateClient)  # <-- here

    def rag_description_generation_chain(self):
        """Generate area-level summary from existing property summaries."""

        # Load all property summaries from the output directory
        summary_files = [
            x
            for x in os.listdir("property_generated_summaries/")
            if x.startswith(f"generated_summaries_{self.zipcode}_")
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
            file_path = f"property_generated_summaries/{file}"
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
        updated_prompt = updated_prompt.replace(
            "{ISO_CODE_HERE}", load_json_file("config.json").get("iso_code", "us")
        )
        updated_prompt = updated_prompt.replace(
            "{OVERALL_MEAN}", str(self.overall_mean)
        )

        # Generate area summary using OpenAI
        area_summary = self.openai_aggregator.generate_summary(
            reviews=all_summaries,  # Pass summaries as "reviews" input
            prompt=updated_prompt,
            listing_id=f"area_{self.zipcode}",
        )

        # Save area-level summary
        output_data = {
            "zipcode": self.zipcode,
            "num_properties_analyzed": len(all_summaries),
            "area_summary": area_summary,
        }

        save_json_file(
            filename=f"generated_summaries_{self.zipcode}.json", data=output_data
        )

        logger.info(f"Area summary saved to generated_summaries_{self.zipcode}.json")

        # Log cost and cache statistics
        self.openai_aggregator.cost_tracker.print_session_summary()
        self.openai_aggregator.cost_tracker.log_session()

        cache_stats = self.openai_aggregator.cache_manager.get_cache_stats()
        if cache_stats.get("enabled"):
            logger.info(
                f"\nCache Statistics: {cache_stats['valid_cache']} valid, {cache_stats['expired_cache']} expired"
            )
