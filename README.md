# AirBNB Review Scraper & Analyzer

An end-to-end pipeline for short-term rental market analysis. Given a zip code, it scrapes hundreds of Airbnb listings and their reviews, generates AI-powered summaries using GPT-4.1-mini, enriches each listing with AirDNA financial metrics via per-listing rentalizer lookups, and produces market-intelligence reports that identify what drives higher nightly rates and occupancy. The final output includes correlation analyses (e.g., "Jacuzzi presence correlates with +57.5% higher ADR"), description quality scoring via OLS regression, and actionable recommendations for hosts — all generated automatically from a single `config.json`.

## Prerequisites

Before setting up the project, ensure you have the following. These are **required** for a full pipeline run:

### 1. OpenAI API Key and Credits

An active [OpenAI account](https://platform.openai.com/) with API access and a **funded balance**. The pipeline uses `gpt-4.1-mini` by default and makes hundreds of API calls across four separate LLM use cases:

| Use Case | Description |
|----------|-------------|
| Property summaries | Each listing's reviews → structured summary with mention counts |
| Area summary | All property summaries → area-level insights |
| Correlation insights | Statistical data + descriptions → market analysis for ADR/Occupancy |
| Description scoring | Each listing description scored on 7 quality dimensions, then synthesized |

For a typical run of ~300 listings, expect significant API usage. The pipeline includes a built-in cost tracker (`utils/cost_tracker.py`) that logs every request to `logs/cost_tracking.json` so you can monitor spend.

### 2. Paid AirDNA Subscription

[AirDNA](https://www.airdna.co/) is a third-party short-term rental analytics platform. A **paid subscription** is required to access rentalizer data, which provides financial metrics not available from Airbnb directly:

- **ADR** (Average Daily Rate) — average price per booked night
- **Occupancy** — percentage of available days that are booked
- **Revenue** — annual rental revenue
- **Days Available** — how many days the property is listed per year

The pipeline automatically looks up each listing discovered in the Airbnb search on AirDNA's rentalizer page — no manual comp set creation required. Without AirDNA data, the correlation analysis and description quality analysis stages will lack the financial metrics needed to function.

## Features

- **AirDNA Per-Listing Lookup** — Enrich each listing with ADR, Occupancy, Revenue, and Days Available via Playwright/CDP rentalizer pages
- **Property Search** — Find Airbnb listings within a geographic area using zip code and `pyairbnb`
- **Review Scraping** — Pull all reviews for discovered listings with per-file caching
- **Property Details Scraping** — Scrape amenities, descriptions, house rules, and neighborhood info
- **Details Fileset Build** — Transform raw details + AirDNA financials into structured CSVs (amenity matrix, descriptions, house rules)
- **AI Property Summaries** — Generate structured summaries per property using GPT-4.1-mini: pros/cons with mention percentages, amenity analysis, and rating context vs. area average
- **AI Area Summary** — Roll up all property summaries into area-level trends and insights
- **Data Extraction** — LLM-powered parsing of summaries into structured numeric data with sentiment categories
- **Correlation Analysis** — Statistical comparison of top/bottom percentile tiers by ADR or Occupancy, with LLM-generated market insights
- **Description Quality Analysis** — OLS regression of ADR against 160+ features, LLM scoring of descriptions on 7 quality dimensions, and correlation of language quality with pricing premiums
- **TTL-Based Caching** — Pipeline cache with cascade invalidation prevents redundant scraping and API calls
- **Cost Tracking** — Monitor OpenAI API usage and costs per session

## Installation

**Requires Python 3.13.**

```bash
# Clone the repository
git clone https://github.com/M-CDevinW/AirBNB-Review-Scraper.git
cd AirBNB-Review-Scraper

# Install dependencies (or use: make setup)
pipenv install --dev

# Activate environment
pipenv shell

# Install Playwright browsers (required for AirDNA scraping)
pipenv run playwright install chromium

# Set OpenAI API key
export OPENAI_API_KEY="your-api-key-here"
```

## How It Works

The pipeline combines two data sources and four LLM use cases to produce market intelligence:

**Data Sources:**
- **Airbnb** (via `pyairbnb`) — listing search by geographic bounding box, review text, property details, amenities, descriptions, and house rules
- **AirDNA** (via Playwright/CDP) — financial metrics (ADR, Occupancy, Revenue, Days Available) scraped per-listing from AirDNA's rentalizer page via a logged-in Chrome session connected over Chrome DevTools Protocol

**AI Processing:**
- All OpenAI calls go through `review_aggregator/openai_aggregator.py`, which handles token estimation via `tiktoken`, automatic chunking at 120K tokens with a merge step, and 3 retries with exponential backoff
- Property-level prompts produce structured summaries with mention counts in "X of Y Reviews (Z%)" format
- Area-level prompts aggregate all property summaries into a single area analysis
- Correlation prompts receive statistical comparison data and produce actionable market insights
- Description prompts use a two-phase approach: first scoring each description on 7 dimensions (1–10), then synthesizing findings with top/bottom examples

**Caching:**
- TTL-based cache (`utils/pipeline_cache_manager.py`) checks file existence and `os.path.getmtime()` against the configured TTL — no metadata file needed
- Refreshing an early stage automatically cascades invalidation to all downstream stages
- Per-file caching for reviews and details allows incremental scraping of new listings

## Respectful Scraping

This pipeline automates data collection, but it is designed to browse no faster than a human would. Every scraping stage inserts randomized delays between requests, so the pace of data retrieval is consistent with a person manually clicking through listings. The AirDNA scraper goes further — it connects to a real Chrome browser session via Chrome DevTools Protocol, meaning it appears on the network as a normal logged-in user navigating page by page.

Key principles:

- **Human-speed pacing** — Randomized pauses between every request ensure automated browsing is no faster than manual browsing. There is no parallel request fan-out; listings are visited one at a time.
- **Caching prevents redundant requests** — TTL-based caching means previously scraped listings are never re-fetched unless their cache expires. A second run against the same zip code hits zero external endpoints if all data is still fresh.
- **Backoff on rate-limit signals** — If the pipeline detects signs of rate limiting (e.g., AirDNA returning empty results), it pauses for an extended cooldown period before retrying, rather than retrying immediately.
- **No API abuse** — OpenAI calls use exponential backoff with retry limits. Token usage and costs are tracked per-session so users can monitor spend.

This project is intended for personal market research. The scraping approach is deliberately conservative — the automation saves time by running unattended, not by going faster.

## Example Output

The `reports/` directory contains example analytical output from a full pipeline run on zipcode 97067 (Mount Hood, Oregon — 341 properties analyzed):

### Area Summary — [`reports/area_summary_97067.json`](reports/area_summary_97067.json)
Aggregated area-level insights from all property summaries. Identifies that listings are primarily cozy cabins, rustic chalets, and mountain homes near Mount Hood. Top positives: hot tubs, location, cleanliness, host communication. Top issues: hot tub maintenance, privacy concerns, WiFi reliability.

### ADR Correlation Analysis — [`reports/correlation_insights_adr_97067.md`](reports/correlation_insights_adr_97067.md)
Identifies what drives higher nightly rates. Key finding: high-ADR properties ($378/night avg) vs low-ADR ($206/night) differ most in Jacuzzi prevalence (+57.5%), Grill (+28.7%), and guest capacity (10.3 vs 4.7 guests).

> | Feature | Difference in Prevalence |
> |---------|-------------------------|
> | Jacuzzi | +57.5% |
> | Grill | +28.7% |
> | Ocean View | +27.6% |
> | Dishwasher | +24.1% |
> | Firepit | +20.7% |

### Occupancy Correlation Analysis — [`reports/correlation_insights_occupancy_97067.md`](reports/correlation_insights_occupancy_97067.md)
Identifies what drives higher booking rates. Key finding: pet-friendly policies (+11.8%), dedicated workspaces (+9.4%), and mountain views (+8.5%) most distinguish high-occupancy properties. Mid-sized properties (~6 guests) outperform larger ones.

### Description Quality Analysis — [`reports/description_quality_97067.md`](reports/description_quality_97067.md)
Uses OLS regression (R² = 0.873 from 160 features) to isolate the ADR premium attributable to description quality vs. property size. Scores each listing's description on evocativeness, specificity, emotional appeal, storytelling, USP clarity, professionalism, and completeness. Estimates a **$100–150/night language premium** for top descriptions.

> Improving Airbnb listing descriptions by focusing on **evocativeness**, **specificity**, and **emotional appeal** can unlock significant ADR premiums (~$100+ per night).

## Configuration

Edit `config.json` to configure the pipeline. All pipeline behavior is controlled here — there is no CLI argument interface.

### Pipeline Steps

| Key | Type | Description |
|-----|------|-------------|
| `search_results` | bool | Search for Airbnb listings by zipcode |
| `details_scrape` | bool | Scrape property details (amenities, rules) |
| `details_results` | bool | Transform scraped details + AirDNA financials into structured datasets |
| `reviews_scrape` | bool | Scrape reviews for listings in the zipcode |
| `comp_sets` | bool | Scrape AirDNA comp sets for property metrics |
| `listing_summaries` | bool | Generate AI summaries for each property |
| `area_summary` | bool | Generate area-level summary + extract structured data from summaries |
| `correlation_results` | bool | Run correlation analysis of amenities/capacity vs. ADR and Occupancy |
| `description_analysis` | bool | Run description quality scoring and regression analysis |

### Search Parameters

| Key | Type | Description |
|-----|------|-------------|
| `zipcode` | string | Target zip code (e.g., `"97067"`) |
| `iso_code` | string | Country code (e.g., `"us"`) |
| `num_listings_to_search` | int | Max listings to find in search |
| `num_listings_to_summarize` | int | Max listings to process with AI |
| `review_thresh_to_include_prop` | int | Minimum reviews required to process a listing |
| `num_summary_to_process` | int | Max property summaries to process in downstream stages |
| `dataset_use_categoricals` | bool | Use categorical encoding for amenity features in analysis |

### AirDNA Settings

| Key | Type | Description |
|-----|------|-------------|
| `min_days_available` | int | Minimum Days Available to include a listing (default: `100`) |
| `airdna_cdp_url` | string | Chrome DevTools Protocol URL (default: `http://localhost:9222`) |
| `airdna_inspect_mode` | bool | Pause after navigation for DOM selector discovery |

### Correlation Settings

| Key | Type | Description |
|-----|------|-------------|
| `correlation_metrics` | array | Metrics to analyze (e.g., `["adr", "occupancy"]`) |
| `correlation_top_percentile` | int | Top percentile tier threshold (e.g., `25` = top 25%) |
| `correlation_bottom_percentile` | int | Bottom percentile tier threshold (e.g., `25` = bottom 25%) |

### OpenAI Settings

| Key | Type | Description |
|-----|------|-------------|
| `openai.model` | string | Model to use (default: `"gpt-4.1-mini"`) |
| `openai.temperature` | float | Response randomness (0.0–1.0) |
| `openai.max_tokens` | int | Max tokens per response |
| `openai.chunk_token_limit` | int | Token limit per chunk sent to the API |
| `openai.enable_cost_tracking` | bool | Log API costs to `logs/cost_tracking.json` |

### Pipeline Caching (TTL)

The pipeline includes a TTL-based cache that prevents redundant scraping and processing. When enabled, each stage's outputs are tracked with timestamps. If all outputs for a stage are still within the TTL window, the stage is skipped entirely on the next run. For per-file stages (reviews, details), individual listings are skipped when their cached files are fresh.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pipeline_cache_enabled` | bool | `true` | Enable/disable pipeline-level TTL caching |
| `pipeline_cache_ttl_days` | int | `7` | Number of days before cached outputs expire |
| `force_refresh_search_results` | bool | `false` | Force re-run area search |
| `force_refresh_details_scrape` | bool | `false` | Force re-scrape all property details |
| `force_refresh_details_results` | bool | `false` | Force rebuild details fileset |
| `force_refresh_reviews_scrape` | bool | `false` | Force re-scrape all reviews |
| `force_refresh_comp_sets` | bool | `false` | Force re-run AirDNA scraping even if cached |
| `force_refresh_listing_summaries` | bool | `false` | Force regenerate property summaries |
| `force_refresh_area_summary` | bool | `false` | Force regenerate area summary + data extraction |
| `force_refresh_correlation_results` | bool | `false` | Force re-run correlation analysis |
| `force_refresh_description_analysis` | bool | `false` | Force re-run description quality analysis |

**How it works:**
- Freshness is determined by file existence and `os.path.getmtime()` — each stage declares its expected output files, and a stage is fresh when all files exist with mtime within the TTL
- On each run, the pipeline checks whether outputs exist and are within the TTL before executing a stage
- Refreshing an early stage cascades invalidation to all downstream stages
- The `force_refresh_*` flags let you bypass the cache for specific stages

**Example:** Run the full pipeline, then re-run immediately — all stages will be skipped:
```bash
pipenv run python main.py   # First run: executes all enabled stages
pipenv run python main.py   # Second run: skips cached stages
```

To force a single stage to re-run:
```json
{"force_refresh_reviews_scrape": true}
```

## Usage

### AirDNA Per-Listing Lookup

Enrich each discovered listing with financial metrics (ADR, Occupancy, Revenue, Days Available) from AirDNA's rentalizer page. The pipeline automatically feeds listing IDs from the Airbnb search into AirDNA — no manual comp set creation needed.

**Setup:**
1. Launch Chrome with remote debugging:
   ```bash
   make chrome-debug
   # Or manually:
   open -a "Google Chrome" --args --remote-debugging-port=9222
   ```
2. In the Chrome window that opens, navigate to [AirDNA](https://app.airdna.co) and log in with your account

**Run:**
```bash
# Set config.json: "comp_sets": true
pipenv run python main.py
# Or:
make scrape-airdna
```

The scraper visits `https://app.airdna.co/data/rentalizer?&listing_id=abnb_{id}` for each listing and extracts header metrics (Bedrooms, Bathrooms, Max Guests, Rating, Review Count) and KPI cards (Revenue, Days Available, Annual Revenue, Occupancy, ADR). All listings are saved regardless of Days Available; filtering by `min_days_available` (default: 100) is applied later when the cleaned amenities matrix is built in the `details_results` stage.

**Output:** `listing_{id}.json` — one file per listing in `outputs/05_comp_sets/`:
```json
{
    "1050769200886027711": {"ADR": 487.5, "Occupancy": 32, "Revenue": 51700.0, "Days_Available": 333, "Bedrooms": 4, "Bathrooms": 3, "Max_Guests": 15, "Rating": 4.7, "Review_Count": 287, "LY_Revenue": 0.0}
}
```

**Inspect mode:** If selectors break (AirDNA UI changes), enable `"airdna_inspect_mode": true` to pause the browser and use Playwright Inspector to discover new selectors.

### Basic Workflow

```bash
# 1. Scrape reviews for a zip code
# Set config.json: "reviews_scrape": true, "zipcode": "97067"
pipenv run python main.py

# 2. Generate property summaries
# Set config.json: "listing_summaries": true
pipenv run python main.py

# 3. Generate area summary
# Set config.json: "area_summary": true
pipenv run python main.py
```

### Full Pipeline Example

Enable all stages in `config.json`:

```json
{
  "search_results": true,
  "details_scrape": true,
  "details_results": true,
  "reviews_scrape": true,
  "comp_sets": true,
  "listing_summaries": true,
  "area_summary": true,
  "correlation_results": true,
  "description_analysis": true,
  "zipcode": "97067"
}
```

Then run:
```bash
pipenv run python main.py
```

## Pipeline Flow

```
Zip Code + config.json
        ↓
┌───────────────────────────────────────┐
│  1. Search Results                    │
│     pyairbnb.search_all() by zipcode  │
│     → outputs/01_search_results/      │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  2. Details Scrape                    │
│     pyairbnb.get_details() per listing│
│     → outputs/02_details_scrape/      │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  3. Details Results                   │
│     Raw details + AirDNA financials   │
│     → amenity matrix, descriptions    │
│     → outputs/03_details_results/     │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  4. Reviews Scrape                    │
│     pyairbnb.get_reviews() per listing│
│     → outputs/04_reviews_scrape/      │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  5. Comp Sets (AirDNA)                │
│     Playwright/CDP → Chrome → AirDNA  │
│     → outputs/05_comp_sets/           │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  6. Listing Summaries (GPT)           │
│     Reviews → structured summaries    │
│     → outputs/06_listing_summaries/   │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  7. Area Summary (GPT)                │
│     Summaries → area insights +       │
│     structured data extraction        │
│     → outputs/07_area_summary/        │
│     → reports/area_summary_*.md/.json │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  8. Correlation Results (GPT)         │
│     Top/bottom percentile comparison  │
│     → outputs/08_correlation_results/ │
│     → reports/correlation_insights_*  │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  9. Description Analysis              │
│     OLS regression + GPT scoring      │
│     → outputs/09_description_analysis/│
│     → reports/description_quality_*   │
└───────────────────────────────────────┘
```

## Output Files

| Directory | Content |
|-----------|---------|
| `outputs/01_search_results/` | Search results by zipcode |
| `outputs/02_details_scrape/` | Property details (amenities, rules, descriptions) |
| `outputs/03_details_results/` | Structured CSVs and JSON: amenity matrix, house rules, descriptions, neighborhood highlights |
| `outputs/04_reviews_scrape/` | Raw review JSON per listing |
| `outputs/05_comp_sets/` | AirDNA per-listing metrics (ADR, Occupancy, Days Available) + master comp set |
| `outputs/06_listing_summaries/` | AI-generated summary per property |
| `outputs/07_area_summary/` | Aggregated numeric data with sentiment categories |
| `outputs/08_correlation_results/` | Correlation statistics (JSON) for each metric |
| `outputs/09_description_analysis/` | Description quality statistics (JSON) |
| `reports/` | Markdown and JSON reports: area summaries, correlation insights, description quality analysis |
| `logs/cost_tracking.json` | OpenAI API cost logs per session |

## Architecture

For a detailed module map, data flow reference, and key patterns guide, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

```
main.py                          # Entry point — config-driven pipeline orchestrator
├── steps/
│   ├── __init__.py              # Shared helper (load_search_results)
│   ├── 01_search_results.py     # Listing discovery by zipcode
│   ├── 02_details_scrape.py     # Scrape property details
│   ├── 03_details_results.py    # Transform details + AirDNA → structured data
│   ├── 04_reviews_scrape.py     # Scrape reviews per listing
│   ├── 05_comp_sets.py          # AirDNA per-listing lookup + master comp set
│   ├── 06_listing_summaries.py  # Per-property AI summaries
│   ├── 07_area_summary.py       # Area-level AI summary + data extraction
│   ├── 08_correlation_results.py # Percentile-based metric correlation
│   └── 09_description_analysis.py # OLS regression + description scoring
├── scraper/
│   ├── airbnb_searcher.py       # Zip code → geo bounding box → listing search
│   ├── airdna_scraper.py        # AirDNA per-listing rentalizer scraper (Playwright/CDP)
│   ├── reviews_scraper.py       # Fetch reviews per listing
│   ├── details_scraper.py       # Fetch property details
│   ├── details_fileset_build.py # Transform to structured data + merge AirDNA financials
│   └── location_calculator.py   # Zip code → lat/lon → bounding box
├── review_aggregator/
│   ├── property_review_aggregator.py  # Per-property AI summaries
│   ├── area_review_aggregator.py      # Area-level AI summaries
│   ├── openai_aggregator.py           # OpenAI client with chunking, retry, cost tracking
│   ├── data_extractor.py              # LLM-powered numeric extraction & clustering
│   ├── correlation_analyzer.py        # Percentile-based metric correlation analysis
│   └── description_analyzer.py        # OLS regression + LLM description quality scoring
├── utils/
│   ├── cost_tracker.py          # OpenAI API cost tracking (per-session)
│   ├── pipeline_cache_manager.py # TTL-based caching with cascade invalidation
│   ├── local_file_handler.py    # File system utilities
│   └── tiny_file_handler.py     # JSON I/O helpers
└── prompts/
    ├── prompt.json              # Property-level prompt template
    ├── zipcode_prompt.json      # Area-level prompt template
    ├── correlation_prompt.json  # Correlation analysis prompts (ADR + Occupancy)
    └── description_analysis_prompt.json # Description scoring + synthesis prompts
```

## Running Tests

```bash
# Run full test suite with coverage (75% minimum required)
make test

# Or directly:
pipenv run pytest

# Fast mode — fail on first error, no coverage:
make test-fast

# Generate HTML coverage report:
make coverage
# → opens coverage_html/index.html
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make setup` | Install dependencies and activate pipenv shell |
| `make test` | Run pytest with coverage |
| `make test-fast` | Run pytest, fail-fast, no coverage |
| `make coverage` | Generate HTML coverage report |
| `make chrome-debug` | Launch Chrome with remote debugging port for AirDNA scraping |
| `make scrape-airdna` | Run AirDNA scraper standalone |

## Notebooks

| Notebook | Purpose |
|----------|---------|
| `eda_property_details.ipynb` | Exploratory data analysis of scraped property details and AirDNA metrics |
| `model_notebook.ipynb` | Modeling experiments on listing features and pricing relationships |

## Disclaimer

This tool scrapes data from Airbnb and AirDNA. Use of web scraping may be subject to the terms of service of these platforms. This project is intended for personal market research and analysis. Users are responsible for ensuring their use complies with applicable terms of service and laws.

## Contributing

Issues and pull requests are welcome. Please ensure all tests pass (`make test`) before submitting.

## License

MIT