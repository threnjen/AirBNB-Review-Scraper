import glob
import json
import logging
import os
import sys

from review_aggregator.area_review_aggregator import AreaRagAggregator
from review_aggregator.correlation_analyzer import CorrelationAnalyzer
from review_aggregator.data_extractor import DataExtractor
from review_aggregator.description_analyzer import DescriptionAnalyzer
from review_aggregator.property_review_aggregator import PropertyRagAggregator
from scraper.airbnb_searcher import airbnb_searcher
from scraper.airdna_scraper import AirDNAScraper
from scraper.details_fileset_build import DetailsFilesetBuilder
from scraper.details_scraper import scrape_details
from scraper.reviews_scraper import scrape_reviews

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
        self.scrape_reviews = False
        self.scrape_details = False
        self.build_details = False
        self.aggregate_reviews = False
        self.aggregate_summaries = False
        self.extract_data = False
        self.analyze_correlations = False
        self.analyze_descriptions = False
        self.scrape_airdna = False
        self.airdna_comp_set_ids = []
        self.airdna_cdp_url = "http://localhost:9222"
        self.airdna_inspect_mode = False
        self.correlation_metrics = ["adr", "occupancy"]
        self.correlation_top_percentile = 25
        self.correlation_bottom_percentile = 25
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

        self.scrape_reviews = self.config.get("scrape_reviews", False)
        self.scrape_details = self.config.get("scrape_details", False)
        self.build_details = self.config.get("build_details", False)
        self.aggregate_reviews = self.config.get("aggregate_reviews", False)
        self.aggregate_summaries = self.config.get("aggregate_summaries", False)
        self.extract_data = self.config.get("extract_data", False)
        self.analyze_correlations = self.config.get("analyze_correlations", False)
        self.analyze_descriptions = self.config.get("analyze_descriptions", False)
        self.scrape_airdna = self.config.get("scrape_airdna", False)
        self.airdna_comp_set_ids = self.config.get("airdna_comp_set_ids", [])
        self.airdna_cdp_url = self.config.get("airdna_cdp_url", "http://localhost:9222")
        self.airdna_inspect_mode = self.config.get("airdna_inspect_mode", False)
        self.correlation_metrics = self.config.get(
            "correlation_metrics", ["adr", "occupancy"]
        )
        self.correlation_top_percentile = self.config.get(
            "correlation_top_percentile", 25
        )
        self.correlation_bottom_percentile = self.config.get(
            "correlation_bottom_percentile", 25
        )
        self.use_categoricals = self.config.get("dataset_use_categoricals", False)

    def compile_comp_sets(self, output_dir="outputs/01_comp_sets"):
        """Merge all per-comp-set JSON files into a single master file.

        Reads compset_*.json from output_dir, merges with first-write-wins
        for duplicate listing IDs, and writes comp_set_{zipcode}.json.
        """
        merged = {}
        duplicates_skipped = 0
        pattern = os.path.join(output_dir, "compset_*.json")

        for filepath in sorted(glob.glob(pattern)):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            for listing_id, details in data.items():
                if listing_id in merged:
                    duplicates_skipped += 1
                else:
                    merged[listing_id] = details

        master_path = os.path.join(output_dir, f"comp_set_{self.zipcode}.json")
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=4)

        logger.info(
            f"Compiled {len(merged)} listings into {master_path} "
            f"({duplicates_skipped} duplicates skipped)."
        )

    def get_area_search_results(self):
        comp_set_path = f"outputs/01_comp_sets/comp_set_{self.zipcode}.json"
        if os.path.isfile(comp_set_path):
            with open(comp_set_path, "r", encoding="utf-8") as f:
                property_ids = json.load(f).keys()
            logger.info(f"Using {len(property_ids)} listing IDs from {comp_set_path}")
            search_results = []
            for room_id in property_ids:
                search_results.append({"room_id": room_id})
        elif os.path.isfile(
            f"outputs/02_search_results/search_results_{self.zipcode}.json"
        ):
            with open(
                f"outputs/02_search_results/search_results_{self.zipcode}.json",
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
        if self.scrape_airdna:
            airdna_scraper = AirDNAScraper(
                cdp_url=self.airdna_cdp_url,
                comp_set_ids=self.airdna_comp_set_ids,
                inspect_mode=self.airdna_inspect_mode,
            )
            airdna_scraper.run()
            self.compile_comp_sets()
            logger.info("AirDNA comp set scraping completed.")

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
            comp_set_filepath = f"outputs/01_comp_sets/comp_set_{self.zipcode}.json"
            fileset_builder = DetailsFilesetBuilder(
                use_categoricals=self.use_categoricals,
                comp_set_filepath=comp_set_filepath,
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

        if self.analyze_correlations:
            analyzer = CorrelationAnalyzer(
                zipcode=self.zipcode,
                metrics=self.correlation_metrics,
                top_percentile=self.correlation_top_percentile,
                bottom_percentile=self.correlation_bottom_percentile,
            )
            analyzer.run_analysis()
            logger.info(f"Correlation analysis for zipcode {self.zipcode} completed.")

        if self.analyze_descriptions:
            desc_analyzer = DescriptionAnalyzer(zipcode=self.zipcode)
            desc_analyzer.run_analysis()
            logger.info(
                f"Description quality analysis for zipcode {self.zipcode} completed."
            )

        # Things to do
        # Aggregrate the aggreated reviews into a single review per zip code
        # Simple frontend gui for config selection (use streamlit)
        # Turn the scraped data into a table for users to look at manually
        # Store output in aws in s3
        # Create a readme with copilot once done


if __name__ == "__main__":
    aggregator = AirBnbReviewAggregator()
    aggregator.run_tasks_from_config()
