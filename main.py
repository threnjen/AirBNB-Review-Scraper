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
from utils.pipeline_cache_manager import PipelineCacheManager

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
        self.airdna_cdp_url = "http://localhost:9222"
        self.airdna_inspect_mode = False
        self.min_days_available = 100
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
        self.airdna_cdp_url = self.config.get("airdna_cdp_url", "http://localhost:9222")
        self.airdna_inspect_mode = self.config.get("airdna_inspect_mode", False)
        self.min_days_available = self.config.get("min_days_available", 100)
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

        # Pipeline cache settings
        self.pipeline_cache = PipelineCacheManager()

    def compile_comp_sets(self, output_dir="outputs/02_comp_sets"):
        """Merge all per-listing JSON files into a single master file.

        Reads listing_*.json from output_dir, merges with first-write-wins
        for duplicate listing IDs, and writes comp_set_{zipcode}.json.
        """
        merged = {}
        duplicates_skipped = 0
        pattern = os.path.join(output_dir, "listing_*.json")

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
        search_output = f"outputs/01_search_results/search_results_{self.zipcode}.json"
        force_refresh = self.pipeline_cache.force_refresh_flags.get("search", False)

        if not force_refresh and self.pipeline_cache.is_file_fresh(
            "search", search_output
        ):
            with open(search_output, "r", encoding="utf-8") as f:
                search_results = json.load(f)
            logger.info(
                f"Loaded {len(search_results)} cached search results (still fresh)."
            )
        elif not force_refresh and os.path.isfile(search_output):
            with open(search_output, "r", encoding="utf-8") as f:
                search_results = json.load(f)
            logger.info(
                f"Loaded {len(search_results)} listings from existing search results file."
            )
        else:
            if force_refresh:
                logger.info("Force refresh enabled for search — re-running.")
            self.pipeline_cache.clear_stage("search")
            self.pipeline_cache.cascade_force_refresh("search")
            search_results = airbnb_searcher(self.zipcode, self.iso_code)
            self.pipeline_cache.record_output("search", search_output)
            self.pipeline_cache.record_stage_complete("search")
        logger.info(f"Search results data looks like: {search_results[:1]}")
        return search_results

    def run_tasks_from_config(self):
        if self.scrape_airdna:
            if self.pipeline_cache.is_stage_fresh("airdna"):
                logger.info("Skipping AirDNA scraping — cached outputs are fresh.")
            else:
                search_results = self.get_area_search_results()
                listing_ids = [
                    str(r.get("room_id", r.get("id", ""))) for r in search_results
                ]
                listing_ids = [i for i in listing_ids if i]
                self.pipeline_cache.clear_stage("airdna")
                self.pipeline_cache.cascade_force_refresh("airdna")
                airdna_scraper = AirDNAScraper(
                    cdp_url=self.airdna_cdp_url,
                    listing_ids=listing_ids,
                    inspect_mode=self.airdna_inspect_mode,
                    min_days_available=self.min_days_available,
                )
                airdna_scraper.run()
                self.compile_comp_sets()
                comp_set_path = f"outputs/02_comp_sets/comp_set_{self.zipcode}.json"
                self.pipeline_cache.record_output("airdna", comp_set_path)
                self.pipeline_cache.record_stage_complete("airdna")
                logger.info("AirDNA per-listing scraping completed.")

        if self.scrape_reviews:
            if self.pipeline_cache.is_stage_fresh("reviews"):
                logger.info("Skipping reviews scraping — cached outputs are fresh.")
            else:
                self.pipeline_cache.clear_stage("reviews")
                self.pipeline_cache.cascade_force_refresh("reviews")
                search_results = self.get_area_search_results()
                scrape_reviews(
                    zipcode=self.zipcode,
                    search_results=search_results,
                    num_listings=self.num_listings_to_search,
                    pipeline_cache=self.pipeline_cache,
                )
                self.pipeline_cache.record_stage_complete("reviews")
                logger.info(
                    f"Scraping reviews for zipcode {self.zipcode} in country {self.iso_code} completed."
                )

        if self.scrape_details:
            if self.pipeline_cache.is_stage_fresh("details"):
                logger.info("Skipping details scraping — cached outputs are fresh.")
            else:
                self.pipeline_cache.clear_stage("details")
                self.pipeline_cache.cascade_force_refresh("details")
                search_results = self.get_area_search_results()
                scrape_details(
                    search_results=search_results,
                    num_listings=self.num_listings_to_search,
                    pipeline_cache=self.pipeline_cache,
                )
                self.pipeline_cache.record_stage_complete("details")
                logger.info(
                    f"Scraping details for zipcode {self.zipcode} in country {self.iso_code} completed."
                )

        if self.aggregate_reviews:
            if self.pipeline_cache.is_stage_fresh("aggregate_reviews"):
                logger.info("Skipping review aggregation — cached outputs are fresh.")
            else:
                self.pipeline_cache.clear_stage("aggregate_reviews")
                self.pipeline_cache.cascade_force_refresh("aggregate_reviews")
                rag_property = PropertyRagAggregator(
                    num_listings_to_summarize=self.num_listings_to_summarize,
                    review_thresh_to_include_prop=self.review_thresh_to_include_prop,
                    zipcode=self.zipcode,
                    pipeline_cache=self.pipeline_cache,
                )
                rag_property.rag_description_generation_chain()
                self.pipeline_cache.record_stage_complete("aggregate_reviews")
                logger.info(
                    f"Aggregating reviews for zipcode {self.zipcode} in country {self.iso_code} completed."
                )

        if self.aggregate_summaries:
            if self.pipeline_cache.is_stage_fresh("aggregate_summaries"):
                logger.info(
                    "Skipping area summary aggregation — cached outputs are fresh."
                )
            else:
                self.pipeline_cache.clear_stage("aggregate_summaries")
                self.pipeline_cache.cascade_force_refresh("aggregate_summaries")
                rag_area = AreaRagAggregator(
                    num_listings=self.num_summary_to_process,
                    review_thresh_to_include_prop=self.review_thresh_to_include_prop,
                    zipcode=self.zipcode,
                    pipeline_cache=self.pipeline_cache,
                )
                rag_area.rag_description_generation_chain()
                self.pipeline_cache.record_stage_complete("aggregate_summaries")
                logger.info(
                    f"Aggregating area summary for zipcode {self.zipcode} completed."
                )

        if self.build_details:
            if self.pipeline_cache.is_stage_fresh("build_details"):
                logger.info(
                    "Skipping details fileset build — cached outputs are fresh."
                )
            else:
                self.pipeline_cache.clear_stage("build_details")
                self.pipeline_cache.cascade_force_refresh("build_details")
                comp_set_filepath = f"outputs/02_comp_sets/comp_set_{self.zipcode}.json"
                fileset_builder = DetailsFilesetBuilder(
                    use_categoricals=self.use_categoricals,
                    comp_set_filepath=comp_set_filepath,
                )
                fileset_builder.build_fileset()
                for output_file in [
                    "outputs/05_details_results/property_amenities_matrix.csv",
                    "outputs/05_details_results/house_rules_details.json",
                    "outputs/05_details_results/property_descriptions.json",
                    "outputs/05_details_results/neighborhood_highlights.json",
                ]:
                    self.pipeline_cache.record_output("build_details", output_file)
                self.pipeline_cache.record_stage_complete("build_details")
                logger.info("Building details fileset completed.")

        if self.extract_data:
            if self.pipeline_cache.is_stage_fresh("extract_data"):
                logger.info("Skipping data extraction — cached outputs are fresh.")
            else:
                self.pipeline_cache.clear_stage("extract_data")
                self.pipeline_cache.cascade_force_refresh("extract_data")
                extractor = DataExtractor(zipcode=self.zipcode)
                extractor.run_extraction()
                output_file = f"outputs/07_extracted_data/area_data_{self.zipcode}.json"
                self.pipeline_cache.record_output("extract_data", output_file)
                self.pipeline_cache.record_stage_complete("extract_data")
                logger.info(f"Data extraction for zipcode {self.zipcode} completed.")

        if self.analyze_correlations:
            if self.pipeline_cache.is_stage_fresh("analyze_correlations"):
                logger.info("Skipping correlation analysis — cached outputs are fresh.")
            else:
                self.pipeline_cache.clear_stage("analyze_correlations")
                self.pipeline_cache.cascade_force_refresh("analyze_correlations")
                analyzer = CorrelationAnalyzer(
                    zipcode=self.zipcode,
                    metrics=self.correlation_metrics,
                    top_percentile=self.correlation_top_percentile,
                    bottom_percentile=self.correlation_bottom_percentile,
                )
                analyzer.run_analysis()
                for metric in self.correlation_metrics:
                    output_file = f"outputs/08_correlation_results/correlation_stats_{metric}_{self.zipcode}.json"
                    self.pipeline_cache.record_output(
                        "analyze_correlations", output_file
                    )
                self.pipeline_cache.record_stage_complete("analyze_correlations")
                logger.info(
                    f"Correlation analysis for zipcode {self.zipcode} completed."
                )

        if self.analyze_descriptions:
            if self.pipeline_cache.is_stage_fresh("analyze_descriptions"):
                logger.info("Skipping description analysis — cached outputs are fresh.")
            else:
                self.pipeline_cache.clear_stage("analyze_descriptions")
                self.pipeline_cache.cascade_force_refresh("analyze_descriptions")
                desc_analyzer = DescriptionAnalyzer(zipcode=self.zipcode)
                desc_analyzer.run_analysis()
                output_file = f"outputs/09_description_analysis/description_quality_stats_{self.zipcode}.json"
                self.pipeline_cache.record_output("analyze_descriptions", output_file)
                self.pipeline_cache.record_stage_complete("analyze_descriptions")
                logger.info(
                    f"Description quality analysis for zipcode {self.zipcode} completed."
                )


if __name__ == "__main__":
    aggregator = AirBnbReviewAggregator()
    aggregator.run_tasks_from_config()
