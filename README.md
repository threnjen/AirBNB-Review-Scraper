# AirBNB Review Scraper & Analyzer

An end-to-end pipeline for short-term rental market analysis. Given a zip code, it scrapes hundreds of Airbnb listings and their reviews, generates AI-powered summaries using GPT-4.1-mini, builds structured amenity and financial datasets by merging Airbnb data with AirDNA comp set metrics, and produces market-intelligence reports that identify what drives higher nightly rates and occupancy. The final output includes correlation analyses (e.g., "Jacuzzi presence correlates with +57.5% higher ADR"), description quality scoring via OLS regression, and actionable recommendations for hosts — all generated automatically from a single `config.json`.

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

[AirDNA](https://www.airdna.co/) is a third-party short-term rental analytics platform. A **paid subscription** is required to access comp set features, which provide financial metrics not available from Airbnb directly:

- **ADR** (Average Daily Rate) — average price per booked night
- **Occupancy** — percentage of available days that are booked
- **Days Available** — how many days the property is listed per year

Without AirDNA data, the correlation analysis and description quality analysis stages will lack the financial metrics needed to function.

### 3. Manually Created AirDNA Comp Sets

You must **manually create comp sets** in the AirDNA web app for your area of interest before running the pipeline. A comp set is a user-curated group of comparable Airbnb listings that AirDNA tracks together. The scraper reads existing comp sets but does not create them.

**To set up comp sets:**
1. Log into [AirDNA](https://app.airdna.co)
2. Navigate to the Comp Sets section
3. Create one or more comp sets containing listings in your target area
4. Copy each comp set's ID from the URL (e.g., `https://app.airdna.co/data/comp-sets/365519` → ID is `365519`)
5. Add the IDs to `config.json` under `airdna_comp_set_ids`

## Features

- **AirDNA Comp Set Scraping** — Extract listing IDs with ADR, Occupancy, and Days Available via Playwright/CDP
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
- **AirDNA** (via Playwright/CDP) — financial metrics (ADR, Occupancy, Days Available) scraped from a logged-in Chrome session connected over Chrome DevTools Protocol

**AI Processing:**
- All OpenAI calls go through `review_aggregator/openai_aggregator.py`, which handles token estimation via `tiktoken`, automatic chunking at 120K tokens with a merge step, and 3 retries with exponential backoff
- Property-level prompts produce structured summaries with mention counts in "X of Y Reviews (Z%)" format
- Area-level prompts aggregate all property summaries into a single area analysis
- Correlation prompts receive statistical comparison data and produce actionable market insights
- Description prompts use a two-phase approach: first scoring each description on 7 dimensions (1–10), then synthesizing findings with top/bottom examples

**Caching:**
- TTL-based cache (`utils/pipeline_cache_manager.py`) tracks timestamps for all output files in `cache/pipeline_metadata.json`
- Refreshing an early stage automatically cascades invalidation to all downstream stages
- Per-file caching for reviews and details allows incremental scraping of new listings

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
| `scrape_airdna` | bool | Scrape AirDNA comp sets for property metrics |
| `scrape_reviews` | bool | Scrape reviews for listings in the zipcode |
| `scrape_details` | bool | Scrape property details (amenities, rules) |
| `aggregate_reviews` | bool | Generate AI summaries for each property |
| `aggregate_summaries` | bool | Generate area-level summary from property summaries |
| `build_details` | bool | Transform scraped details into structured datasets |
| `extract_data` | bool | Extract and aggregate numeric review data via LLM |
| `analyze_correlations` | bool | Run correlation analysis of amenities/capacity vs. ADR and Occupancy |
| `analyze_descriptions` | bool | Run description quality scoring and regression analysis |

### Search Parameters

| Key | Type | Description |
|-----|------|-------------|
| `zipcode` | string | Target zip code (e.g., `"97067"`) |
| `iso_code` | string | Country code (e.g., `"us"`) |
| `num_listings_to_search` | int | Max listings to find in search |
| `num_listings_to_summarize` | int | Max listings to process with AI |
| `review_thresh_to_include_prop` | int | Minimum reviews required to process a listing |

### AirDNA Settings

| Key | Type | Description |
|-----|------|-------------|
| `airdna_comp_set_ids` | array | List of AirDNA comp set IDs to scrape |
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
| `force_refresh_search` | bool | `false` | Force re-run area search |
| `force_refresh_scrape_airdna` | bool | `false` | Force re-run AirDNA scraping even if cached |
| `force_refresh_reviews` | bool | `false` | Force re-scrape all reviews |
| `force_refresh_scrape_details` | bool | `false` | Force re-scrape all property details |
| `force_refresh_aggregate_reviews` | bool | `false` | Force regenerate property summaries |
| `force_refresh_aggregate_summaries` | bool | `false` | Force regenerate area summary |
| `force_refresh_build_details` | bool | `false` | Force rebuild details fileset |
| `force_refresh_extract_data` | bool | `false` | Force re-run data extraction |
| `force_refresh_analyze_correlations` | bool | `false` | Force re-run correlation analysis |
| `force_refresh_analyze_descriptions` | bool | `false` | Force re-run description quality analysis |

**How it works:**
- Metadata is stored in `cache/pipeline_metadata.json`, recording when each output file was produced
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
{"force_refresh_reviews": true}
```

## Usage

### AirDNA Comp Set Scraping

Scrape property metrics (ADR, Occupancy, Days Available) from your AirDNA comp sets.

**Setup:**
1. Launch Chrome with remote debugging:
   ```bash
   make chrome-debug
   # Or manually:
   open -a "Google Chrome" --args --remote-debugging-port=9222
   ```
2. In the Chrome window that opens, navigate to [AirDNA](https://app.airdna.co) and log in with your account

**Scrape a comp set:**
```bash
# 1. Set your comp set IDs in config.json:
#    "scrape_airdna": true,
#    "airdna_comp_set_ids": ["365519"]

# 2. Run the pipeline (or standalone):
pipenv run python main.py
# Or:
make scrape-airdna
```

**Output:** `compset_{id}.json` — one file per comp set in `outputs/01_comp_sets/`:
```json
{
    "1050769200886027711": {"ADR": 945.57, "Occupancy": 39, "Days_Available": 335},
    "549180550450067551": {"ADR": 377.19, "Occupancy": 88, "Days_Available": 357}
}
```

**Inspect mode:** If selectors break (AirDNA UI changes), enable `"airdna_inspect_mode": true` to pause the browser and use Playwright Inspector to discover new selectors.

### Basic Workflow

```bash
# 1. Scrape reviews for a zip code
# Set config.json: "scrape_reviews": true, "zipcode": "97067"
pipenv run python main.py

# 2. Generate property summaries
# Set config.json: "aggregate_reviews": true
pipenv run python main.py

# 3. Generate area summary
# Set config.json: "aggregate_summaries": true
pipenv run python main.py
```

### Full Pipeline Example

Enable all stages in `config.json`:

```json
{
  "scrape_airdna": true,
  "scrape_reviews": true,
  "scrape_details": true,
  "aggregate_reviews": true,
  "aggregate_summaries": true,
  "build_details": true,
  "extract_data": true,
  "analyze_correlations": true,
  "analyze_descriptions": true,
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
│  0. AirDNA Comp Set Scraping          │
│     Playwright/CDP → Chrome → AirDNA  │
│     → outputs/01_comp_sets/           │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  1. Listing Discovery                 │
│     pyairbnb.search_all() or comp set │
│     IDs → outputs/02_search_results/  │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  2. Review Scraping                   │
│     pyairbnb.get_reviews() per listing│
│     → outputs/03_reviews_scraped/     │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  3. Details Scraping                  │
│     pyairbnb.get_details() per listing│
│     → outputs/04_details_scraped/     │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  4. Property Summary Generation (GPT) │
│     Reviews → structured summaries    │
│     → outputs/06_generated_summaries/ │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  5. Area Summary Generation (GPT)     │
│     All summaries → area insights     │
│     → reports/area_summary_*.md/.json │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  6. Details Fileset Build             │
│     Raw details + AirDNA financials   │
│     → amenity matrix, descriptions    │
│     → outputs/05_details_results/     │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  7. Data Extraction (GPT)             │
│     Summaries → structured categories │
│     → outputs/07_extracted_data/      │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  8. Correlation Analysis (GPT)        │
│     Top/bottom percentile comparison  │
│     → outputs/08_correlation_results/ │
│     → reports/correlation_insights_*  │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  9. Description Quality Analysis      │
│     OLS regression + GPT scoring      │
│     → outputs/09_description_analysis/│
│     → reports/description_quality_*   │
└───────────────────────────────────────┘
```

## Output Files

| Directory | Content |
|-----------|---------|
| `outputs/01_comp_sets/` | AirDNA comp set metrics per listing (ADR, Occupancy, Days Available) |
| `outputs/02_search_results/` | Search results by zipcode |
| `outputs/03_reviews_scraped/` | Raw review JSON per listing |
| `outputs/04_details_scraped/` | Property details (amenities, rules, descriptions) |
| `outputs/05_details_results/` | Structured CSVs and JSON: amenity matrix, house rules, descriptions, neighborhood highlights |
| `outputs/06_generated_summaries/` | AI-generated summary per property |
| `outputs/07_extracted_data/` | Aggregated numeric data with sentiment categories |
| `outputs/08_correlation_results/` | Correlation statistics (JSON) for each metric |
| `outputs/09_description_analysis/` | Description quality statistics (JSON) |
| `reports/` | Markdown and JSON reports: area summaries, correlation insights, description quality analysis |
| `logs/cost_tracking.json` | OpenAI API cost logs per session |

## Architecture

```
main.py                          # Entry point — config-driven pipeline orchestrator
├── scraper/
│   ├── airbnb_searcher.py       # Zip code → geo bounding box → listing search
│   ├── airdna_scraper.py        # AirDNA comp set scraper (Playwright/CDP)
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

## Disclaimer

This tool scrapes data from Airbnb and AirDNA. Use of web scraping may be subject to the terms of service of these platforms. This project is intended for personal market research and analysis. Users are responsible for ensuring their use complies with applicable terms of service and laws.

## Contributing

Issues and pull requests are welcome. Please ensure all tests pass (`make test`) before submitting.

## License

MIT