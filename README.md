# AirBNB Review Scraper & Analyzer

An end-to-end pipeline that scrapes AirBNB property reviews by zip code, generates AI-powered summaries for each listing, and extracts aggregated area-level insights weighted by actual review counts.

## Features

- **AirDNA Comp Set Scraper** - Scrape AirDNA comp sets via Playwright, extracting Airbnb listing IDs with ADR, Occupancy, and Days Available
- **Property Search** - Find AirBNB listings within a geographic area using zip code
- **Review Scraping** - Pull all reviews for discovered listings
- **Property Details** - Scrape amenities, descriptions, house rules
- **AI Summaries** - Generate structured summaries per property using GPT-4.1-mini:
  - Pros/cons with mention percentages
  - Amenities analysis
  - Rating context vs. area average
- **Area-Level Insights** - Roll up property summaries into area trends
- **Data Extraction** - Parse numeric review data and cluster into categories with weighted aggregation
- **Caching** - TTL-based pipeline cache prevents redundant scraping and API calls
- **Cost Tracking** - Monitor OpenAI API usage

## Installation

```bash
# Clone the repository
git clone https://github.com/M-CDevinW/AirBNB-Review-Scraper.git
cd AirBNB-Review-Scraper

# Install dependencies
pipenv install

# Activate environment
pipenv shell

# Set OpenAI API key
export OPENAI_API_KEY="your-api-key-here"
```

## Configuration

Edit `config.json` to configure the pipeline:

### Pipeline Steps

| Key | Type | Description |
|-----|------|-------------|
| `scrape_airdna` | bool | Scrape AirDNA comp sets for property metrics |
| `scrape_reviews` | bool | Scrape reviews for listings in the zipcode |
| `scrape_details` | bool | Scrape property details (amenities, rules) |
| `build_details` | bool | Transform scraped details into structured datasets |
| `aggregate_reviews` | bool | Generate AI summaries for each property |
| `aggregate_summaries` | bool | Generate area-level summary from property summaries |
| `extract_data` | bool | Extract and aggregate numeric review data |

### Search Parameters

| Key | Type | Description |
|-----|------|-------------|
| `zipcode` | string | Target zip code (e.g., "97067") |
| `iso_code` | string | Country code (e.g., "us") |
| `num_listings_to_search` | int | Max listings to find in search |
| `num_listings_to_summarize` | int | Max listings to process with AI |
| `review_thresh_to_include_prop` | int | Minimum reviews required to process a listing |

### AirDNA Settings

| Key | Type | Description |
|-----|------|-------------|
| `airdna_comp_set_ids` | array | List of AirDNA comp set IDs to scrape |
| `airdna_cdp_url` | string | Chrome DevTools Protocol URL (default: `http://localhost:9222`) |
| `airdna_inspect_mode` | bool | Pause after navigation for DOM selector discovery |

### Custom Listings

| Key | Type | Description |
|-----|------|-------------|
| `use_custom_listings_file` | bool | Use custom listing IDs instead of search |
| `custom_filepath` | string | Path to custom listings JSON file |

### OpenAI Settings

| Key | Type | Description |
|-----|------|-------------|
| `openai.model` | string | Model to use (default: "gpt-4.1-mini") |
| `openai.temperature` | float | Response randomness (0.0-1.0) |
| `openai.max_tokens` | int | Max tokens per response |
| `openai.chunk_size` | int | Reviews per API call |
| `openai.enable_cost_tracking` | bool | Log API costs |

### Pipeline Caching (TTL)

The pipeline includes a TTL-based cache that prevents redundant scraping and processing. When enabled, each stage's outputs are tracked with timestamps. If all outputs for a stage are still within the TTL window, the stage is skipped entirely on the next run. For per-file stages (reviews, details), individual listings are skipped when their cached files are fresh.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pipeline_cache_enabled` | bool | `true` | Enable/disable pipeline-level TTL caching |
| `pipeline_cache_ttl_days` | int | `7` | Number of days before cached outputs expire |
| `force_refresh_scrape_airdna` | bool | `false` | Force re-run AirDNA scraping even if cached |
| `force_refresh_search` | bool | `false` | Force re-run area search |
| `force_refresh_reviews` | bool | `false` | Force re-scrape all reviews |
| `force_refresh_scrape_details` | bool | `false` | Force re-scrape all property details |
| `force_refresh_build_details` | bool | `false` | Force rebuild details fileset |
| `force_refresh_aggregate_reviews` | bool | `false` | Force regenerate property summaries |
| `force_refresh_aggregate_summaries` | bool | `false` | Force regenerate area summary |

**How it works:**
- Metadata is stored in `cache/pipeline_metadata.json`, recording when each output file was produced
- On each run, the pipeline checks whether outputs exist and are within the TTL before executing a stage
- The `force_refresh_*` flags let you bypass the cache for specific stages without affecting others

**Example:** Run the full pipeline, then re-run immediately — all stages 0–6 will be skipped:
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

**Prerequisites:**
1. Install Playwright browsers: `pipenv run playwright install chromium`
2. Launch Chrome with remote debugging:
   ```bash
   make chrome-debug
   # Or manually:
   open -a "Google Chrome" --args --remote-debugging-port=9222
   ```
3. In the Chrome window that opens, navigate to [AirDNA](https://app.airdna.co) and log in with your account

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

**Output:** `compset_{id}.json` — one file per comp set, matching the `custom_listing_ids.json` format:
```json
{
    "1050769200886027711": {"ADR": 945.57, "Occupancy": 39, "Days_Available": 335},
    "549180550450067551": {"ADR": 377.19, "Occupancy": 88, "Days_Available": 357}
}
```

To use scraped data in downstream pipeline stages, set `custom_filepath` to the output file:
```json
{"use_custom_listings_file": true, "custom_filepath": "compset_365519.json"}
```

**Inspect mode:** If selectors break (AirDNA UI changes), enable `"airdna_inspect_mode": true` to pause the browser and use Playwright Inspector to discover new selectors.

### Basic Workflow

```bash
# 1. Scrape reviews for a zip code
# Set config.json: "scrape_reviews": true, "zipcode": "97067"
python main.py

# 2. Generate property summaries
# Set config.json: "aggregate_reviews": true
python main.py

# 3. Extract aggregated area data
# Set config.json: "extract_data": true
python main.py
```

### Full Pipeline Example

```json
{
  "scrape_reviews": true,
  "scrape_details": true,
  "build_details": true,
  "aggregate_reviews": true,
  "aggregate_summaries": true,
  "extract_data": true,
  "zipcode": "97067"
}
```

## Pipeline Flow

```
Zip Code Input
      ↓
┌─────────────────────────────────────┐
│  1. Search AirBNB listings          │
│     → property_search_results/      │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│  2. Scrape reviews & details        │
│     → property_reviews_scraped/     │
│     → property_details_scraped/     │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│  3. Generate property summaries     │
│     (PropertyRagAggregator + GPT)   │
│     → property_generated_summaries/ │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│  4. Extract & aggregate data        │
│     (DataExtractor)                 │
│     → area_data_{zipcode}.json      │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│  5. Generate area summary           │
│     (AreaRagAggregator)             │
│     → generated_summaries_{zip}.json│
└─────────────────────────────────────┘
```

## Output Files

| Directory/File | Content |
|----------------|---------|
| `compset_{id}.json` | Scraped AirDNA comp set metrics per listing |
| `property_search_results/` | Search results by zipcode |
| `property_reviews_scraped/` | Raw review JSON per listing |
| `property_details_scraped/` | Property details (amenities, rules) |
| `property_details_results/` | Structured CSVs and JSON from details |
| `property_generated_summaries/` | AI-generated summary per property |
| `generated_summaries_{zip}.json` | Area-level AI summary |
| `area_data_{zip}.json` | Aggregated numeric data with categories |
| `logs/cost_tracking.json` | API cost logs |

## Architecture

```
main.py                          # Entry point
├── scraper/
│   ├── airbnb_searcher.py       # Zip code → listing search
│   ├── airdna_scraper.py        # AirDNA comp set scraper (Playwright/CDP)
│   ├── reviews_scraper.py       # Fetch reviews per listing
│   ├── details_scraper.py       # Fetch property details
│   └── details_fileset_build.py # Transform to structured data
├── review_aggregator/
│   ├── property_review_aggregator.py  # Per-property AI summaries
│   ├── area_review_aggregator.py      # Area-level AI summaries
│   ├── data_extractor.py              # Numeric extraction & clustering
│   └── openai_aggregator.py           # OpenAI client with caching
├── utils/
│   ├── cost_tracker.py          # API cost tracking
│   └── tiny_file_handler.py     # JSON I/O helpers
└── prompts/
    ├── prompt.json              # Property-level prompt template
    └── zipcode_prompt.json      # Area-level prompt template
```

## Running Tests

```bash
# Run integration tests
python tests/test_pipeline_integration.py

# Or with pytest
pytest tests/ -v
```

## License

MIT