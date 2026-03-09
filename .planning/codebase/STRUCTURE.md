# Codebase Structure

**Analysis Date:** 2026-03-08

## Directory Layout

```
AirBNB-Review-Scraper/
├── main.py                     # Pipeline orchestrator entry point
├── config.json                 # Runtime configuration (stage flags, OpenAI settings, zipcode)
├── Makefile                    # Dev workflow commands (test, lint, run)
├── Pipfile / Pipfile.lock       # Dependency declarations (pipenv)
├── pytest.ini                  # Test configuration
├── AGENTS.md                   # Agent-oriented project documentation
│
├── steps/                      # Pipeline stage modules (01–09), each exports run()
│   ├── __init__.py             # Shared step helper: load_search_results()
│   ├── 01_search_results.py
│   ├── 02_details_scrape.py
│   ├── 03_airdna_data.py
│   ├── 04_reviews_scrape.py
│   ├── 05_details_results.py
│   ├── 06_listing_summaries.py
│   ├── 07_area_summary.py
│   ├── 08_correlation_results.py
│   └── 09_description_analysis.py
│
├── scraper/                    # Data collection from Airbnb and AirDNA
│   ├── airbnb_searcher.py      # Bounding-box search via pyairbnb
│   ├── details_scraper.py      # Per-listing detail scrape via pyairbnb
│   ├── reviews_scraper.py      # Per-listing review scrape via pyairbnb
│   ├── airdna_scraper.py       # AirDNA rentalizer scrape via Playwright + CDP
│   ├── details_fileset_build.py # Joins raw Airbnb + AirDNA data into analysis CSVs
│   └── location_calculator.py  # Zipcode → lat/lon bounding box via pgeocode
│
├── review_aggregator/          # LLM analysis and statistical summarization
│   ├── openai_aggregator.py    # OpenAI client with chunking, retry, cost tracking
│   ├── property_review_aggregator.py  # Per-listing review → summary (step 06)
│   ├── area_review_aggregator.py      # All summaries → area prose report (step 07)
│   ├── correlation_analyzer.py        # Amenity/metric correlation + insights (step 08)
│   └── description_analyzer.py        # Listing description quality scoring (step 09)
│
├── utils/                      # Shared infrastructure
│   ├── pipeline_cache_manager.py  # Filesystem TTL cache for all stage outputs
│   ├── local_file_handler.py      # Directory clear operations
│   ├── tiny_file_handler.py       # load_json_file / save_json_file helpers
│   └── cost_tracker.py            # OpenAI API token/cost tracking, session logging
│
├── prompts/                    # LLM prompt templates (JSON files with placeholders)
│   ├── prompt.json                    # Per-listing review summarization prompt
│   ├── zipcode_prompt.json            # Area-level summary prompt
│   ├── correlation_prompt.json        # Correlation analysis prompts (ADR + occupancy)
│   └── description_analysis_prompt.json  # Description quality scoring prompt
│
├── outputs/                    # Pipeline stage outputs (gitignored data files)
│   ├── 01_search_results/      # search_results_{zipcode}.json
│   ├── 02_details_scrape/      # property_details_{id}.json (per listing)
│   ├── 03_airdna_data/           # listing_{id}.json + comp_set_{zipcode}.json
│   ├── 04_reviews_scrape/      # reviews_{zipcode}_{id}.json (per listing)
│   ├── 05_details_results/     # property_amenities_matrix_{zipcode}.csv, descriptions JSON, etc.
│   ├── 06_listing_summaries/   # listing_summary_{zipcode}_{id}.json (per listing)
│   ├── 07_area_summary/        # (reserved; report written to reports/)
│   ├── 08_correlation_results/ # correlation_stats_{metric}_{zipcode}.json
│   └── 09_description_analysis/ # description_quality_stats_{zipcode}.json
│
├── reports/                    # Final human-readable Markdown reports
│   ├── area_summary_{zipcode}.md
│   ├── correlation_insights_{metric}_{zipcode}.md
│   └── description_quality_{zipcode}.md
│
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests (one file per source module)
│   ├── integration/            # Integration test(s) for pipeline flow
│   └── fixtures/               # Shared test data (sample_data.json)
│
├── logs/                       # Runtime logs (cost tracking JSON)
│   └── cost_tracking.json
│
├── docs/                       # Developer documentation
├── .planning/                  # GSD planning artifacts
│   └── codebase/               # Auto-generated codebase analysis documents
└── .github/workflows/          # CI configuration
```

## Directory Purposes

**`steps/`:**
- Purpose: One module per pipeline stage; each exposes `run(config, pipeline_cache)`
- Contains: Stage logic thin wrappers, cache decision calls, calls into `scraper/` or `review_aggregator/`
- Key files: `steps/__init__.py` (shared `load_search_results` helper used by steps 01, 02, 03, 04)

**`scraper/`:**
- Purpose: All data acquisition — no analysis lives here
- Contains: Functions and classes that call external APIs/services and write raw output files
- Key files: `scraper/airdna_scraper.py` (Playwright + CDP, most complex scraper), `scraper/details_fileset_build.py` (post-processing joins)

**`review_aggregator/`:**
- Purpose: LLM-powered analysis and statistical insight generation
- Contains: Pydantic model classes with `task_chain()` or `run_analysis()` as main entry methods
- Key files: `review_aggregator/openai_aggregator.py` (shared by all LLM steps), `review_aggregator/correlation_analyzer.py`

**`utils/`:**
- Purpose: Shared infrastructure with no business logic
- Contains: File I/O helpers, the cache manager, cost tracker
- Key files: `utils/pipeline_cache_manager.py` (central to all stage decisions)

**`prompts/`:**
- Purpose: All LLM prompt templates, kept separate from code for easy iteration
- Contains: JSON files with a single key containing the prompt string with `{PLACEHOLDER}` tokens
- Key files: `prompts/prompt.json` (per-listing summary), `prompts/zipcode_prompt.json` (area summary)

**`outputs/`:**
- Purpose: Filesystem cache of all pipeline stage outputs; numbered subdirectories match stage numbers
- Generated: Yes (by pipeline runs)
- Committed: No (gitignored)

**`reports/`:**
- Purpose: Final deliverable Markdown files for human consumption
- Generated: Yes (by steps 07, 08, 09)
- Committed: Example reports are committed; live reports may be gitignored

## Key File Locations

**Entry Points:**
- `main.py`: Primary pipeline runner
- `scraper/airdna_scraper.py`: Standalone AirDNA scraper (has its own `__main__` block)

**Configuration:**
- `config.json`: All pipeline flags, OpenAI settings, zipcode, thresholds
- `.env`: Environment variables (`OPENAI_API_KEY`); not committed
- `.env.example`: Documents required env vars

**Core Logic:**
- `utils/pipeline_cache_manager.py`: Stage caching, skip/resume/force-refresh decisions, cascade logic
- `review_aggregator/openai_aggregator.py`: All OpenAI API calls, token chunking, retry
- `scraper/details_fileset_build.py`: Joins Airbnb details + AirDNA comp set into analysis-ready CSV

**Testing:**
- `tests/unit/`: Unit test per module
- `tests/integration/test_pipeline_integration.py`: End-to-end pipeline flow test
- `tests/fixtures/sample_data.json`: Shared fixture data

## Naming Conventions

**Files:**
- Steps: two-digit prefix + underscore + snake_case name (`01_search_results.py`)
- Scrapers: snake_case noun phrase (`airbnb_searcher.py`, `details_scraper.py`)
- Aggregators: snake_case with `_aggregator` or `_analyzer` suffix (`openai_aggregator.py`, `correlation_analyzer.py`)
- Tests: `test_` prefix matching the source module name (`test_pipeline_cache_manager.py`)

**Output files:** `{type}_{zipcode}_{id}.json` or `{type}_{metric}_{zipcode}.json`
- Search results: `search_results_{zipcode}.json`
- Reviews: `reviews_{zipcode}_{listing_id}.json`
- Listing summaries: `listing_summary_{zipcode}_{listing_id}.json`
- Correlation stats: `correlation_stats_{metric}_{zipcode}.json`
- Reports: `area_summary_{zipcode}.md`, `correlation_insights_{metric}_{zipcode}.md`

**Classes:**
- PascalCase (`AirDNAScraper`, `CorrelationAnalyzer`, `PropertyAggregator`)
- Pydantic `BaseModel` used for all main service classes

**Functions:**
- snake_case; public pipeline functions are `run()` in step modules
- Private helpers prefixed with `_` (`_fetch_reviews_with_retry`, `_is_listing_cached`)

## Where to Add New Code

**New pipeline stage:**
- Step module: `steps/NN_name.py` (export `run(config, pipeline_cache)`, define `STAGE = "name"`)
- Add to `PIPELINE_STEPS` in `main.py`
- Add stage to `PipelineCacheManager.STAGE_ORDER` in `utils/pipeline_cache_manager.py`
- Add `force_refresh_name` flag to `config.json` and `pipeline_cache_manager.py` init
- Add expected output paths to `PipelineCacheManager.expected_outputs()`
- If it produces analysis outputs, add to `CASCADE_TARGET_STAGES`

**New scraper:**
- Implementation: `scraper/{name}.py`
- Invoked from its corresponding step in `steps/`

**New LLM analyzer:**
- Implementation: `review_aggregator/{name}_analyzer.py`
- Prompt template: `prompts/{name}_prompt.json`
- Invoked from its corresponding step in `steps/`

**Utilities:**
- Shared helpers: `utils/{name}.py`

## Special Directories

**`outputs/`:**
- Purpose: Intermediate data files produced by each pipeline stage
- Generated: Yes, by pipeline runs
- Committed: No

**`reports/`:**
- Purpose: Final Markdown deliverables (area summary, correlation insights, description quality)
- Generated: Yes, by steps 07, 08, 09
- Committed: Example reports (`area_summary_97067.md`, etc.) are committed as samples

**`logs/`:**
- Purpose: OpenAI cost tracking session logs (`cost_tracking.json`)
- Generated: Yes, appended on each LLM-using run
- Committed: No

**`.planning/`:**
- Purpose: GSD planning documents and codebase analysis
- Generated: By GSD tooling
- Committed: Yes

---

*Structure analysis: 2026-03-08*
