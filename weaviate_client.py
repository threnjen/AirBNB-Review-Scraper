import os

import pandas as pd
import weaviate
import weaviate.classes as wvc
from pydantic import BaseModel, ConfigDict, SkipValidation

# from weaviate.classes.config import Configure
from weaviate.classes.query import Filter
from weaviate.util import generate_uuid5

IS_LOCAL = True if os.environ.get("IS_LOCAL", "True").lower() == "true" else False


class WeaviateClient(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    weaviate_client: SkipValidation[weaviate.Client] = None
    ec2: bool = False

    def model_post_init(self, __context):
        self.weaviate_client = self.connect_weaviate_client_docker()

    def connect_weaviate_client_docker(self) -> weaviate.client:
        if not IS_LOCAL:
            client = weaviate.connect_to_local(
                host="127.0.0.1",
                port=8081,
                grpc_port=50051,
                headers={
                    "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"],
                },
            )
            print("\nConnected to Weaviate instance on Fargate ECS")
            return client

        print("\nConnected to Weaviate instance on local machine")
        return weaviate.connect_to_local(
            port=8081,
            headers={
                "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"],
            },
        )

    def check_collection_exists(self, collection_name: str, reset: bool = True) -> bool:
        if self.weaviate_client.collections.exists(collection_name):
            print(f"Collection {collection_name} already exists for this block")
            if reset:
                self.weaviate_client.collections.delete(collection_name)
                print(f"Deleted and recreating collection {collection_name}")
                return False
            return True

    def create_reviews_collection(self, collection_name: str, reset: bool = True):
        if not self.check_collection_exists(collection_name, reset):
            self.weaviate_client.collections.create(
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_transformers(),
                name=collection_name,
                generative_config=wvc.config.Configure.Generative.openai(
                    model="gpt-4o-mini"
                ),
                properties=[
                    wvc.config.Property(
                        name="review_text",
                        data_type=wvc.config.DataType.TEXT,
                        vectorize_property_name=False,
                    ),
                    wvc.config.Property(
                        name="product_id",
                        data_type=wvc.config.DataType.TEXT,
                        skip_vectorization=True,
                        vectorize_property_name=False,
                    ),
                ],
            )

    def add_reviews_collection_batch(
        self,
        listing_id: str,
        collection_name: str,
        reviews: list[str],
    ) -> None:
        print(f"Adding reviews for item {listing_id}")
        collection = self.weaviate_client.collections.get(collection_name)

        with collection.batch.dynamic() as batch:
            for review in reviews:
                # print(f"Review looks like {review}")
                # print(f"Listing ID is {listing_id}")
                review_item = {
                    "review_text": review,
                    "product_id": listing_id,
                }
                # print(f"Review item is {review_item}")
                uuid = generate_uuid5(review_item)

                if collection.data.exists(uuid):
                    print("Gobbledeegook")
                    continue

                result = batch.add_object(properties=review_item, uuid=uuid)

                if "error" in result:
                    print(f"Failed to insert {uuid}: {result['error']}")
                else:
                    # print(f"Inserted review with uuid={uuid}")
                    pass

        print(f"Reviews added for item {listing_id}")

    def verify_reviews(self, collection_name: str, listing_id: str):
        collection = self.weaviate_client.collections.get(collection_name)

        # Fetch reviews that belong to this product
        results = collection.query.fetch_objects(
            filters=wvc.query.Filter.by_property("product_id").equal(listing_id),
            limit=10,  # you can increase this if needed
            include_vector=True,
        )

        print(f"Found {len(results.objects)} reviews for listing {listing_id}:")
        for obj in results.objects:
            print(obj.properties)
            print(obj.vector)

    def remove_collection_listings(
        self,
        listing_id: str,
        collection_name: str,
        reviews: list[str],
    ) -> None:
        collection = self.weaviate_client.collections.get(collection_name)

        print(f"Removing embeddings for item {listing_id}")

        for review in reviews:
            review_item = {
                "review_text": review,
                "product_id": listing_id,
            }
            uuid = generate_uuid5(review_item)

            if collection.data.exists(uuid):
                collection.data.delete_by_id(uuid=uuid)

    def generate_aggregated_review(
        self,
        listing_id: str,
        collection_name: str,
        generate_prompt: str,
    ) -> str:
        print(f"Generating aggregated review for item {listing_id}")

        try:
            collection = self.weaviate_client.collections.get(collection_name)
        except Exception as e:
            print(f"Failed to get collection '{collection_name}': {e}")
            return ""

        try:
            summary = collection.generate.near_text(
                query="aggregate_review",
                limit=1000,  # how many reviews to consider
                return_properties=["review_text", "product_id"],
                filters=Filter.by_property("product_id").equal(listing_id),
                grouped_task=generate_prompt,
            )
        except Exception as e:
            print(f"Error during generate.near_text(): {e}")

        print(f"Summary looks like this: {summary}")
        print(f"Summary type is {type(summary)}")

        # Ensure we got results back
        if not summary.objects:
            print("No reviews found for this listing.")

        if not getattr(summary, "generated", None):
            print("No aggregated summary was generated.")

        # Debugging: show what we used
        # print("Retrieved review snippets:")
        # for obj in summary.objects:
        #     print("-", obj.properties.get("review_text"))

        print("\nGenerated summary:")

        print(f"Generated summary for item {listing_id}: {summary.generated}")

        # for attribute in dir(summary):
        #     if not attribute.startswith("objects") and not attribute.startswith("__dict__"):
        #         print(f"{attribute}: {getattr(summary, attribute)}")

        return summary

    def close_client(self):
        self.weaviate_client.close()
