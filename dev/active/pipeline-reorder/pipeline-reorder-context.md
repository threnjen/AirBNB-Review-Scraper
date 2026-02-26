# Pipeline Reorder — Context

## Key Files

| File | Role |
|---|---|
| `main.py` | Pipeline orchestrator — `AirBnbReviewAggregator`, `run_tasks_from_config()`, `get_area_search_results()`, `compile_comp_sets()` |
| `config.json` | Toggle flags, force-refresh flags, parameters |
| `utils/pipeline_cache_manager.py` | `STAGE_ORDER`, `STAGE_OUTPUT_DIRS`, `expected_outputs()`, `force_refresh_flags` |
| `scraper/airbnb_searcher.py` | `airbnb_searcher()` — search step |
| `scraper/details_scraper.py` | `scrape_details()` — hardcodes `outputs/04_details_scraped` |
| `scraper/details_fileset_build.py` | `DetailsFilesetBuilder` — reads `04_details_scraped` + `02_comp_sets`, writes `05_details_results` |
| `scraper/reviews_scraper.py` | `scrape_reviews()` — hardcodes `outputs/03_reviews_scraped` |
| `scraper/airdna_scraper.py` | `AirDNAScraper` — hardcodes `outputs/02_comp_sets` |
| `review_aggregator/property_review_aggregator.py` | `PropertyRagAggregator` — reads `03_reviews_scraped`, writes `06_generated_summaries` |
| `review_aggregator/area_review_aggregator.py` | `AreaRagAggregator` — reads `06_generated_summaries`, writes `reports/` |
| `review_aggregator/data_extractor.py` | `DataExtractor` — reads `06_generated_summaries`, writes `07_extracted_data` |
| `review_aggregator/correlation_analyzer.py` | `CorrelationAnalyzer` — writes `08_correlation_results` + `reports/` |
| `review_aggregator/description_analyzer.py` | `DescriptionAnalyzer` — writes `09_description_analysis` + `reports/` |

## Decisions

- **Search gets a config toggle**: `search_results: true` + `force_refresh_search_results: false`
- **Merge `aggregate_summaries` + `extract_data`**: Both become step 7 `area_summary`
- **Rename `generated_summaries` → `listing_summaries`** and **`extracted_data` → `area_summary`**
- **Step runner files in `steps/`**: One file per stage, named to match output directory
- **Underlying modules keep their filenames**: Only orchestration-layer naming changes
- **`reports/` stays unnumbered**: Multiple steps (7, 8, 9) write markdown reports there

## Directory Rename Map

| Old | New |
|---|---|
| `outputs/02_comp_sets/` | `outputs/05_comp_sets/` |
| `outputs/03_reviews_scraped/` | `outputs/04_reviews_scrape/` |
| `outputs/04_details_scraped/` | `outputs/02_details_scrape/` |
| `outputs/05_details_results/` | `outputs/03_details_results/` |
| `outputs/06_generated_summaries/` | `outputs/06_listing_summaries/` |
| `outputs/07_extracted_data/` | `outputs/07_area_summary/` |
| `outputs/08_correlation_results/` | (unchanged) |
| `outputs/09_description_analysis/` | (unchanged) |
| `outputs/01_search_results/` | (unchanged) |

## Config Flag Rename Map

| Old Flag | New Flag |
|---|---|
| (implicit search) | `search_results` / `force_refresh_search_results` |
| `scrape_details` / `force_refresh_scrape_details` | `details_scrape` / `force_refresh_details_scrape` |
| `build_details` / `force_refresh_build_details` | `details_results` / `force_refresh_details_results` |
| `scrape_reviews` / `force_refresh_reviews` | `reviews_scrape` / `force_refresh_reviews_scrape` |
| `scrape_airdna` / `force_refresh_scrape_airdna` | `comp_sets` / `force_refresh_comp_sets` |
| `aggregate_reviews` / `force_refresh_aggregate_reviews` | `listing_summaries` / `force_refresh_listing_summaries` |
| `aggregate_summaries` / `force_refresh_aggregate_summaries` | (merged into `area_summary`) |
| `extract_data` / `force_refresh_extract_data` | `area_summary` / `force_refresh_area_summary` |
| `analyze_correlations` / `force_refresh_analyze_correlations` | `correlation_results` / `force_refresh_correlation_results` |
| `analyze_descriptions` / `force_refresh_analyze_descriptions` | `description_analysis` / `force_refresh_description_analysis` |

## Cache Stage Name Map

| Old Stage | New Stage |
|---|---|
| `search` | `search_results` |
| `airdna` | `comp_sets` |
| `reviews` | `reviews_scrape` |
| `details` | `details_scrape` |
| `build_details` | `details_results` |
| `aggregate_reviews` | `listing_summaries` |
| `aggregate_summaries` | (merged into `area_summary`) |
| `extract_data` | `area_summary` |
| `analyze_correlations` | `correlation_results` |
| `analyze_descriptions` | `description_analysis` |
