# Pipeline Reorder — Tasks

## Stage 1: Rename Config Flags & Update Cache Manager

- [x] Update `config.json` with new flag names in pipeline order
- [x] Add `search_results` and `force_refresh_search_results` flags
- [x] Remove `aggregate_summaries`/`extract_data` flags, replace with `area_summary`
- [x] Update `STAGE_ORDER` in `utils/pipeline_cache_manager.py`
- [x] Update `STAGE_OUTPUT_DIRS` with new directory mappings
- [x] Update `force_refresh_flags` config key names in `__init__`
- [x] Update all `expected_outputs()` branches for new stage names and paths
- [x] Merge `aggregate_summaries` + `extract_data` expected outputs into `area_summary`
- [x] Update `tests/unit/test_pipeline_cache_manager.py`
- [x] Update `tests/unit/test_pipeline_cache_mtime.py`
- [x] Run `pipenv run pytest tests/unit/test_pipeline_cache_manager.py tests/unit/test_pipeline_cache_mtime.py` — all pass

## Stage 2: Update Hardcoded Paths in Modules

- [x] Update `scraper/airdna_scraper.py` — `outputs/02_comp_sets` → `outputs/05_comp_sets`
- [x] Update `scraper/reviews_scraper.py` — `outputs/03_reviews_scraped` → `outputs/04_reviews_scrape`
- [x] Update `scraper/details_scraper.py` — `outputs/04_details_scraped` → `outputs/02_details_scrape`
- [x] Update `scraper/details_fileset_build.py` — `04_details_scraped` → `02_details_scrape`, `05_details_results` → `03_details_results`, `02_comp_sets` → `05_comp_sets`
- [x] Update `review_aggregator/property_review_aggregator.py` — `03_reviews_scraped` → `04_reviews_scrape`, `06_generated_summaries` → `06_listing_summaries`
- [x] Update `review_aggregator/area_review_aggregator.py` — `06_generated_summaries` → `06_listing_summaries`
- [x] Update `review_aggregator/data_extractor.py` — `06_generated_summaries` → `06_listing_summaries`, `07_extracted_data` → `07_area_summary`
- [x] Check `review_aggregator/correlation_analyzer.py` for paths
- [x] Check `review_aggregator/description_analyzer.py` for paths
- [x] Grep for any remaining old directory names across all `.py` files
- [x] Update corresponding unit tests for each module
- [x] Run `pipenv run pytest` — all pass

## Stage 3: Create Step Runners & Refactor main.py

- [x] Create `steps/__init__.py`
- [x] Create `steps/01_search_results.py`
- [x] Create `steps/02_details_scrape.py`
- [x] Create `steps/03_details_results.py`
- [x] Create `steps/04_reviews_scrape.py`
- [x] Create `steps/05_comp_sets.py` (includes `compile_comp_sets`)
- [x] Create `steps/06_listing_summaries.py`
- [x] Create `steps/07_area_summary.py` (merges `aggregate_summaries` + `extract_data`)
- [x] Create `steps/08_correlation_results.py`
- [x] Create `steps/09_description_analysis.py`
- [x] Refactor `main.py` — read new config flags, call step runners in order
- [x] Remove `get_area_search_results()` and `compile_comp_sets()` from `main.py`
- [x] Update `tests/unit/test_compile_comp_sets.py`
- [x] Update `tests/unit/test_get_area_search_results.py`
- [x] Update `tests/integration/test_pipeline_integration.py`
- [x] Run `pipenv run pytest` — all pass
- [x] Update `docs/ARCHITECTURE.md`
- [x] Update `README.md`
- [x] Final grep for any old names across entire repo
