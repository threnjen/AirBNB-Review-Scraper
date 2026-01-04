import json
import pandas as pd
import weaviate.classes as wvc

from pydantic import BaseModel, ConfigDict

from review_aggregator.weaviate_client import WeaviateClient

from utils.nlp_functions import filter_stopwords


class RagDescription(BaseModel):
    review_threshold: int = 5
    num_listings: int = 3
    model_config = ConfigDict(arbitrary_types_allowed=True)
    num_completed_listings: int = 0
    num_overall_ids: int = 100
    collection_name: str = "Reviews"
    overall_stats: dict = {}
    listing_ids: list = []
    generate_prompt: str = "None"
    weaviate: WeaviateClient = None
    zipcode: str = "00501"

    def open_config(self):
        with open("config.json", "r") as f:
            config = json.load(f)
        return config

    def get_number_of_listings_to_process(self, unprocessed_reviews: dict) -> int:
        # placeholder function to count the number of listing ids.
        total_listings = len(unprocessed_reviews)
        if self.num_listings < total_listings:
            listings_to_process = self.num_listings
        else:
            listings_to_process = total_listings

        return listings_to_process

    def get_listing_ratings_and_reviews(
        self, unprocessed_reviews: dict, listing_id: str
    ) -> list:
        listing_ratings_and_reviews = unprocessed_reviews.get(listing_id)
        return listing_ratings_and_reviews

    def get_listing_id_mean_rating(self, unprocessed_reviews, listing_id) -> float:
        mean_rating = 0
        listing_data = self.get_listing_ratings_and_reviews(
            unprocessed_reviews, listing_id
        )
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

    def get_overall_mean_rating(self, unprocessed_reviews: dict) -> float:
        overall_mean = 0
        for listing_id in unprocessed_reviews:
            overall_mean += self.get_listing_id_mean_rating(
                unprocessed_reviews=unprocessed_reviews, listing_id=listing_id
            )
        overall_mean /= len(unprocessed_reviews)
        overall_mean = round(overall_mean, 4)
        # print(f"The overall mean rating is {overall_mean}")
        return overall_mean

    def load_prompt(self, prompt):
        try:
            with open(prompt, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompt file {prompt} not found.")
        return data["gpt4o_mini_generate_prompt_structured"]

    def load_zipcode_prompt(self):
        with open("zipcode_prompt.json", "r") as f:
            data = json.load(f)
        return data["prompt_zipcode"]

    def prompt_replacement(
        self,
        current_prompt: str,
        listing_mean: str,
        overall_mean: str,
    ) -> str:
        # Add more replacements to fill out the entire prompt
        current_prompt = current_prompt.replace("{ZIP_CODE_HERE}", self.zipcode)
        current_prompt = current_prompt.replace(
            "{ISO_CODE_HERE}", self.open_config().get("iso_code", "us")
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

    def process_single_listing(
        self,
        weaviate_client: WeaviateClient,
        listing_id: str,
        ratings: dict,
        generated_prompt: str,
    ):
        reviews = self.clean_single_item_reviews(ratings=ratings)

        weaviate_client.add_collection_batch(
            collection_name=self.collection_name,
            listing_id=listing_id,
            items=reviews,
        )

        summary = weaviate_client.generate_aggregate(
            id=listing_id,
            collection_name=self.collection_name,
            generate_prompt=generated_prompt,
            filter_field="product_id",
            return_properties=["review_text"],
        )

        weaviate_client.remove_collection_listings(
            listing_id=listing_id, collection_name=self.collection_name, items=reviews
        )

        return summary

    def rag_description_generation_chain_reviews(self):
        with open(f"results/reviews_{self.zipcode}.json", "r") as file:
            unprocessed_reviews = json.load(file)

        try:
            existing_file = open(
                f"results/generated_summaries_{self.zipcode}.json"
            ).read()
            already_aggregated = json.loads(existing_file)
        except FileNotFoundError:
            already_aggregated = {}

        print(f"Total reviews loaded: {len(unprocessed_reviews)}")

        already_aggregated_ids = list(already_aggregated.keys())

        print(f"Already aggregated ids: {len(already_aggregated_ids)}")

        unprocessed_reviews = {
            x: y
            for x, y in unprocessed_reviews.items()
            if x not in already_aggregated_ids
        }

        print(f"Reviews to process after filtering: {len(unprocessed_reviews)}")

        listings_to_process = self.get_number_of_listings_to_process(
            unprocessed_reviews=unprocessed_reviews
        )

        generated_prompt = self.load_prompt(prompt="zipcode_prompt.json")

        weaviate_client = WeaviateClient()

        overall_mean = self.get_overall_mean_rating(
            unprocessed_reviews=unprocessed_reviews
        )

        unprocessed_reviews_ids = list(unprocessed_reviews.keys())

        weaviate_properties = [
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
        ]

        weaviate_client.create_general_collection(
            collection_name=self.collection_name,
            incoming_properties=weaviate_properties,
        )

        try:
            existing_file = open(
                f"results/generated_summaries_{self.zipcode}.json"
            ).read()
            generated_summaries = json.loads(existing_file)
        except FileNotFoundError:
            generated_summaries = {}

        for listing_id in unprocessed_reviews_ids[:listings_to_process]:
            # print(f"Listing id is {listing_id} of type {type(listing_id)}")

            print(
                f"\nProcessing listing {listing_id}\n{self.num_completed_listings} of {listings_to_process}"
            )

            listing_mean_rating = self.get_listing_id_mean_rating(
                listing_id=listing_id, unprocessed_reviews=unprocessed_reviews
            )
            # print(listing_mean_rating)

            listing_ratings = self.get_listing_ratings_and_reviews(
                listing_id=listing_id, unprocessed_reviews=unprocessed_reviews
            )

            if (
                listing_ratings is None
                or len(listing_ratings) == 0
                or len(listing_ratings) < self.review_threshold
            ):
                print(
                    f"No ratings found for listing {listing_id} or number under threshold; skipping."
                )
                self.num_completed_listings += 1
                continue

            updated_prompt = self.prompt_replacement(
                current_prompt=generated_prompt,
                listing_mean=str(listing_mean_rating),
                overall_mean=str(overall_mean),
            )

            generated_summaries[listing_id] = self.process_single_listing(
                weaviate_client,
                listing_id,
                listing_ratings,
                updated_prompt,
            )

            self.num_completed_listings += 1

            with open(
                f"results/generated_summaries_{self.zipcode}.json",
                "w",
                encoding="utf-8",
            ) as f:
                f.write(json.dumps(generated_summaries, ensure_ascii=False))

    def rag_description_generation_chain_summaries(self):
        with open(f"results/generated_summaries_{self.zipcode}.json", "r") as file:
            unprocessed_summaries = json.load(file)

        generated_prompt = self.load_prompt(prompt="review_summary_prompt.json")

        weaviate_client = WeaviateClient()

        weaviate_properties = [
            {
                "name": "summary_text",
                "data_type": wvc.config.DataType.TEXT,
                "vectorize_property_name": False,
            },
            {
                "name": "product_id",
                "data_type": wvc.config.DataType.TEXT,
                "skip_vectorization": True,
                "vectorize_property_name": False,
            },
        ]
        weaviate_client.create_general_collection(
            collection_name=self.collection_name,
            incoming_properties=weaviate_properties,
        )

        # Add each summary into the collection so generate_aggregate can find them.
        # Use a shared product_id value ("summary_aggregate") so the generate call
        # can filter by that id and aggregate all summaries together.

        print(
            f"Unprocessed summaries looks like {unprocessed_summaries} of type {type(unprocessed_summaries)}"
        )

        summary_items = []
        for listing_id, summary_text in unprocessed_summaries.items():
            summary_items.append(summary_text)

        if summary_items:
            weaviate_client.add_collection_batch(
                listing_id="summary_aggregate",
                collection_name=self.collection_name,
                items=summary_items,
                property_name="summary_text",
            )

        generated_summary = weaviate_client.generate_aggregate(
            id="summary_aggregate",
            collection_name=self.collection_name,
            generate_prompt=generated_prompt,
            filter_field="product_id",
            return_properties=["summary_text"],
        )

        # optional: remove the inserted summary objects after aggregation
        weaviate_client.remove_collection_listings(
            listing_id="summary_aggregate",
            collection_name=self.collection_name,
            items=summary_items,
            property_name="summary_text",
        )

        aggregated_summary = {}
        aggregated_summary["aggregated_summary"] = generated_summary

        with open(
            f"results/aggregated_summary_{self.zipcode}.json",
            "w",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(aggregated_summary, ensure_ascii=False))
