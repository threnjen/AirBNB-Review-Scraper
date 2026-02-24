# AirBNB Review Scraper & Analyzer

An end-to-end pipeline that scrapes AirBNB property reviews by zip code, generates AI-powered summaries for each listing, and extracts aggregated area-level insights weighted by actual review counts.

## Features

- **Property Search** - Find AirBNB listings within a geographic area using zip code
- **Review Scraping** - Pull all reviews for discovered listings
- **Property Details** - Scrape amenities, descriptions, house rules
- **AI Summaries** - Generate structured summaries per property using GPT-4o-mini:
  - Pros/cons with mention percentages
  - Amenities analysis
  - Rating context vs. area average
- **Area-Level Insights** - Roll up property summaries into area trends
- **Data Extraction** - Parse numeric review data and cluster into categories with weighted aggregation
- **Caching** - Reduce API costs with 7-day response cache
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

### Custom Listings

| Key | Type | Description |
|-----|------|-------------|
| `use_custom_listings_file` | bool | Use custom listing IDs instead of search |
| `custom_filepath` | string | Path to custom listings JSON file |

### OpenAI Settings

| Key | Type | Description |
|-----|------|-------------|
| `openai.model` | string | Model to use (default: "gpt-4o-mini") |
| `openai.temperature` | float | Response randomness (0.0-1.0) |
| `openai.max_tokens` | int | Max tokens per response |
| `openai.chunk_size` | int | Reviews per API call |
| `openai.enable_caching` | bool | Cache responses to reduce costs |
| `openai.enable_cost_tracking` | bool | Log API costs |

## Usage

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
| `property_search_results/` | Search results by zipcode |
| `property_reviews_scraped/` | Raw review JSON per listing |
| `property_details_scraped/` | Property details (amenities, rules) |
| `property_details_results/` | Structured CSVs and JSON from details |
| `property_generated_summaries/` | AI-generated summary per property |
| `generated_summaries_{zip}.json` | Area-level AI summary |
| `area_data_{zip}.json` | Aggregated numeric data with categories |
| `cache/summaries/` | Cached OpenAI responses |
| `logs/cost_tracking.json` | API cost logs |

## Architecture

```
main.py                          # Entry point
├── scraper/
│   ├── airbnb_searcher.py       # Zip code → listing search
│   ├── reviews_scraper.py       # Fetch reviews per listing
│   ├── details_scraper.py       # Fetch property details
│   └── details_fileset_build.py # Transform to structured data
├── review_aggregator/
│   ├── property_review_aggregator.py  # Per-property AI summaries
│   ├── area_review_aggregator.py      # Area-level AI summaries
│   ├── data_extractor.py              # Numeric extraction & clustering
│   └── openai_aggregator.py           # OpenAI client with caching
├── utils/
│   ├── cache_manager.py         # Response caching
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