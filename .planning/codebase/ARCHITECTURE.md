# Architecture

**Analysis Date:** 2026-03-08

## Pattern Overview

**Overall:** Sequential ETL Pipeline with LLM Analysis Layer

**Key Characteristics:**
- Nine numbered pipeline stages executed in order, each with a `run(config, pipeline_cache)` interface
- Filesystem is the integration layer: stages write JSON/CSV outputs that downstream stages consume as inputs
- Cache-aware: a `PipelineCacheManager` determines per-stage whether to skip, resume, or force-refresh based on output file mtime and TTL
- Configuration-driven: `config.json` controls which stages are enabled and sets all tuneable parameters
- LLM analysis is isolated to the final four stages (06–09) via `OpenAIAggregator`

## Layers

**Orchestrator:**
- Purpose: Loads config, instantiates the cache manager, iterates over enabled pipeline steps via dynamic `importlib` import
- Location: `main.py`
- Contains: `AirBnbReviewAggregator` class, `PIPELINE_STEPS` registry
- Depends on: `utils/pipeline_cache_manager.py`, `config.json`
- Used by: CLI (`python main.py`)

**Pipeline Steps:**
- Purpose: Thin wrappers that check cache state, invoke a service/scraper, then notify the cache
- Location: `steps/01_search_results.py` through `steps/09_description_analysis.py`
- Contains: One `run(config, pipeline_cache)` function per file; a `STAGE` constant
- Depends on: `scraper/`, `review_aggregator/`, `utils/pipeline_cache_manager.py`
- Used by: `main.py` (via `importlib.import_module`)

**Scrapers:**
- Purpose: All direct data collection from Airbnb and AirDNA
- Location: `scraper/`
- Contains: `airbnb_searcher.py`, `details_scraper.py`, `reviews_scraper.py`, `airdna_scraper.py`, `details_fileset_build.py`, `location_calculator.py`
- Depends on: `pyairbnb` library, `playwright` (AirDNA only), `pgeocode`
- Used by: Steps 01–05

**Review Aggregator / Analyzers:**
- Purpose: LLM-powered summarization and statistical analysis
- Location: `review_aggregator/`
- Contains: `openai_aggregator.py`, `property_review_aggregator.py`, `area_review_aggregator.py`, `correlation_analyzer.py`, `description_analyzer.py`
- Depends on: `openai`, `tiktoken`, `pandas`, `utils/`
- Used by: Steps 06–09

**Utilities:**
- Purpose: Cross-cutting infrastructure (file I/O, cache management, cost tracking)
- Location: `utils/`
- Contains: `pipeline_cache_manager.py`, `local_file_handler.py`, `tiny_file_handler.py`, `cost_tracker.py`
- Depends on: `pydantic`, standard library
- Used by: All layers above

## Data Flow

**Full Pipeline Run:**

1. `main.py` reads `config.json`, instantiates `PipelineCacheManager`, iterates enabled steps
2. **Step 01** — `airbnb_searcher` geocodes zipcode via `pgeocode`, divides bounding box into a 2×2 grid, calls `pyairbnb.search_all` for each box, writes `outputs/01_search_results/search_results_{zipcode}.json`
3. **Step 02** — `details_scraper` iterates listing IDs from step 01, calls `pyairbnb.get_details` per listing, writes `outputs/02_details_scrape/property_details_{id}.json`
4. **Step 03** — `AirDNAScraper` connects to a running Chrome via CDP, navigates `app.airdna.co/data/rentalizer?listing_id=abnb_{id}` per listing, extracts KPI metrics, writes `outputs/03_airdna_data/listing_{id}.json`; then merges all per-listing files into `comp_set_{zipcode}.json`
5. **Step 04** — `reviews_scraper` calls `pyairbnb.get_reviews` per listing, writes `outputs/04_reviews_scrape/reviews_{id}.json`
6. **Step 05** — `DetailsFilesetBuilder` joins Airbnb details with AirDNA comp set data, produces `outputs/06_details_results/property_amenities_matrix_{zipcode}.csv`, property descriptions, house rules, neighborhood highlights
7. **Step 06** — `PropertyAggregator` loads all review files, calls `OpenAIAggregator.generate_summary` per listing, writes `outputs/05_listing_summaries/listing_summary_{zipcode}_{id}.json`
8. **Step 07** — `AreaAggregator` loads all listing summaries for zipcode, calls `OpenAIAggregator.generate_summary` once for the area, writes `reports/area_summary_{zipcode}.md`
9. **Step 08** — `CorrelationAnalyzer` loads the amenities matrix CSV, segments properties into top/bottom percentile tiers per metric (ADR, occupancy), computes amenity prevalence differences, generates LLM insights, writes `outputs/08_correlation_results/` JSON and `reports/correlation_insights_{metric}_{zipcode}.md`
10. **Step 09** — `DescriptionAnalyzer` loads property descriptions, scores them for quality dimensions, correlates with ADR, writes `outputs/09_description_analysis/` JSON and `reports/description_quality_{zipcode}.md`

**Cache Decision Flow:**

1. Step calls `pipeline_cache.should_run_stage(STAGE, zipcode)`
2. Returns `"skip"` if all expected output files exist and are within TTL
3. Returns `"clear_and_run"` if `force_refresh_{stage}` is True in config
4. Returns `"resume"` otherwise (partial output, continue where left off)
5. After completing work, step calls `pipeline_cache.notify_stage_ran(STAGE)` which cascades `force_refresh=True` to downstream analysis stages (06–09)

**State Management:**
- No in-memory state is passed between stages; all inter-stage state is files on disk
- `PipelineCacheManager` is passed by reference through all steps but only carries config flags and TTL settings, not data

## Key Abstractions

**PipelineCacheManager:**
- Purpose: Filesystem-based TTL cache for all pipeline stage outputs; determines skip/resume/clear decisions
- Examples: `utils/pipeline_cache_manager.py`
- Pattern: Pydantic `BaseModel`; uses `os.path.getmtime` for freshness; cascade propagates refresh flags downstream

**OpenAIAggregator:**
- Purpose: Wraps the OpenAI chat completions API with token-aware chunking, retry with exponential backoff, and per-request cost tracking
- Examples: `review_aggregator/openai_aggregator.py`
- Pattern: Pydantic `BaseModel`; composes `CostTracker`; reads config overrides from `config.json` at init

**Step Module Contract:**
- Purpose: Every step exposes exactly one function `run(config: dict, pipeline_cache: PipelineCacheManager) -> None | list`
- Examples: `steps/01_search_results.py` through `steps/09_description_analysis.py`
- Pattern: Module-level `STAGE` constant matches the `config.json` flag name and the `PipelineCacheManager.STAGE_ORDER` entry

**Aggregator Classes:**
- Purpose: Encapsulate the multi-pass LLM summarization workflow (load raw data, filter already-processed, batch-process, save, re-process incomplete)
- Examples: `review_aggregator/property_review_aggregator.py`, `review_aggregator/area_review_aggregator.py`
- Pattern: Pydantic `BaseModel`; `task_chain()` is the main entry method

## Entry Points

**Primary CLI:**
- Location: `main.py` (`if __name__ == "__main__":`)
- Triggers: `python main.py`
- Responsibilities: Load config, run all enabled pipeline stages in order

**AirDNA Scraper Standalone:**
- Location: `scraper/airdna_scraper.py` (`if __name__ == "__main__":`)
- Triggers: `python -m scraper.airdna_scraper`
- Responsibilities: Run only the AirDNA scrape step directly, reading config and search results independently

## Error Handling

**Strategy:** Log-and-continue at the per-listing level; raise at the infrastructure level

**Patterns:**
- Scraper loops catch `Exception` per listing, log a warning, and `continue` — no listing failure aborts the batch
- `reviews_scraper.py` implements a full-pass retry: if >20% of listings fail, waits 120 seconds and retries the entire pass
- `AirDNAScraper` similarly retries a full pass if >25% of listings return empty metrics (rate-limit detection)
- `OpenAIAggregator.call_openai_with_retry` uses exponential backoff for up to `max_retries` (default 3) attempts
- `PipelineCacheManager.__init__` catches config load failures and falls back to defaults, logging a warning
- `tiny_file_handler.load_json_file` returns `{}` on `FileNotFoundError` (silent fallback)

## Cross-Cutting Concerns

**Logging:** `logging.basicConfig(level=logging.INFO, stream=sys.stdout)` is called at module level in every module; all modules use `logger = logging.getLogger(__name__)`

**Validation:** Pydantic `BaseModel` used for `PipelineCacheManager`, `OpenAIAggregator`, `CostTracker`, `PropertyAggregator`, `AreaAggregator`, `CorrelationAnalyzer`; no input validation on raw scraped data

**Authentication:** Airbnb is accessed via the `pyairbnb` library (no credentials needed); AirDNA requires a logged-in Chrome session reachable via CDP at `airdna_cdp_url`; OpenAI key is read from the environment (`OPENAI_API_KEY`)

**Prompt Management:** Prompts are stored as JSON files in `prompts/` (`prompt.json`, `zipcode_prompt.json`, `correlation_prompt.json`, `description_analysis_prompt.json`); placeholder strings like `{ZIP_CODE_HERE}` are replaced at runtime via `str.replace`

---

*Architecture analysis: 2026-03-08*
