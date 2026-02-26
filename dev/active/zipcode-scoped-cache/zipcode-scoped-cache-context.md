# Context: Filesystem-Driven Cache

## Key Files
- `utils/pipeline_cache_manager.py` — `PipelineCacheManager`: rewriting `is_stage_fresh`, `should_run_stage`, `clear_stage_for_zipcode`; adding `expected_outputs`, `get_missing_outputs`, `_is_file_fresh_by_mtime`; removing `_load_metadata`, `_save_metadata`, `record_output`, `record_stage_complete`, `_is_timestamp_fresh`
- `utils/local_file_handler.py` — `LocalFileHandler.clear_directory`, `clear_files_matching` (unchanged)
- `main.py` — `AirBnbReviewAggregator.run_tasks_from_config` (10 stage blocks), `get_area_search_results` — removing all `record_output`/`record_stage_complete` calls
- `scraper/details_fileset_build.py` — `DetailsFilesetBuilder.build_fileset` — adding zipcode param, renaming output files to include zipcode
- `review_aggregator/correlation_analyzer.py` — `CorrelationAnalyzer.load_property_data`, `load_descriptions` — updating paths to zipcode-scoped filenames
- `review_aggregator/description_analyzer.py` — `DescriptionAnalyzer.load_property_data`, `load_descriptions` — updating paths to zipcode-scoped filenames
- `scraper/airdna_scraper.py` — `AirDNAScraper._is_listing_cached` — updating `is_file_fresh` call (no metadata)
- `scraper/reviews_scraper.py` — `scrape_reviews` — updating `is_file_fresh` call
- `scraper/details_scraper.py` — `scrape_details` — updating `is_file_fresh` call
- `review_aggregator/property_review_aggregator.py` — `filter_out_processed_reviews` — updating `is_file_fresh` call
- `tests/unit/test_pipeline_cache_manager.py` — rewriting for mtime-based tests
- `tests/integration/test_pipeline_integration.py` — removing metadata-based assertions

## Decisions
- **TTL source**: `os.path.getmtime` exclusively — no metadata timestamps, no `pipeline_metadata.json`
- **No `_completed` flags**: freshness = all expected files exist on disk with mtime within TTL
- **Expected outputs are enumerated, not recorded**: `expected_outputs()` derives the file list from stage name + zipcode + search results (for dynamic stages) + config (for correlation metrics)
- **`build_details` outputs get zipcode in filenames**: `property_amenities_matrix_{zipcode}.csv`, `property_amenities_matrix_cleaned_{zipcode}.csv`, `house_rules_details_{zipcode}.json`, `property_descriptions_{zipcode}.json`, `neighborhood_highlights_{zipcode}.json`
- **`force_refresh_` clears only expected outputs for the one zipcode**: `clear_stage_for_zipcode` calls `expected_outputs(stage, zipcode)` and deletes only those files — never wipes the entire directory, never touches other zipcodes' files
- **Cascade behavior unchanged**: `cascade_force_refresh` and `_apply_init_cascade` remain as-is (they only set flags)
- **Three-way return unchanged**: `"skip"` / `"resume"` / `"clear_and_run"` (string literals)
- **Per-file `is_file_fresh` in scrapers**: now checks `os.path.getmtime` + force_refresh flag only — no metadata lookup
- **`clear_stage()` retained as deprecated full-wipe fallback**

## Expected Output File Reference

| Stage | Output Dir | File Pattern | Count |
|---|---|---|---|
| `search` | `outputs/01_search_results/` | `search_results_{zipcode}.json` | 1 fixed |
| `airdna` | `outputs/02_comp_sets/` | `listing_{lid}.json` + `comp_set_{zipcode}.json` | dynamic + 1 |
| `reviews` | `outputs/03_reviews_scraped/` | `reviews_{zipcode}_{lid}.json` | dynamic |
| `details` | `outputs/04_details_scraped/` | `property_details_{lid}.json` | dynamic |
| `build_details` | `outputs/05_details_results/` | `*_{zipcode}.*` (5 files) | 5 fixed |
| `aggregate_reviews` | `outputs/06_generated_summaries/` | `generated_summaries_{zipcode}_{lid}.json` | dynamic |
| `aggregate_summaries` | `reports/` | `area_summary_{zipcode}.json`, `area_summary_{zipcode}.md` | 2 fixed |
| `extract_data` | `outputs/07_extracted_data/` | `area_data_{zipcode}.json` | 1 fixed |
| `analyze_correlations` | `outputs/08_correlation_results/` + `reports/` | `correlation_stats_{metric}_{zipcode}.json`, `correlation_insights_{metric}_{zipcode}.md` | 2 per metric |
| `analyze_descriptions` | `outputs/09_description_analysis/` + `reports/` | `description_quality_stats_{zipcode}.json`, `description_quality_{zipcode}.md` | 2 fixed |

## Dynamic Stage Enumeration
- `airdna`, `reviews`, `details`: listing IDs from `outputs/01_search_results/search_results_{zipcode}.json` (`room_id` or `id` field)
- `aggregate_reviews`: listing IDs from review files on disk matching `reviews_{zipcode}_*.json`
- `analyze_correlations`: metrics from `config.correlation_metrics` (default `["adr", "occupancy"]`)
