import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from review_aggregator.weaviate_client import WeaviateClient



class PropertyDataExtraction(BaseModel):
    review_threshold: int = 5
    num_listings: int = 3
    model_config = ConfigDict(arbitrary_types_allowed=True)
    num_completed_listings: int = 0
    num_overall_ids: int = 100
    collection_name: str = "Reviews"
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
        pass

    def open_config(self):
        with open("config.json", "r") as f:
            config = json.load(f)
        return config
