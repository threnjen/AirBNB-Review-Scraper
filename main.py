import json
import pandas as pd
import os
import datetime

from pydantic import BaseModel, ConfigDict

from weaviate_client import WeaviateClient

from utils.nlp_functions import filter_stopwords


class RagDescription(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    num_completed_listings: int = 0
    num_overall_ids: int = 100
    collection_name: str = "reviews"
    overall_stats: dict = {}
    listing_ids: list = []
    generate_prompt: str = "None"
    weaviate: WeaviateClient = None

    def open_config(self):
        with open("config.json", "r") as f:
            config = json.load(f)
        return config

    def get_number_of_listings_to_process(self, unprocessed_reviews: dict) -> int:
        # placeholder function to count the number of listing ids.
        return len(unprocessed_reviews)

    def get_listing_ratings_and_reviews(
        self, unprocessed_reviews: dict, listing_id: str
    ) -> list:
        listing_ratings_and_reviews = unprocessed_reviews.get(listing_id)
        # print(f"The type of listing_ratings_and_reviews is {type(listing_ratings_and_reviews)}")
        return listing_ratings_and_reviews

    def get_listing_id_mean_rating(self, unprocessed_reviews, listing_id) -> float:
        mean_rating = 0
        listing_data = self.get_listing_ratings_and_reviews(
            unprocessed_reviews, listing_id
        )
        for review in listing_data:
            # print(f"Review is equal to {review}")
            if review.get("rating") is None:
                # print(f"Review {review} has no rating, skipping.")
                pass
            else:
                mean_rating += review.get("rating")
        # print(f"Listing data is of type {type(listing_data)} with length {len(listing_data)}")
        if len(listing_data) > 0:
            mean_rating /= len(listing_data)
            mean_rating = round(mean_rating, 4)
        else:
            # print(f"No reviews found for listing {listing_id}")
            mean_rating = 0
        # print(f"The mean rating for listing {listing_id} is {mean_rating}")
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

    def load_prompt(self):
        with open("prompt.json", "r") as f:
            data = json.load(f)
        return data["gpt4o_mini_generate_prompt_structured"]
    
    def load_zipcode_prompt(self):
        with open("zipcode_prompt.json", "r") as f:
            data = json.load(f)
        return data["gpt4o_mini_generate_prompt_structured_zipcode"]

    def prompt_replacement(
        self,
        current_prompt: str,
        listing_mean: str,
        overall_mean: str,
    ) -> str:
        # Add more replacements to fill out the entire prompt
        current_prompt = current_prompt.replace("{ZIP_CODE_HERE}", self.open_config().get("zipcode", "00501"))
        current_prompt = current_prompt.replace("{ISO_CODE_HERE}", self.open_config().get("iso_code", "us"))
        current_prompt = current_prompt.replace("{RATING_AVERAGE_HERE}", listing_mean)
        current_prompt = current_prompt.replace("{OVERALL_MEAN}", overall_mean)
        return current_prompt

    def clean_single_item_reviews(self, ratings: dict) -> list:
        # print(f"Ratings is {ratings} with type {type(ratings)}")
        df = pd.DataFrame(ratings)[["rating", "review"]]

        # print(df)

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
        # print(f"Reviews looks like this: {reviews[:2]} with type {type(reviews)}")

        weaviate_client.add_reviews_collection_batch(
            collection_name=self.collection_name,
            listing_id=listing_id,
            reviews=reviews,
        )

        summary = weaviate_client.generate_aggregated_review(
            listing_id=listing_id,
            collection_name=self.collection_name,
            generate_prompt=generated_prompt,
        )

        # weaviate_client.verify_reviews(
        #     collection_name=self.collection_name, listing_id=listing_id
        # )

        weaviate_client.remove_collection_listings(
            listing_id=listing_id, collection_name=self.collection_name, reviews=reviews
        )

        # print(f"The summary is {summary.generated}")

        # print(f"My api key is {os.environ['OPENAI_API_KEY']}")

        return summary.generated

    def rag_description_generation_chain(self):
        with open(f"reviews_{self.open_config().get("zipcode", "00501")}.json", "r") as file:
            unprocessed_reviews = json.load(file)

        num_to_process = self.get_number_of_listings_to_process(
            unprocessed_reviews=unprocessed_reviews
        )

        generated_prompt = self.load_prompt()

        # print(f"Listings are of type {type(unprocessed_reviews)}")

        # print(f"Number of listings to process: {num_to_process}")
        # print(f"Prompt to use: {generated_prompt}")

        # print(list(unprocessed_reviews.keys())[0])

        weaviate_client = WeaviateClient()

        overall_mean = self.get_overall_mean_rating(
            unprocessed_reviews=unprocessed_reviews
        )

        # self.process_single_listing(weaviate_client=weaviate_client, listing_id=list(unprocessed_reviews.keys())[0], ratings=list(unprocessed_reviews.values())[0], generated_prompt=generated_prompt)

        unprocessed_reviews_ids = list(unprocessed_reviews.keys())

        weaviate_client.create_reviews_collection(collection_name=self.collection_name)

        generated_summaries = {}

        for listing_id in unprocessed_reviews_ids[0:10]:
            # print(f"Listing id is {listing_id} of type {type(listing_id)}")

            print(
                f"\nProcessing listing {listing_id}\n{self.num_completed_listings} of {num_to_process}"
            )

            listing_mean_rating = self.get_listing_id_mean_rating(
                listing_id=listing_id, unprocessed_reviews=unprocessed_reviews
            )
            # print(listing_mean_rating)

            listing_ratings = self.get_listing_ratings_and_reviews(
                listing_id=listing_id, unprocessed_reviews=unprocessed_reviews
            )

            if listing_ratings is None or len(listing_ratings) == 0:
                print(f"No ratings found for listing {listing_id}, skipping.")
                continue

            # cleaned_ratings = self.clean_single_item_reviews(ratings=listing_ratings)
            # print(cleaned_ratings[:1])

            updated_prompt = self.prompt_replacement(
                current_prompt=generated_prompt,
                listing_mean=str(listing_mean_rating),
                overall_mean=str(overall_mean),
                # cleaned_ratings=cleaned_ratings,
            )
            # print(updated_prompt)
            
            generated_summaries[listing_id] = self.process_single_listing(
                weaviate_client,
                listing_id,
                listing_ratings,
                updated_prompt,
            )

            self.num_completed_listings += 1

        with open(f"generated_summaries_{datetime.datetime.now().strftime("%Y%m%d%H%M")}.json", "w", encoding="utf-8") as f:
            f.write(
                json.dumps(generated_summaries, ensure_ascii=False)
            )

        weaviate_client.close_client()


if __name__ == "__main__":
    rag_description = RagDescription()

    rag_description.rag_description_generation_chain()
