import os

import pandas as pd
import json
import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Configure
from pydantic import BaseModel, ConfigDict, SkipValidation
from weaviate.classes.init import AdditionalConfig, Timeout

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
                port=8080,
                # grpc_port=50051,
                grpc_port=None,
                headers={
                    "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"],
                },
                timeout_config=(
                    30,
                    1200,
                ),
            )
            print("\nConnected to Weaviate instance on Fargate ECS")
            return client

        print("\nConnected to Weaviate instance on local machine")
        return weaviate.connect_to_local(
            port=8080,
            headers={
                "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"],
            },
            additional_config=AdditionalConfig(
                timeout=Timeout(init=30, query=600, insert=600)  # Values in seconds
            ),
        )

    def check_collection_exists(self, collection_name: str, reset: bool = True) -> bool:
        if self.weaviate_client.collections.exists(collection_name):
            print(f"Collection {collection_name} already exists for this block")
            if reset:
                self.weaviate_client.collections.delete(collection_name)
                print(f"Deleted and recreating collection {collection_name}")
                return False
            return True

    def create_general_collection(
        self,
        collection_name: str,
        reset: bool = True,
        incoming_properties: list[dict] = None,
    ):
        if not self.check_collection_exists(collection_name, reset):
            properties_list = []

            for prop in incoming_properties:
                properties_list.append(
                    wvc.config.Property(
                        name=prop["name"],
                        data_type=prop["data_type"],
                        vectorize_property_name=prop.get(
                            "vectorize_property_name", False
                        ),
                        skip_vectorization=prop.get("skip_vectorization", False),
                    )
                )

            self.weaviate_client.collections.create(
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_transformers(),
                name=collection_name,
                properties=properties_list,
            )

    def add_reviews_collection_batch(
        self,
        listing_id: str,
        collection_name: str,
        reviews: list[str],
    ) -> None:
        print(f"Adding reviews for item {listing_id}")
        collection = self.weaviate_client.collections.get(collection_name)
        print(f"Using collection {collection_name}")

        with collection.batch.dynamic() as batch:
            for review in reviews:
                review_item = {
                    "review_text": review,
                    "product_id": listing_id,
                }
                uuid = generate_uuid5(review_item)

                result = batch.add_object(properties=review_item, uuid=uuid)

                if "error" in result:
                    print(f"Failed to insert {uuid}: {result['error']}")
                else:
                    # print(f"Inserted review with uuid={uuid}")
                    pass

        print(f"Reviews added for item {listing_id}")

    # def verify_reviews(self, collection_name: str, listing_id: str):
    #     collection = self.weaviate_client.collections.get(collection_name)

    #     # Fetch reviews that belong to this product
    #     results = collection.query.fetch_objects(
    #         filters=wvc.query.Filter.by_property("product_id").equal(listing_id),
    #         limit=10,  # you can increase this if needed
    #         include_vector=True,
    #     )

    #     print(f"Found {len(results.objects)} reviews for listing {listing_id}:")
    #     for obj in results.objects:
    #         # print(obj.properties)
    #         # print(obj.vector)
    #         pass

    def remove_collection_listings(
        self,
        listing_id: str,
        collection_name: str,
        reviews: list[str],
    ) -> None:
        collection = self.weaviate_client.collections.get(collection_name)

        # print(f"Removing embeddings for item {listing_id}")

        for review in reviews:
            review_item = {
                "review_text": review,
                "product_id": listing_id,
            }
            uuid = generate_uuid5(review_item)

            if collection.data.exists(uuid):
                collection.data.delete_by_id(uuid=uuid)

    def generate_aggregate(
        self,
        id: str,
        collection_name: str,
        generate_prompt: str,
        filter_field: str,
        return_properties: list[str] = [],
    ) -> str:
        print(f"Generating aggregate for item {id}")

        try:
            collection = self.weaviate_client.collections.get(collection_name)
            collection.config.update(
                generative_config=Configure.Generative.openai(
                    model="gpt-5-nano"  # pick any supported model
                )
            )
        except Exception as e:
            print(f"Failed to get collection '{collection_name}': {e}")
            return ""

        objs = collection.query.fetch_objects(
            filters=Filter.by_property(filter_field).equal(id),
            return_properties=return_properties,
        )

        print(f"Successfully retrieved total of {len(objs.objects)} items")

        # test_fetch = collection.generate.fetch_objects(
        #     filters=Filter.by_property(filter_field).equal(id),
        #     return_properties=return_properties,
        #     grouped_task="Summarize these in one sentence.",
        #     limit=3,
        # )
        # print(f"\nSuccessfully summarized 3 items: {test_fetch.generated}")

        # test_fetch = collection.generate.fetch_objects(
        #     filters=Filter.by_property(filter_field).equal(id),
        #     return_properties=return_properties,
        #     grouped_task="Summarize these in one sentence.",
        #     limit=25,
        # )
        # print(f"\nSuccessfully summarized 25 items: {test_fetch.generated}")

        # print(f"\n{generate_prompt}")

        try:
            aggregate = collection.generate.fetch_objects(
                filters=Filter.by_property(filter_field).equal(id),
                return_properties=return_properties,
                grouped_task=generate_prompt,
                limit=1000,
            )
        except Exception as e:
            print(f"Error during generate.fetch_objects(): {e}")

        print(f"Aggregate is {aggregate} of type {type(aggregate)}")

        if not aggregate.objects:
            print("No objects found for this id.")

        if not getattr(aggregate, "generated", None):
            print("No aggregate was generated.")

        print(f"Generated aggregate for item {id}: {aggregate.generated}")

        return aggregate

    def close_client(self):
        self.weaviate_client.close()
