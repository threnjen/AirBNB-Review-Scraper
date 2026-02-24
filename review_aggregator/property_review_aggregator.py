from typing import Any
import pandas as pd
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


class PropertyRagAggregator(BaseModel):
    review_thresh_to_include_prop: int = 5
    model_config = ConfigDict(arbitrary_types_allowed=True)
    num_completed_listings: int = 0
    num_overall_ids: int = 100
    # collection_name: str = "Reviews"
    overall_stats: dict = Field(default_factory=dict)
    listing_ids: list = Field(default_factory=list)
    generate_prompt: str = "None"  # consider Optional[str] = None
    zipcode: str = "00501"
    overall_mean: float = 0.0
    num_listings_to_summarize: int = 0
    empty_aggregated_reviews: list = Field(default_factory=list)
    review_ids_need_more_processing: list = Field(default_factory=list)
    # weaviate_client: WeaviateClient = Field(default_factory=WeaviateClient)  # <-- here
    openai_aggregator: OpenAIAggregator = Field(default_factory=OpenAIAggregator)

    # def model_post_init(self, __context: Any) -> None:
    #     self.weaviate_client.create_general_collection(
    #         collection_name=self.collection_name,
    #         incoming_properties=[
    #             {
    #                 "name": "review_text",
    #                 "data_type": wvc.config.DataType.TEXT,
    #                 "vectorize_property_name": False,
    #             },
    #             {
    #                 "name": "product_id",
    #                 "data_type": wvc.config.DataType.TEXT,
    #                 "skip_vectorization": True,
    #                 "vectorize_property_name": False,
    #             },
    #         ],
    #     )

    def adjust_list_length_upper_bound_for_config(
        self, unprocessed_reviews: dict
    ) -> int:
        # placeholder function to count the number of listing ids.
        total_listings = len(unprocessed_reviews)
        if self.num_listings_to_summarize < total_listings:
            num_listings_to_summarize = self.num_listings_to_summarize
        else:
            num_listings_to_summarize = total_listings

        return num_listings_to_summarize

    def get_listing_id_mean_rating(self, one_property_reviews) -> float:
        mean_rating = 0
        for review in one_property_reviews:
            if review.get("rating") is None:
                pass
            else:
                mean_rating += review.get("rating")
        if len(one_property_reviews) > 0:
            mean_rating /= len(one_property_reviews)
            mean_rating = round(mean_rating, 4)
        else:
            mean_rating = 0
        # logger.info(f"Calculated mean for listing {listing_id}: {mean_rating}")
        return mean_rating

    def get_overall_mean_rating(self, reviews: dict) -> float:
        overall_mean = 0
        for listing_id in reviews:
            overall_mean += self.get_listing_id_mean_rating(
                one_property_reviews=reviews[listing_id]
            )

        overall_mean /= len(reviews)
        overall_mean = round(overall_mean, 4)
        # logger.info(f"The overall mean rating is {overall_mean}")
        logger.info(f"Calculated overall mean: {overall_mean}")
        return overall_mean

    def prompt_replacement(
        self,
        current_prompt: str,
        listing_mean: str,
        overall_mean: str,
    ) -> str:
        # Add more replacements to fill out the entire prompt
        current_prompt = current_prompt.replace("{ZIP_CODE_HERE}", self.zipcode)
        current_prompt = current_prompt.replace(
            "{ISO_CODE_HERE}", load_json_file("config.json").get("iso_code", "us")
        )
        current_prompt = current_prompt.replace("{RATING_AVERAGE_HERE}", listing_mean)
        current_prompt = current_prompt.replace("{OVERALL_MEAN}", overall_mean)
        return current_prompt

    def clean_single_item_reviews(self, ratings: dict) -> list:
        df = pd.DataFrame(ratings)[["rating", "review"]]

        # df["review"] = df["review"].replace(r"[^A-Za-z0-9 ]+", "", regex=True)
        # df["review"] = df["review"].str.lower().apply(lambda x: filter_stopwords(x))

        # remove all special characters from combined_review
        df["combined_review"] = df["rating"].astype("string") + " " + df["review"]

        return df["combined_review"].to_list()

    def process_single_listing(self, one_property_reviews, listing_id):
        logger.info(
            f"\nProcessing listing {listing_id}\n{self.num_completed_listings} of {self.num_listings_to_summarize}"
        )

        listing_mean_rating = self.get_listing_id_mean_rating(
            one_property_reviews=one_property_reviews
        )
        logger.info(f"Listing {listing_id} mean rating: {listing_mean_rating}")

        if (
            one_property_reviews is None
            or len(one_property_reviews) == 0
            or len(one_property_reviews) < self.review_thresh_to_include_prop
        ):
            logger.info(
                f"No reviews found for listing {listing_id} or number under threshold; skipping."
            )
            return

        generated_prompt = load_json_file("prompts/prompt.json")["prompt"]

        updated_prompt = self.prompt_replacement(
            current_prompt=generated_prompt,
            listing_mean=str(listing_mean_rating),
            overall_mean=str(self.overall_mean),
        )
        reviews = self.clean_single_item_reviews(ratings=one_property_reviews)

        # self.weaviate_client.add_collection_batch(
        #     collection_name=self.collection_name,
        #     listing_id=listing_id,
        #     items=reviews,
        # )

        # summary = self.weaviate_client.generate_aggregate(
        #     id=listing_id,
        #     collection_name=self.collection_name,
        #     generate_prompt=updated_prompt,
        #     filter_field="product_id",
        #     return_properties=["review_text"],
        # )

        # self.weaviate_client.remove_collection_listings(
        #     listing_id=listing_id, collection_name=self.collection_name, items=reviews
        # )

        # Generate summary using OpenAI aggregator
        summary = self.openai_aggregator.generate_summary(
            reviews=reviews, prompt=updated_prompt, listing_id=listing_id
        )

        return summary

    def filter_out_processed_reviews(
        self, reviews: dict, already_processed_reviews: dict
    ) -> dict:
        already_processed_reviews_ids = list(already_processed_reviews.keys())

        logger.info(f"Already aggregated ids: {len(already_processed_reviews_ids)}")

        unprocessed_reviews = {
            x: y for x, y in reviews.items() if x not in already_processed_reviews_ids
        }

        logger.info(f"Reviews to process after filtering: {len(unprocessed_reviews)}")

        return unprocessed_reviews

    def get_unfinished_aggregated_reviews(self, generated_summaries) -> list[str]:
        incomplete_keys = []
        for key, value in generated_summaries.items():
            if "?" in value:
                incomplete_keys.append(key)

        logger.info(f"Listings needing more processing: {len(incomplete_keys)}")
        return incomplete_keys

    def get_empty_aggregated_reviews(self, generated_summaries) -> list[str]:
        incomplete_keys = []
        for key, value in generated_summaries.items():
            if value == "" or value is None:
                incomplete_keys.append(key)
        return incomplete_keys

    def remove_empty_reviews(self, generated_summaries) -> dict:
        empty_aggregated_reviews = self.get_empty_aggregated_reviews(
            generated_summaries
        )
        for empty_id in empty_aggregated_reviews:
            del generated_summaries[empty_id]
            os.remove(
                f"property_generated_summaries/generated_summaries_{self.zipcode}_{empty_id}.json"
            )

        return generated_summaries

    def rag_description_generation_chain(self):
        # Load reviews along with any existing aggregated summaries to determine what still needs processing

        reviews = {}
        generated_summaries = {}

        review_files = [
            x
            for x in os.listdir("property_reviews_scraped/")
            if x.startswith("reviews_")
        ]

        for file in review_files:
            one_property = load_json_file(filename=f"property_reviews_scraped/{file}")
            reviews.update(one_property)
        logger.info(f"Total property loaded: {len(reviews)}")

        generated_summaries_files = [
            x
            for x in os.listdir("property_generated_summaries/")
            if x.startswith("generated_summaries_")
        ]
        # logger.info(f"Generated summaries files found: {generated_summaries_files}")

        for file in generated_summaries_files:
            # logger.info(f"Using generated summaries file: {file}")
            one_property = load_json_file(
                filename=f"property_generated_summaries/{file}"
            )
            generated_summaries.update(one_property)

        logger.info(f"Already processed reviews loaded: {len(generated_summaries)}")

        self.overall_mean = self.get_overall_mean_rating(reviews=reviews)

        unprocessed_reviews = self.filter_out_processed_reviews(
            reviews=reviews, already_processed_reviews=generated_summaries
        )

        if not unprocessed_reviews:
            logger.info("No unprocessed reviews found; exiting.")
            return

        unprocessed_reviews_ids = list(unprocessed_reviews.keys())
        logger.info(f"Number of reviews to aggregate: {len(unprocessed_reviews_ids)}")

        self.num_listings_to_summarize = self.adjust_list_length_upper_bound_for_config(
            unprocessed_reviews=unprocessed_reviews,
        )
        logger.info(
            f"Number of listings to summarize in this run: {self.num_listings_to_summarize}"
        )

        start_index = 0
        end_index = start_index + self.num_listings_to_summarize

        # First pass: process each unprocessed listing up to the configured limit
        for listing_id in unprocessed_reviews_ids[start_index:end_index]:
            generated_summaries[listing_id] = self.process_single_listing(
                one_property_reviews=unprocessed_reviews[listing_id],
                listing_id=listing_id,
            )

            self.num_completed_listings += 1

            save_json_file(
                filename=f"property_generated_summaries/generated_summaries_{self.zipcode}_{listing_id}.json",
                data={listing_id: generated_summaries[listing_id]},
            )
        logger.info("First pass of RAG description generation chain completed.")

        # Second pass: Remove any listings that resulted in empty summaries
        generated_summaries = self.remove_empty_reviews(generated_summaries)

        # Third pass: Re-process any listings that resulted in incomplete summaries where the model indicated uncertainty
        self.review_ids_need_more_processing = self.get_unfinished_aggregated_reviews(
            generated_summaries
        )

        for listing_id in self.review_ids_need_more_processing:
            logger.info(listing_id)
            generated_summaries[listing_id] = self.process_single_listing(
                one_property_reviews=reviews[listing_id],
                listing_id=listing_id,
            )

            self.num_completed_listings += 1

            save_json_file(
                filename=f"property_generated_summaries/generated_summaries_{self.zipcode}_{listing_id}.json",
                data={listing_id: generated_summaries[listing_id]},
            )
        logger.info("RAG description generation chain completed.")

        # logger.info cost summary and log session
        self.openai_aggregator.cost_tracker.print_session_summary()
        self.openai_aggregator.cost_tracker.log_session()

        # logger.info cache statistics
        cache_stats = self.openai_aggregator.cache_manager.get_cache_stats()
        if cache_stats.get("enabled"):
            logger.info(
                f"\nCache Statistics: {cache_stats['valid_cache']} valid, {cache_stats['expired_cache']} expired"
            )

        # Clean up expired cache
        if cache_stats.get("expired_cache", 0) > 0:
            self.openai_aggregator.cache_manager.clear_expired_cache()
