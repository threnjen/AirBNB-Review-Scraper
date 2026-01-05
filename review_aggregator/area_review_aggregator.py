from typing import Any
import pandas as pd
import weaviate.classes as wvc
from utils.tiny_file_handler import load_json_file, save_json_file

from pydantic import BaseModel, ConfigDict, Field

from review_aggregator.weaviate_client import WeaviateClient

from utils.nlp_functions import filter_stopwords


class AreaRagAggregator(BaseModel):
    review_threshold: int = 5
    num_listings: int = 3
    model_config = ConfigDict(arbitrary_types_allowed=True)
    num_completed_listings: int = 0
    num_overall_ids: int = 100
    collection_name: str = "Summaries"
    overall_stats: dict = Field(default_factory=dict)
    listing_ids: list = Field(default_factory=list)
    generate_prompt: str = "None"  # consider Optional[str] = None
    zipcode: str = "00501"
    overall_mean: float = 0.0
    number_of_listings_to_process: int = 0
    empty_aggregated_reviews: list = Field(default_factory=list)
    review_ids_need_more_processing: list = Field(default_factory=list)
    weaviate_client: WeaviateClient = Field(default_factory=WeaviateClient)  # <-- here

    def model_post_init(self, __context: Any) -> None:
        self.weaviate_client.create_general_collection(
            collection_name=self.collection_name,
            incoming_properties=[
                {
                    "name": "review_text",
                    "data_type": wvc.config.DataType.TEXT,
                    "vectorize_property_name": False,
                },
                {
                    "name": "product_id",
                    "data_type": wvc.config.DataType.TEXT,
                    "skip_vectorization": True,
                    "vectorize_property_name": False,
                },
            ],
        )

    def adjust_list_length_upper_bound_for_config(
        self, unprocessed_reviews: dict
    ) -> int:
        # placeholder function to count the number of listing ids.
        total_listings = len(unprocessed_reviews)
        if self.num_listings < total_listings:
            number_of_listings_to_process = self.num_listings
        else:
            number_of_listings_to_process = total_listings

        return number_of_listings_to_process

    def get_listing_ratings_and_reviews(self, reviews: dict, listing_id: str) -> list:
        listing_ratings_and_reviews = reviews.get(listing_id)
        return listing_ratings_and_reviews

    def get_listing_id_mean_rating(self, reviews, listing_id) -> float:
        mean_rating = 0
        listing_data = self.get_listing_ratings_and_reviews(reviews, listing_id)
        for review in listing_data:
            if review.get("rating") is None:
                pass
            else:
                mean_rating += review.get("rating")
        if len(listing_data) > 0:
            mean_rating /= len(listing_data)
            mean_rating = round(mean_rating, 4)
        else:
            mean_rating = 0
        return mean_rating

    def get_overall_mean_rating(self, reviews: dict) -> float:
        overall_mean = 0
        for listing_id in reviews:
            overall_mean += self.get_listing_id_mean_rating(
                reviews=reviews, listing_id=listing_id
            )
        overall_mean /= len(reviews)
        overall_mean = round(overall_mean, 4)
        # print(f"The overall mean rating is {overall_mean}")
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

        df["review"] = df["review"].replace(r"[^A-Za-z0-9 ]+", "", regex=True)
        df["review"] = df["review"].str.lower().apply(lambda x: filter_stopwords(x))

        # remove all special characters from combined_review
        df["combined_review"] = df["rating"].astype("string") + " " + df["review"]

        return df["combined_review"].to_list()

    def process_single_listing(self, reviews, listing_id):
        print(
            f"\nProcessing listing {listing_id}\n{self.num_completed_listings} of {self.number_of_listings_to_process}"
        )

        listing_mean_rating = self.get_listing_id_mean_rating(
            listing_id=listing_id, reviews=reviews
        )

        listing_ratings = self.get_listing_ratings_and_reviews(
            listing_id=listing_id, reviews=reviews
        )

        if (
            listing_ratings is None
            or len(listing_ratings) == 0
            or len(listing_ratings) < self.review_threshold
        ):
            print(
                f"No ratings found for listing {listing_id} or number under threshold; skipping."
            )
            return

        generated_prompt = load_json_file("prompt.json")["prompt"]

        updated_prompt = self.prompt_replacement(
            current_prompt=generated_prompt,
            listing_mean=str(listing_mean_rating),
            overall_mean=str(self.overall_mean),
        )
        reviews = self.clean_single_item_reviews(ratings=listing_ratings)

        self.weaviate_client.add_reviews_collection_batch(
            collection_name=self.collection_name,
            listing_id=listing_id,
            reviews=reviews,
        )

        summary = self.weaviate_client.generate_aggregate(
            id=listing_id,
            collection_name=self.collection_name,
            generate_prompt=updated_prompt,
            filter_field="product_id",
            return_properties=["review_text"],
        )

        self.weaviate_client.remove_collection_listings(
            listing_id=listing_id, collection_name=self.collection_name, reviews=reviews
        )

        return summary

    def filter_out_processed_reviews(
        self, reviews: dict, already_processed_reviews: dict
    ) -> dict:
        already_processed_reviews_ids = list(already_processed_reviews.keys())

        print(f"Already aggregated ids: {len(already_processed_reviews_ids)}")

        unprocessed_reviews = {
            x: y for x, y in reviews.items() if x not in already_processed_reviews_ids
        }

        print(f"Reviews to process after filtering: {len(unprocessed_reviews)}")

        return unprocessed_reviews

    def get_unfinished_aggregated_reviews(self, generated_summaries) -> list[str]:
        incomplete_keys = []
        for key, value in generated_summaries.items():
            if "?" in value:
                incomplete_keys.append(key)

        print(f"Listings needing more processing: {len(incomplete_keys)}")
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

        save_json_file(
            filename=f"results/generated_summaries_{self.zipcode}.json",
            data=generated_summaries,
        )
        return generated_summaries

    def rag_description_generation_chain(self):
        # Load reviews along with any existing aggregated summaries to determine what still needs processing
        reviews = load_json_file(filename=f"results/reviews_{self.zipcode}.json")
        print(f"Total reviews loaded: {len(reviews)}")

        self.overall_mean = self.get_overall_mean_rating(reviews=reviews)

        generated_summaries = load_json_file(
            filename=f"results/generated_summaries_{self.zipcode}.json"
        )
        print(f"Already processed reviews loaded: {len(generated_summaries)}")

        unprocessed_reviews = self.filter_out_processed_reviews(
            reviews=reviews, already_processed_reviews=generated_summaries
        )

        if not unprocessed_reviews:
            print("No unprocessed reviews found; exiting.")
            return

        unprocessed_reviews_ids = list(unprocessed_reviews.keys())
        print(f"Number of reviews to aggregate: {len(unprocessed_reviews_ids)}")

        self.number_of_listings_to_process = (
            self.adjust_list_length_upper_bound_for_config(
                unprocessed_reviews=unprocessed_reviews
            )
        )

        # First pass: process each unprocessed listing up to the configured limit
        for listing_id in unprocessed_reviews_ids[: self.number_of_listings_to_process]:
            generated_summaries[listing_id] = self.process_single_listing(
                reviews=unprocessed_reviews,
                listing_id=listing_id,
            )

            self.num_completed_listings += 1

            save_json_file(
                filename=f"results/generated_summaries_{self.zipcode}.json",
                data=generated_summaries,
            )

        # Second pass: Remove any listings that resulted in empty summaries
        generated_summaries = self.remove_empty_reviews(generated_summaries)

        # Third pass: Re-process any listings that resulted in incomplete summaries where the model indicated uncertainty
        self.review_ids_need_more_processing = self.get_unfinished_aggregated_reviews(
            generated_summaries
        )

        for listing_id in self.review_ids_need_more_processing:
            print(listing_id)
            generated_summaries[listing_id] = self.process_single_listing(
                reviews=reviews,
                listing_id=listing_id,
            )

            self.num_completed_listings += 1

            save_json_file(
                filename=f"results/generated_summaries_{self.zipcode}.json",
                data=generated_summaries,
            )
        print("RAG description generation chain completed.")
