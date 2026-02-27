# Architecture Overview

> **Purpose:** Model-friendly context primer. Use this doc to quickly locate modules, understand data flow, and identify key patterns before diving into code.

## Project Purpose

End-to-end pipeline for short-term rental market analysis. Given a zip code, it scrapes Airbnb listings + reviews, enriches them with AirDNA financial metrics, generates AI-powered summaries and statistical analyses, and produces actionable market intelligence reports. Entry point: `main.py` → `AirBnbReviewAggregator` → `run_tasks_from_config()`, which iterates `PIPELINE_STEPS` and calls each enabled step's `run()` function. All behaviour is driven by `config.json`.

## Module Map

### `steps/` — Pipeline Step Runners

Each step is a numbered module with a `run(config, pipeline_cache)` entry point. Config flag names, step filenames, and output directories are aligned.

| File | Config Flag | Output Directory |
|------|-------------|------------------|
| `01_search_results.py` | `search_results` | `outputs/01_search_results/` |
| `02_details_scrape.py` | `details_scrape` | `outputs/02_details_scrape/` |
| `03_comp_sets.py` | `comp_sets` | `outputs/03_comp_sets/` |
| `04_reviews_scrape.py` | `reviews_scrape` | `outputs/04_reviews_scrape/` |
| `05_details_results.py` | `details_results` | `outputs/05_details_results/` |
| `06_listing_summaries.py` | `listing_summaries` | `outputs/06_listing_summaries/` |
| `07_area_summary.py` | `area_summary` | `outputs/07_area_summary/` + `reports/` |
| `08_correlation_results.py` | `correlation_results` | `outputs/08_correlation_results/` + `reports/` |
| `09_description_analysis.py` | `description_analysis` | `outputs/09_description_analysis/` + `reports/` |

### `scraper/` — Data Acquisition

| File | Key Symbols | Purpose |
|------|-------------|---------|
| `airbnb_searcher.py` | `airbnb_searcher()`, `boxed_search()` | Zip → bounding box → 2×2 grid → `pyairbnb.search_all()` per sub-box |
| `airdna_scraper.py` | `AirDNAScraper`, `.run()`, `.scrape_listing()`, `_extract_header_metrics()`, `_extract_kpi_metrics()` | Playwright/CDP browser automation against AirDNA rentalizer pages |
| `reviews_scraper.py` | `scrape_reviews()` | Iterates listing IDs, calls `pyairbnb.get_reviews()`, saves per-listing JSON |
| `details_scraper.py` | `scrape_details()` | Iterates listing IDs, calls `pyairbnb.get_details()`, saves per-listing JSON |
| `details_fileset_build.py` | `DetailsFilesetBuilder`, `.build_fileset()`, `.clean_amenities_df()`, `.parse_amenity_flags()`, `.get_financials()` | Transforms raw details + AirDNA financials into structured CSV/JSON |
| `location_calculator.py` | `locationer()` | `pgeocode` zip → lat/lon → bounding box (±0.14 degrees) |

### `review_aggregator/` — AI Processing & Analysis

| File | Key Symbols | Purpose |
|------|-------------|---------|
| `openai_aggregator.py` | `OpenAIAggregator`, `.generate_summary()`, `.call_openai_with_retry()`, `.chunk_reviews()`, `.estimate_tokens()` | Central OpenAI client — tiktoken estimation, 120K-token chunking, 3 retries with exponential backoff, cost tracking |
| `property_review_aggregator.py` | `PropertyRagAggregator`, `.rag_description_generation_chain()`, `.process_single_listing()` | Per-property: loads reviews → GPT summary with 3-pass process (generate → remove empties → retry incompletes) |
| `area_review_aggregator.py` | `AreaRagAggregator`, `.rag_description_generation_chain()`, `.save_results()` | Aggregates all property summaries into single area-level analysis via GPT |
| `data_extractor.py` | `DataExtractor`, `.run_extraction()`, `.extract_data_from_summary()`, `.aggregate_extractions()` | LLM-powered parsing of summaries → structured JSON (categories, mention counts, percentages) |
| `correlation_analyzer.py` | `CorrelationAnalyzer`, `.run_analysis()`, `.segment_by_metric()`, `.compute_amenity_prevalence()`, `.generate_insights()` | Segments top/bottom percentile tiers by ADR or Occupancy, computes prevalence diffs for 22 amenities + 4 numeric features, sends to GPT |
| `description_analyzer.py` | `DescriptionAnalyzer`, `.run_analysis()`, `.compute_size_adjusted_residuals()`, `.score_single_description()`, `.correlate_scores_with_premium()`, `.generate_synthesis()` | OLS regression (ADR ~ all features), LLM scores descriptions on 7 dimensions (1–10), Pearson correlation vs ADR residuals |

### `utils/` — Infrastructure

| File | Key Symbols | Purpose |
|------|-------------|---------|
| `pipeline_cache_manager.py` | `PipelineCacheManager`, `.should_run_stage()`, `.is_stage_fresh()`, `.is_file_fresh()`, `.cascade_force_refresh()` | TTL-based file caching via `os.path.getmtime()`. 10-stage ordered pipeline with cascade invalidation |
| `cost_tracker.py` | `CostTracker`, `.track_request()`, `.get_session_summary()`, `.log_session()` | Tracks input/output tokens and costs per GPT-4.1-mini pricing, session logging to `logs/cost_tracking.json` |
| `local_file_handler.py` | `LocalFileHandler`, `.clear_directory()`, `.clear_files_matching()` | Directory/file cleanup operations for cache clearing |
| `tiny_file_handler.py` | `load_json_file()`, `save_json_file()` | Simple JSON read/write helpers |

### `prompts/` — LLM Prompt Templates

| File | Keys | Used By Step |
|------|------|--------------|
| `prompt.json` | `"prompt"` | Step 06 — Listing summaries. Placeholders: `{ZIP_CODE_HERE}`, `{ISO_CODE_HERE}`, `{RATING_AVERAGE_HERE}`, `{OVERALL_MEAN}` |
| `zipcode_prompt.json` | `"gpt4o_mini_generate_prompt_structured"` | Step 07 — Area summary |
| `correlation_prompt.json` | `"adr_prompt"`, `"occupancy_prompt"` | Step 08 — Correlation analysis |
| `description_analysis_prompt.json` | `"scoring_prompt"`, `"synthesis_prompt"` | Step 09 — Description quality scoring + synthesis |

## Pipeline Stages

Execution order as defined in `main.PIPELINE_STEPS` and `PipelineCacheManager.STAGE_ORDER`:

| # | Stage Key | Step File | Source Module | Output |
|---|-----------|-----------|---------------|--------|
| 1 | `search_results` | `steps/01_search_results.py` | `scraper/airbnb_searcher.py` | `outputs/01_search_results/` |
| 2 | `details_scrape` | `steps/02_details_scrape.py` | `scraper/details_scraper.py` | `outputs/02_details_scrape/` |
| 3 | `comp_sets` | `steps/03_comp_sets.py` | `scraper/airdna_scraper.py` | `outputs/03_comp_sets/` |
| 4 | `reviews_scrape` | `steps/04_reviews_scrape.py` | `scraper/reviews_scraper.py` | `outputs/04_reviews_scrape/` |
| 5 | `details_results` | `steps/05_details_results.py` | `scraper/details_fileset_build.py` | `outputs/05_details_results/` |
| 6 | `listing_summaries` | `steps/06_listing_summaries.py` | `review_aggregator/property_review_aggregator.py` | `outputs/06_listing_summaries/` |
| 7 | `area_summary` | `steps/07_area_summary.py` | `review_aggregator/area_review_aggregator.py` + `data_extractor.py` | `outputs/07_area_summary/` + `reports/` |
| 8 | `correlation_results` | `steps/08_correlation_results.py` | `review_aggregator/correlation_analyzer.py` | `outputs/08_correlation_results/` + `reports/` |
| 9 | `description_analysis` | `steps/09_description_analysis.py` | `review_aggregator/description_analyzer.py` | `outputs/09_description_analysis/` + `reports/` |

## Entry Point

`main.py` defines `AirBnbReviewAggregator`:

1. Loads `config.json`
2. Instantiates `PipelineCacheManager` with configured TTL
3. `run_tasks_from_config()` iterates `PIPELINE_STEPS` — a list of `(module_name, config_flag)` pairs
4. For each enabled flag, imports the step module via `importlib.import_module()` and calls `step.run(config, pipeline_cache)`
5. Each step internally calls `pipeline_cache.should_run_stage()` → returns `"skip"` (fresh), `"resume"` (incomplete), or `"clear_and_run"` (force refresh)
6. Stages execute only when cache says to, then downstream stages are cascade-invalidated if needed

## Key Patterns

### Pydantic BaseModel Everywhere
All `review_aggregator` classes, `CostTracker`, and `PipelineCacheManager` extend Pydantic `BaseModel` with `ConfigDict(arbitrary_types_allowed=True)` to allow non-serializable fields (OpenAI client, pandas DataFrames).

### Pipeline Cache with Cascade Invalidation
`PipelineCacheManager` uses `os.path.getmtime()` against a configurable TTL (default 7 days). The 9 stages are ordered — refreshing any stage auto-invalidates all downstream stages. Per-file freshness checks (`is_file_fresh()`) enable incremental scraping: only new or expired listings are re-fetched.

### Centralized OpenAI Client
All GPT calls route through `OpenAIAggregator.generate_summary()` → `call_openai_with_retry()`. Features:
- Token estimation via `tiktoken.encoding_for_model()`
- Auto-chunking at 120K tokens with merge step for multi-chunk responses
- 3 retries with exponential backoff (1s, 2s, 4s)
- Every call tracked by `CostTracker` (input/output tokens, cost at GPT-4.1-mini rates)

### Cost Tracking
`CostTracker` prices at GPT-4.1-mini rates ($0.40/1M input, $1.60/1M output tokens). Logs every request with timestamp, listing ID, token counts, and cost. Session summaries persist to `logs/cost_tracking.json` with 100-session rotation and includes per-100-listings extrapolation.

### Respectful Scraping
All scraper modules insert randomized delays between requests to mimic human browsing speed. The AirDNA scraper connects through a real Chrome browser session via CDP, appearing as a logged-in human user. Caching prevents redundant requests — previously scraped listings are skipped. Retry logic detects rate-limit signals and backs off rather than hammering.

## Config Schema

`config.json` has three levels:

- **Pipeline toggles** — 9 booleans matching step names (`search_results`, `details_scrape`, `details_results`, `reviews_scrape`, `comp_sets`, `listing_summaries`, `area_summary`, `correlation_results`, `description_analysis`). Each has a corresponding `force_refresh_*` boolean to override cache.
- **Search/scraping parameters** — `zipcode`, `iso_code`, `num_listings_to_search`, `num_listings_to_summarize`, `num_summary_to_process`, `review_thresh_to_include_prop`, `min_days_available`, `airdna_cdp_url`, `airdna_inspect_mode`, `correlation_metrics`, `correlation_top_percentile`, `correlation_bottom_percentile`, `dataset_use_categoricals`
- **Nested `openai` object** — `model`, `temperature`, `max_tokens`, `chunk_token_limit`, `enable_cost_tracking`

## Output Directory Layout

| Directory | Contents |
|-----------|----------|
| `outputs/01_search_results/` | Listing discovery results by zipcode |
| `outputs/02_details_scrape/` | Property details JSON (amenities, rules, descriptions) |
| `outputs/03_comp_sets/` | AirDNA per-listing financial metrics JSON + master comp set |
| `outputs/04_reviews_scrape/` | Raw review JSON per listing |
| `outputs/05_details_results/` | Structured CSVs: amenity matrix, descriptions, house rules, neighborhood highlights |
| `outputs/06_listing_summaries/` | AI-generated per-property summaries |
| `outputs/07_area_summary/` | Aggregated structured data from summaries |
| `outputs/08_correlation_results/` | Correlation statistics JSON per metric |
| `outputs/09_description_analysis/` | Description quality statistics JSON |
| `reports/` | Final markdown + JSON reports (area summary, correlation insights, description quality) |
| `logs/cost_tracking.json` | OpenAI API cost log per session |

## Test Organization

- `tests/conftest.py` — 16 fixtures including `isolate_tests` (autouse), `mock_openai_client`, sample data fixtures
- `tests/fixtures/sample_data.json` — shared test data
- `tests/unit/` — 16 test files, one per source module
- `tests/integration/` — `test_pipeline_integration.py`
- Coverage enforced at 75% minimum via `pytest.ini`

## Dependencies

| Package | Role |
|---------|------|
| `pyairbnb` | Airbnb listing search, review/detail fetching |
| `playwright` | Browser automation for AirDNA scraping via CDP |
| `pgeocode` | Zip code → latitude/longitude geocoding |
| `openai` | GPT-4.1-mini API client |
| `tiktoken` | Token counting for OpenAI chunking |
| `pydantic` | Data validation and settings for all aggregator/utility classes |
| `pandas` | DataFrames for amenity matrices, correlation analysis, OLS regression |
| `numpy` | Numeric operations, OLS regression via `numpy.linalg.lstsq` in description quality analysis |
