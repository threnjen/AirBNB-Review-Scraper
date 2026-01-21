import os

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

    # def model_post_init(self, __context):
    #     self.weaviate_client = self.connect_weaviate_client()

    def connect_weaviate_client(self) -> weaviate.client:
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
            # logger.info("Connected to Weaviate instance on Fargate ECS")
            return client

        # logger.info("Connected to Weaviate instance on local machine")
        return weaviate.connect_to_local(
            port=8080,
            grpc_port=50051,
            headers={
                "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"],
            },
            additional_config=AdditionalConfig(
                timeout=Timeout(init=60, query=600, insert=600)  # Values in seconds
            ),
        )

    def check_collection_exists(self, collection_name: str, reset: bool = True) -> bool:
        weaviate_client = self.connect_weaviate_client()
        if weaviate_client.collections.exists(collection_name):
            logger.info(f"Collection {collection_name} already exists for this block")
            if reset:
                weaviate_client.collections.delete(collection_name)
                logger.info(f"Deleted and recreating collection {collection_name}")
                weaviate_client.close()
                return False
            weaviate_client.close()
            return True
        weaviate_client.close()
        return False

    def create_general_collection(
        self,
        collection_name: str,
        reset: bool = True,
        incoming_properties: list[dict] = None,
    ):
        weaviate_client = self.connect_weaviate_client()
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
            weaviate_client = self.connect_weaviate_client()
            weaviate_client.collections.create(
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_transformers(),
                name=collection_name,
                properties=properties_list,
            )
            weaviate_client.close()

    def add_collection_batch(
        self,
        listing_id: str,
        collection_name: str,
        items: list[str],
        property_name: str = "review_text",
    ) -> None:
        weaviate_client = self.connect_weaviate_client()
        collection = weaviate_client.collections.get(collection_name)

        with collection.batch.dynamic() as batch:
            for item in items:
                obj = {
                    property_name: item,
                    "product_id": listing_id,
                }
                uuid = generate_uuid5(obj)
                result = batch.add_object(properties=obj, uuid=uuid)
                if "error" in result:
                    logger.info(f"Failed to insert {uuid}: {result['error']}")

        weaviate_client.close()

    def remove_collection_listings(
        self,
        listing_id: str,
        collection_name: str,
        items: list[str],
        property_name: str = "review_text",
    ) -> None:
        weaviate_client = self.connect_weaviate_client()
        collection = weaviate_client.collections.get(collection_name)

        for item in items:
            obj = {
                property_name: item,
                "product_id": listing_id,
            }
            uuid = generate_uuid5(obj)
            if collection.data.exists(uuid):
                collection.data.delete_by_id(uuid=uuid)

        weaviate_client.close()

    def generate_aggregate(
        self,
        id: str,
        collection_name: str,
        generate_prompt: str,
        filter_field: str,
        return_properties: list[str] = [],
    ) -> str:
        logger.info(f"Generating aggregate for item {id}")

        weaviate_client = self.connect_weaviate_client()

        try:
            collection = weaviate_client.collections.get(collection_name)
            collection.config.update(
                generative_config=Configure.Generative.openai(
                    model="gpt-5-nano"  # pick any supported model
                )
            )
        except Exception as e:
            logger.info(f"Failed to get collection '{collection_name}': {e}")
            weaviate_client.close()
            return ""

        try:
            aggregate = collection.generate.fetch_objects(
                filters=Filter.by_property(filter_field).equal(id),
                return_properties=return_properties,
                grouped_task=generate_prompt,
                limit=1000,
            )
            logger.info(f"Aggregate is {aggregate} of type {type(aggregate)}")

            if not aggregate.objects:
                logger.info("No objects found for this id.")
                weaviate_client.close()
                return ""

            if not getattr(aggregate, "generated", None):
                logger.info("No aggregate was generated.")
                weaviate_client.close()
                return ""

            logger.info(f"Generated aggregate for item {id}: {aggregate.generated}")

            weaviate_client.close()

            return aggregate.generated
        except Exception as e:
            logger.info(f"Error during generate.fetch_objects(): {e}")
            weaviate_client.close()
            return ""
