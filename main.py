import json
import pandas as pd

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

    def get_number_of_listings_to_process(self, unprocessed_reviews: dict) -> int:
        # placeholder function to count the number of listing ids.
        return len(unprocessed_reviews)

    def get_listing_ratings_and_reviews(self, unprocessed_reviews: dict, listing_id: str) -> list:
        listing_ratings_and_reviews = unprocessed_reviews.get(listing_id)
        print(f"The type of listing_ratings_and_reviews is {type(listing_ratings_and_reviews)}")
        return listing_ratings_and_reviews

    def get_listing_id_mean_rating(self, listing_id) -> float:
        mean_rating = 0
        listing_data = self.get_listing_ratings_and_reviews(self.unprocessed_reviews, listing_id)
        for review in listing_data:
            mean_rating += review.get("rating")
        print(f"The mean rating for listing {listing_id} is {mean_rating}")
        return mean_rating

    def load_prompt(self):
        with open("prompt.json", "r") as f:
            data = json.load(f)
        return data["gpt4o_mini_generate_prompt_structured"]

    def prompt_replacement(
        self,
        current_prompt: str,
        listing_mean: str,
    ) -> str:
        # Add more replacements to fill out the entire prompt
        current_prompt = current_prompt.replace("{LISTING_AVERAGE_HERE}", listing_mean)
        return current_prompt

    def clean_single_item_reviews(self, ratings: dict) -> list:
        df = pd.DataFrame(ratings)[["rating", "review"]]

        #print(df)

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
        print(f"Reviews looks like this: {reviews[:5]} with type {type(reviews)}")

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

        weaviate_client.remove_collection_listings(
            listing_id=listing_id, collection_name=self.collection_name, reviews=reviews
        )

        return

    def rag_description_generation_chain(self):

        with open('reviews.json', 'r') as file:
            unprocessed_reviews = json.load(file)

        num_to_process = self.get_number_of_listings_to_process(unprocessed_reviews=unprocessed_reviews)

        generated_prompt = self.load_prompt()

        #print(f"Listings are of type {type(unprocessed_reviews)}")

        print(f"Number of listings to process: {num_to_process}")
        #print(f"Prompt to use: {generated_prompt}")

        print(list(unprocessed_reviews.keys())[0])

        weaviate_client = WeaviateClient()

        self.process_single_listing(weaviate_client=weaviate_client, listing_id=list(unprocessed_reviews.keys())[0], ratings=list(unprocessed_reviews.values())[0], generated_prompt=generated_prompt)
        
        
        """
        weaviate_client.create_reviews_collection(collection_name=self.collection_name)

        for listing_id in listing_ids[:1]:
            print(
                f"\nProcessing listing {listing_id}\n{self.num_completed_listings} of {num_to_process}"
            )

            listing_mean_rating = self.get_listing_id_mean_rating(listing_id)
            listing_ratings = self.get_listing_ratings_and_reviews(df, listing_id)

            updated_prompt = self.prompt_replacement(
                current_prompt=generated_prompt,
                listing_mean=str(listing_mean_rating),
            )

            self.process_single_listing(
                weaviate_client,
                listing_id,
                listing_ratings,
                updated_prompt,
            )

            self.num_completed_listings += 1

        weaviate_client.close_client()
        """

if __name__ == "__main__":
    rag_description = RagDescription()

    rag_description.rag_description_generation_chain()
