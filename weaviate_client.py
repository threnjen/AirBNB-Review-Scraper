import os

import pandas as pd
import weaviate
import weaviate.classes as wvc
from pydantic import BaseModel, ConfigDict

# from weaviate.classes.config import Configure
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.util import generate_uuid5

IS_LOCAL = True if os.environ.get("IS_LOCAL", "True").lower() == "true" else False


class WeaviateClient(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    weaviate_client: weaviate.client = None
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
                name=collection_name,
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_transformers(),
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
                review_item = {
                    "review_text": review,
                    "product_id": listing_id,
                }
                uuid = generate_uuid5(review_item)

                if collection.data.exists(uuid):
                    continue
                else:
                    batch.add_object(properties=review_item, uuid=uuid)

        print(f"Reviews added for item {listing_id}")

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

        collection = self.weaviate_client.collections.get(collection_name)

        summary = collection.generate.near_text(
            query="aggregate_review",
            return_properties=["review_text", "product_id"],
            filters=Filter.by_property("product_id").equal(listing_id),
            grouped_task=generate_prompt,
        )
        return summary

    def close_client(self):
        self.weaviate_client.close()
