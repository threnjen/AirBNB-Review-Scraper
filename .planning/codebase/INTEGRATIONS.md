# External Integrations

**Analysis Date:** 2026-03-08

## APIs & External Services

**Airbnb (Unofficial):**
- Service: Airbnb listings search, property details, and guest reviews
  - SDK/Client: `pyairbnb` 2.2.1
  - Auth: No API key — pyairbnb uses unofficial web scraping with HTTP client spoofing (`curl-cffi`)
  - Search usage: `scraper/airbnb_searcher.py` via `pyairbnb.search_all()`
  - Details usage: `scraper/details_scraper.py` via `pyairbnb.get_details(room_id=...)`
  - Reviews usage: `scraper/reviews_scraper.py` via `pyairbnb.get_reviews(room_url=...)`
  - Rate limiting: Random sleep delays (1–5s for search, 3–6s for reviews) between requests
  - Retry logic: Up to 3 retries with exponential backoff; full-pass retry if >20% of listings fail

**AirDNA Rentalizer (Browser Automation):**
- Service: Per-listing STR performance metrics (ADR, Occupancy, Revenue, Days Available)
  - SDK/Client: `playwright` 1.58.0 via Chromium CDP remote debugging
  - Auth: Manual browser login required before running; user must authenticate in Chrome at `http://localhost:9222`
  - CDP URL: Configurable via `config.json` key `airdna_cdp_url` (default `http://localhost:9222`)
  - Usage: `scraper/airdna_scraper.py` — `AirDNAScraper` class connects to running Chrome instance
  - Rate limiting: Random sleep 10–15s between listings; 3-minute cooldown and retry if >25% of listings fail
  - Inspect mode: `config.json` key `airdna_inspect_mode` pauses execution for selector discovery

**OpenAI API:**
- Service: LLM-powered review summarization and area insight generation
  - SDK/Client: `openai` 2.24.0
  - Auth: `OPENAI_API_KEY` environment variable (set in `.env`, loaded automatically by OpenAI SDK)
  - Model: `gpt-4.1-mini` (configurable via `config.json` under `openai.model`)
  - Usage: `review_aggregator/openai_aggregator.py` — `OpenAIAggregator` class
    - Per-listing review summarization: `steps/05_listing_summaries.py`
    - Area-level summary generation: `review_aggregator/area_review_aggregator.py`
    - Description quality analysis: `review_aggregator/description_analyzer.py`
  - Chunking: Automatically chunks reviews exceeding `chunk_token_limit` (default 120,000 tokens) and merges results
  - Retry logic: Up to 3 retries with exponential backoff per API call
  - Timeout: 60 seconds per call
  - Configuration keys (`config.json` → `openai`):
    - `model` (default `gpt-4.1-mini`)
    - `temperature` (default 0.3)
    - `max_tokens` (default 16000)
    - `chunk_token_limit` (default 120000)
    - `enable_cost_tracking` (default true)

**pgeocode / GeoNames:**
- Service: Postal code geocoding to latitude/longitude bounding boxes
  - SDK/Client: `pgeocode` 0.5.0
  - Auth: None — downloads country data from GeoNames public dataset on first use
  - Usage: `scraper/location_calculator.py` — `locationer()` function; called by `scraper/airbnb_searcher.py` to compute geographic search bounding box

## Data Storage

**Databases:**
- None — no database is used

**File Storage:**
- Local filesystem only — all pipeline outputs are JSON files written to `outputs/` subdirectories:
  - `outputs/01_search_results/` — Airbnb search results per zipcode
  - `outputs/02_details_scrape/` — Per-listing property details JSON
  - `outputs/03_airdna_data/` — AirDNA metrics per listing + merged comp set
  - `outputs/04_reviews_scrape/` — Per-listing review arrays JSON
  - `outputs/07_details_results/` — Processed amenity matrices (CSV) and description/rules JSON
  - `outputs/05_listing_summaries/` — Per-listing OpenAI review summaries JSON
  - `outputs/08_correlation_results/` — Correlation stats JSON
  - `outputs/09_description_analysis/` — Description quality stats JSON
- Reports written to `reports/` as Markdown files

**Caching:**
- Filesystem-based TTL cache managed by `utils/pipeline_cache_manager.py`
  - Freshness determined by `os.path.getmtime` — no metadata sidecar files
  - Default TTL: 30 days (configurable via `config.json` key `pipeline_cache_ttl_days`)
  - Per-stage force-refresh flags in `config.json` (e.g., `force_refresh_search_results`)
  - Cascade logic: refreshing an upstream stage auto-invalidates downstream analysis stages (`area_summary`, `correlation_results`, `description_analysis`)

## Authentication & Identity

**Auth Provider:**
- None — no user auth system
- OpenAI: API key via environment variable `OPENAI_API_KEY`
- AirDNA: Manual browser session (user logs in to Chrome before running scraper)
- Airbnb: No credentials — pyairbnb uses anonymous web scraping

## Monitoring & Observability

**Error Tracking:**
- None — no external error tracking service

**Logs:**
- Python standard `logging` module, level INFO, output to stdout (`logging.basicConfig(level=logging.INFO, stream=sys.stdout)`) in all modules
- OpenAI cost tracking persisted to `logs/cost_tracking.json` (managed by `utils/cost_tracker.py`)
  - Tracks per-request token counts, costs, cache hits; rotates to last 100 sessions
  - Pricing model hardcoded in `utils/cost_tracker.py`: $0.40/1M input, $1.60/1M output

## CI/CD & Deployment

**Hosting:**
- Not deployed — local developer tooling only

**CI Pipeline:**
- GitHub Actions: `.github/workflows/black-check.yml`
  - Trigger: Pull requests to `main`
  - Runs: `black .` format check on Python 3.x (ubuntu-latest)
  - No test automation in CI — tests run locally via `make test`

## Environment Configuration

**Required env vars:**
- `OPENAI_API_KEY` — OpenAI API key for review summarization

**Secrets location:**
- `.env` file at project root (not committed to git, listed in `.gitignore`)
- `.env.example` documents the required variable name

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-03-08*
