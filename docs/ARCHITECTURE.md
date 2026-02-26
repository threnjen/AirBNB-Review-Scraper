# Architecture Overview

> **Purpose:** Model-friendly context primer. Use this doc to quickly locate modules, understand data flow, and identify key patterns before diving into code.

## Project Purpose

End-to-end pipeline for short-term rental market analysis. Given a zip code, it scrapes Airbnb listings + reviews, enriches them with AirDNA financial metrics, generates AI-powered summaries and statistical analyses, and produces actionable market intelligence reports. Entry point: `main.py` → `AirBnbReviewAggregator` → `run_tasks_from_config()`, driven entirely by `config.json`.

## Module Map

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

| File | Keys | Used By Stage |
|------|------|---------------|
| `prompt.json` | `"prompt"` | Stage 4 — Property summaries. Placeholders: `{ZIP_CODE_HERE}`, `{ISO_CODE_HERE}`, `{RATING_AVERAGE_HERE}`, `{OVERALL_MEAN}` |
| `zipcode_prompt.json` | `"gpt4o_mini_generate_prompt_structured"` | Stage 5 — Area summary |
| `correlation_prompt.json` | `"adr_prompt"`, `"occupancy_prompt"` | Stage 8 — Correlation analysis |
| `description_analysis_prompt.json` | `"scoring_prompt"`, `"synthesis_prompt"` | Stage 9 — Description quality scoring + synthesis |

## Pipeline Stages

Execution order as defined in `PipelineCacheManager.STAGE_ORDER`:

| # | Stage Name | Source Module | Entry Symbol | Input | Output |
|---|-----------|---------------|--------------|-------|--------|
| 0 | Listing Discovery | `scraper/airbnb_searcher.py` | `airbnb_searcher()` | Zipcode + ISO code | `outputs/01_search_results/` |
| 1 | AirDNA Lookup | `scraper/airdna_scraper.py` | `AirDNAScraper.run()` | Listing IDs from stage 0 | `outputs/02_comp_sets/` |
| 2 | Review Scraping | `scraper/reviews_scraper.py` | `scrape_reviews()` | Search results | `outputs/03_reviews_scraped/` |
| 3 | Details Scraping | `scraper/details_scraper.py` | `scrape_details()` | Search results | `outputs/04_details_scraped/` |
| 4 | Property Summaries | `review_aggregator/property_review_aggregator.py` | `PropertyRagAggregator.rag_description_generation_chain()` | Reviews + `prompts/prompt.json` | `outputs/06_generated_summaries/` |
| 5 | Area Summary | `review_aggregator/area_review_aggregator.py` | `AreaRagAggregator.rag_description_generation_chain()` | Property summaries + `prompts/zipcode_prompt.json` | `reports/` |
| 6 | Details Fileset Build | `scraper/details_fileset_build.py` | `DetailsFilesetBuilder.build_fileset()` | Raw details + comp set data | `outputs/05_details_results/` |
| 7 | Data Extraction | `review_aggregator/data_extractor.py` | `DataExtractor.run_extraction()` | Property summaries | `outputs/07_extracted_data/` |
| 8 | Correlation Analysis | `review_aggregator/correlation_analyzer.py` | `CorrelationAnalyzer.run_analysis()` | Amenity matrix CSV + descriptions + prompt | `outputs/08_correlation_results/` + `reports/` |
| 9 | Description Analysis | `review_aggregator/description_analyzer.py` | `DescriptionAnalyzer.run_analysis()` | Cleaned amenity matrix + descriptions + prompt | `outputs/09_description_analysis/` + `reports/` |

## Entry Point

`main.py` defines `AirBnbReviewAggregator`:

1. Loads `config.json`
2. Instantiates `PipelineCacheManager` with configured TTL
3. `run_tasks_from_config()` iterates enabled pipeline stages
4. Each stage checks cache status via `should_run_stage()` → returns `"skip"` (fresh), `"resume"` (incomplete), or `"clear_and_run"` (force refresh)
5. Stages execute only when cache says to, then downstream stages are cascade-invalidated if needed

## Key Patterns

### Pydantic BaseModel Everywhere
All `review_aggregator` classes, `CostTracker`, and `PipelineCacheManager` extend Pydantic `BaseModel` with `ConfigDict(arbitrary_types_allowed=True)` to allow non-serializable fields (OpenAI client, pandas DataFrames).

### Pipeline Cache with Cascade Invalidation
`PipelineCacheManager` uses `os.path.getmtime()` against a configurable TTL (default 7 days). The 10 stages are ordered — refreshing any stage auto-invalidates all downstream stages. Per-file freshness checks (`is_file_fresh()`) enable incremental scraping: only new or expired listings are re-fetched.

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

- **Pipeline toggles** — 9 booleans (`scrape_airdna`, `scrape_reviews`, etc.) control which stages run. 11 `force_refresh_*` booleans override cache per-stage.
- **Search/scraping parameters** — `zipcode`, `iso_code`, `num_listings_to_search`, `num_listings_to_summarize`, `num_summary_to_process`, `review_thresh_to_include_prop`, `min_days_available`, `airdna_cdp_url`, `airdna_inspect_mode`, `correlation_metrics`, `correlation_top_percentile`, `correlation_bottom_percentile`, `dataset_use_categoricals`
- **Nested `openai` object** — `model`, `temperature`, `max_tokens`, `chunk_token_limit`, `enable_cost_tracking`

## Output Directory Layout

| Directory | Contents |
|-----------|----------|
| `outputs/01_search_results/` | Listing discovery results by zipcode |
| `outputs/02_comp_sets/` | AirDNA per-listing financial metrics JSON |
| `outputs/03_reviews_scraped/` | Raw review JSON per listing |
| `outputs/04_details_scraped/` | Property details JSON (amenities, rules, descriptions) |
| `outputs/05_details_results/` | Structured CSVs: amenity matrix, descriptions, house rules, neighborhood highlights |
| `outputs/06_generated_summaries/` | AI-generated property summaries |
| `outputs/07_extracted_data/` | Aggregated structured data from summaries |
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
| `numpy` | Numeric operations underlying pandas/statsmodels work |
| `statsmodels` | OLS regression in description quality analysis |
