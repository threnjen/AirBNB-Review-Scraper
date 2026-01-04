import json
import sys
from scraper.reviews_scraper import airbnb_scraper
from scraper.details_scraper import airbnb_scraper as details_scraper
from review_aggregator.property_review_aggregator import PropertyRagAggregator
from review_aggregator.area_review_aggregator import AreaRagAggregator
from scraper.details_fileset_build import DetailsFilesetBuilder

if __name__ == "__main__":
    with open("config.json", "r") as f:
        config = json.load(f)
    zipcode = config.get("zipcode", "00501")
    iso_code = config.get("iso_code", "us")
    number_of_listings_to_process = config.get("number_of_listings_to_process", 3)
    review_threshold = config.get("review_threshold", 5)
    number_of_summaries_to_process = config.get("number_of_summaries_to_process", 3)

    print(f"Configuration loaded: {config}")

    if config.get("scrape_reviews", False):
        airbnb_scraper(
            zipcode=zipcode,
            iso_code=iso_code,
            num_listings=number_of_listings_to_process,
        )
        print(
            f"Scraping reviews for zipcode {zipcode} in country {iso_code} completed."
        )

    if config.get("scrape_details", False):
        details_scraper(
            zipcode=zipcode,
            iso_code=iso_code,
            num_listings=number_of_listings_to_process,
        )
        print(
            f"Scraping details for zipcode {zipcode} in country {iso_code} completed."
        )

    if config.get("build_details", False):
        fileset_builder = DetailsFilesetBuilder()
        fileset_builder.build_fileset()
        print("Building details fileset completed.")

    if config.get("aggregate_reviews", False):
        rag_description = PropertyRagAggregator(
            num_listings=number_of_listings_to_process,
            review_threshold=review_threshold,
            zipcode=zipcode,
        )
        rag_description.rag_description_generation_chain()
        print(
            f"Aggregating reviews for zipcode {zipcode} in country {iso_code} completed."
        )

    if config.get("aggregate_summaries", False):
        rag_description = AreaRagAggregator(
            num_listings=number_of_summaries_to_process,
            review_threshold=review_threshold,
            zipcode=zipcode,
            collection_name="Summaries",
        )
        rag_description.rag_description_generation_chain_summaries()
        print(
            f"Aggregating summaries for zipcode {zipcode} in country {iso_code} completed."
        )

    # Things to do
    # Aggregrate the aggreated reviews into a single review per zip code
    # Simple frontend gui for config selection (use streamlit)
    # Turn the scraped data into a table for users to look at manually
    # Store output in aws in s3
    # Create a readme with copilot once done
