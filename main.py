import json
import sys
import os

from scraper.reviews_scraper import scrape_reviews
from scraper.details_scraper import scrape_details
from scraper.airbnb_searcher import airbnb_searcher
from review_aggregator.property_review_aggregator import PropertyRagAggregator
from review_aggregator.area_review_aggregator import AreaRagAggregator
from review_aggregator.data_extractor import DataExtractor
from scraper.details_fileset_build import DetailsFilesetBuilder

import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class AirBnbReviewAggregator:
    def __init__(self):
        self.config = {}
        self.zipcode = "00000"
        self.iso_code = "us"
        self.num_listings_to_summarize = 3
        self.num_listings_to_search = 3
        self.review_thresh_to_include_prop = 5
        self.num_summary_to_process = 3
        self.use_custom_listings_file = False
        self.custom_filepath = ""
        self.scrape_reviews = False
        self.scrape_details = False
        self.build_details = False
        self.aggregate_reviews = False
        self.aggregate_summaries = False
        self.extract_data = False
        self.use_categoricals = False
        self.load_configs()
        logger.info(f"Configuration loaded: {self.config}")

    def load_configs(self):
        with open("config.json", "r") as f:
            self.config = json.load(f)
        self.zipcode = self.config.get("zipcode", "97067")
        self.iso_code = self.config.get("iso_code", "us")
        self.num_listings_to_search = self.config.get("num_listings_to_search", 3)
        self.num_listings_to_summarize = self.config.get("num_listings_to_summarize", 3)
        self.review_thresh_to_include_prop = self.config.get(
            "review_thresh_to_include_prop", 5
        )
        self.num_summary_to_process = self.config.get("num_summary_to_process", 3)

        self.use_custom_listings_file = self.config.get(
            "use_custom_listings_file", False
        )
        self.custom_filepath = self.config.get(
            "custom_filepath", "custom_listings.json"
        )
        self.scrape_reviews = self.config.get("scrape_reviews", False)
        self.scrape_details = self.config.get("scrape_details", False)
        self.build_details = self.config.get("build_details", False)
        self.aggregate_reviews = self.config.get("aggregate_reviews", False)
        self.aggregate_summaries = self.config.get("aggregate_summaries", False)
        self.extract_data = self.config.get("extract_data", False)
        self.use_categoricals = self.config.get("dataset_use_categoricals", False)

    def get_area_search_results(self):
        if self.use_custom_listings_file and os.path.isfile(self.custom_filepath):
            with open(self.custom_filepath, "r", encoding="utf-8") as f:
                property_ids = json.load(f).keys()
            logger.info(
                f"Using {len(property_ids)} custom listing IDs from custom_listing_ids.json"
            )
            search_results = []
            for room_id in property_ids:
                search_results.append({"room_id": room_id})
        elif os.path.isfile(
            f"property_search_results/search_results_{self.zipcode}.json"
        ):
            with open(
                f"property_search_results/search_results_{self.zipcode}.json",
                "r",
                encoding="utf-8",
            ) as f:
                search_results = json.load(f)
            logger.info(
                f"Loaded {len(search_results)} listings from existing search results file."
            )
        else:
            search_results = airbnb_searcher(self.zipcode, self.iso_code)
        logger.info(f"Search results data looks like: {search_results[:1]}")
        return search_results

    def run_tasks_from_config(self):
        if self.scrape_reviews:
            search_results = self.get_area_search_results()
            scrape_reviews(
                zipcode=self.zipcode,
                search_results=search_results,
                num_listings=self.num_listings_to_search,
            )
            logger.info(
                f"Scraping reviews for zipcode {self.zipcode} in country {self.iso_code} completed."
            )

        if self.scrape_details:
            search_results = self.get_area_search_results()
            scrape_details(
                search_results=search_results,
                num_listings=self.num_listings_to_search,
            )
            logger.info(
                f"Scraping details for zipcode {self.zipcode} in country {self.iso_code} completed."
            )

        if self.build_details:
            fileset_builder = DetailsFilesetBuilder(
                use_categoricals=self.use_categoricals
            )
            fileset_builder.build_fileset()
            logger.info("Building details fileset completed.")

        if self.aggregate_reviews:
            rag_property = PropertyRagAggregator(
                num_listings_to_summarize=self.num_listings_to_summarize,
                review_thresh_to_include_prop=self.review_thresh_to_include_prop,
                zipcode=self.zipcode,
            )
            rag_property.rag_description_generation_chain()
            logger.info(
                f"Aggregating reviews for zipcode {self.zipcode} in country {self.iso_code} completed."
            )

        if self.aggregate_summaries:
            rag_area = AreaRagAggregator(
                num_listings=self.num_summary_to_process,
                review_thresh_to_include_prop=self.review_thresh_to_include_prop,
                zipcode=self.zipcode,
            )
            rag_area.rag_description_generation_chain()
            logger.info(
                f"Aggregating area summary for zipcode {self.zipcode} completed."
            )

        if self.extract_data:
            extractor = DataExtractor(zipcode=self.zipcode)
            extractor.run_extraction()
            logger.info(f"Data extraction for zipcode {self.zipcode} completed.")

        # Things to do
        # Aggregrate the aggreated reviews into a single review per zip code
        # Simple frontend gui for config selection (use streamlit)
        # Turn the scraped data into a table for users to look at manually
        # Store output in aws in s3
        # Create a readme with copilot once done


if __name__ == "__main__":
    aggregator = AirBnbReviewAggregator()
    aggregator.run_tasks_from_config()
