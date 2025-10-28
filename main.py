import json
import sys
from scraper.scraper import airbnb_scraper
from review_aggregator.review_aggregator import RagDescription

if __name__ == "__main__":
    with open("config.json", "r") as f:
        config = json.load(f)
    zipcode = config.get("zipcode", "00501")
    iso_code = config.get("iso_code", "us")
    scrape_reviews = config.get("scrape_reviews", False)
    aggregate_reviews = config.get("agggregate_reviews", False)
    number_of_listings_to_process = config.get("number_of_listings_to_process", 3)

    print(f"Configuration loaded: {config}")

    if scrape_reviews:
        airbnb_scraper(
            zipcode=zipcode,
            iso_code=iso_code,
            num_listings=number_of_listings_to_process,
        )
        print(
            f"Scraping reviews for zipcode {zipcode} in country {iso_code} completed."
        )

    if aggregate_reviews:
        rag_description = RagDescription()
        rag_description.rag_description_generation_chain()
        print(
            f"Aggregating reviews for zipcode {zipcode} in country {iso_code} completed."
        )

    # Things to do
    # Aggregrate the aggreated reviews into a single review per zip code
    # Simple frontend gui for config selection (use streamlit)
    # Turn the scraped data into a table for users to look at manually
    # Store output in aws in s3
    # Create a readme with copilot once done
