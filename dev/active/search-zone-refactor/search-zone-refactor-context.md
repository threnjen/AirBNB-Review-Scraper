# Search Zone Refactor — Context

Key files, data findings, and architectural decisions for the zipcode → search zone refactor.

---

## Key Files (Grouped by Concern)

### Config & Entry Point
- `config.json` — current keys: `zipcodes` (array), `dest_lat`, `dest_long`, `iso_code`
- `main.py` — `AirBnbReviewAggregator` class, `PIPELINE_STEPS` list, `run_tasks_from_config()` loop
- `utils/tiny_file_handler.py` — `load_config()` anchored to repo root

### Search & Location
- `scraper/airbnb_searcher.py` — `airbnb_searcher(zipcode, iso_code)`, uses `location_calculator.locationer()`, saves `search_results_{zipcode}.json`
- `scraper/location_calculator.py` — `locationer(postal_code, iso_code)` → uses `pgeocode` to convert zipcode to ±0.14° bounding box

### Scraping Steps
- `steps/01_search_results.py` — delegates to `steps/__init__.py:load_search_results()`
- `steps/__init__.py` — `load_search_results()` reads `config["zipcode"]`, loads or runs search
- `steps/02_details_scrape.py` — reads `config["zipcode"]` for cache key
- `steps/03_airdna_data.py` — reads `config["zipcode"]` for `comp_set_{zipcode}.json` and cache key
- `steps/04_reviews_scrape.py` — passes `zipcode` to `scrape_reviews()` for `reviews_{id}.json`

### Processing Steps
- `steps/06_details_results.py` — `DetailsFilesetBuilder(zipcode=...)` builds amenities matrix
- `steps/05_listing_summaries.py` — `PropertyAggregator(zipcode=...)` generates per-listing LLM summaries
- `steps/07_area_summary.py` — `AreaAggregator(zipcode=...)` generates area-level summary
- `steps/08_correlation_results.py` — `CorrelationAnalyzer(zipcode=...)` runs correlation analysis
- `steps/09_description_analysis.py` — `DescriptionAnalyzer(zipcode=...)` scores descriptions

### Aggregators & Analyzers
- `review_aggregator/property_review_aggregator.py` — `PropertyAggregator.task_chain()`: writes `listing_summary_{zipcode}_{listing_id}.json`, reads `reviews_*` files (no zipcode filter — contamination risk)
- `review_aggregator/area_review_aggregator.py` — `AreaAggregator.task_chain()`: filters `listing_summary_{zipcode}_*`, writes `reports/area_summary_{zipcode}.md`
- `review_aggregator/correlation_analyzer.py` — reads `property_amenities_matrix_cleaned_{zipcode}.csv`, writes reports
- `review_aggregator/description_analyzer.py` — reads `property_amenities_matrix_cleaned_{zipcode}.csv`, writes reports

### Data Processing
- `scraper/details_fileset_build.py` — `DetailsFilesetBuilder`: builds amenities matrix CSV from property detail JSONs + AirDNA comp set; `build_fileset()`, `clean_amenities_df()`, `parse_basic_details()`, `parse_amenity_flags()`
- `scraper/reviews_scraper.py` — `scrape_reviews(zipcode, ...)`: saves `reviews_{id}.json`

### Cache Manager
- `utils/pipeline_cache_manager.py` — `PipelineCacheManager`: `STAGE_ORDER`, `STAGE_OUTPUT_DIRS`, `expected_outputs(stage, zipcode)`, `should_run_stage(stage, zipcode)`, `clear_stage_for_zipcode(stage, zipcode)`, `is_stage_fresh(stage, zipcode)`

### Prompts
- `prompts/prompt.json` — per-listing prompt with `{ZIP_CODE_HERE}`, `{ISO_CODE_HERE}` placeholders
- `prompts/zipcode_prompt.json` — area-level prompt with `{ZIP_CODE_HERE}`, `{ISO_CODE_HERE}` placeholders

### Tests (Major Impact)
- `tests/fixtures/sample_data.json` — `sample_config` has `"zipcode": "97067"`
- `tests/conftest.py` — `mock_pgeocode` fixture
- `tests/unit/test_pipeline_cache_manager.py` — extensive zipcode in paths and assertions
- `tests/unit/test_property_review_aggregator.py` — zipcode in fixtures and `{ZIP_CODE_HERE}` prompts
- `tests/unit/test_area_review_aggregator.py` — zipcode filter assertions
- `tests/integration/test_pipeline_integration.py` — imports `SCRAPING_STEPS`/`PROCESSING_STEPS`, tests ordering, zipcode injection per step

---

## Data Findings

### Search Results Structure (pyairbnb `search_all`)
Each listing in `outputs/01_search_results/search_results_{zip}.json` contains:
```
{
  "room_id": 739518952229863292,
  "name": "Ranger's Rest | Historic Mt Hood Cabin w/ Hot Tub",
  "title": "Cabin in Rhododendron",
  "coordinates": {"latitude": 45.344290712906435, "longitud": -121.93318404472397},
  ...
}
```
**Note**: pyairbnb has a typo — key is `"longitud"` (missing final "e"), not `"longitude"`.

### Property Details Structure (pyairbnb `get_details`)
Each file in `outputs/02_details_scrape/property_details_{id}.json` starts with:
```
{
  "coordinates": {"latitude": 45.36997, "longitude": -121.91467},
  "room_type": "Entire home/apt",
  ...
}
```
Property details uses the correct `"longitude"` key. This is the reliable source for lat/lng in the amenities matrix.

### AirDNA Comp Set Structure
`outputs/03_airdna_data/comp_set_{zip}.json` and per-listing `listing_{id}.json` — financial data only (ADR, Occupancy, Days_Available, LY_Revenue). No coordinates.

---

## Architectural Decisions

### D1: `search_zone_name` as universal identifier
- Replaces zipcode in ALL file paths, cache keys, and pipeline scoping
- User-supplied string (e.g., `"mt_hood_corridor"`) — must be filesystem-safe
- Used in aggregate files (`area_summary_{zone}.md`, matrix CSVs, reports)
- NOT used in per-listing files (`property_details_{id}.json`, `listing_summary_{id}.json`)

### D2: Per-listing files drop zone prefix
- `listing_summary_{listing_id}.json` — no zone/zipcode prefix needed
- `property_details_{id}.json` — already has no prefix
- `reviews_{zone}_{id}.json` — keeps zone prefix to avoid cross-zone contamination in review files (reviews have no internal listing ID key to distinguish)

### D3: Euclidean distance model
- At ~45°N latitude: 1° lat ≈ 69 miles, 1° lon ≈ 49 miles
- Convert `search_radius_miles` to degree offsets for bounding box
- Post-search filter removes listings outside the circular radius (bounding box is square)
- `boxed_search` grid dimensions remain configurable (currently hardcoded to 2)

### D4: Lat/lng source for amenities matrix
- Use `property_details_{id}.json` → `coordinates.latitude` / `coordinates.longitude` (correct key names)
- Do NOT use search results (typo key `"longitud"`, less precise)

### D5: `dest_lat` / `dest_long` remain as-is
- These are the POI (point of interest) for feature engineering distance calculations
- Completely separate concept from `start_lat` / `start_long` (search center)
- Feature engineering plan depends on these + lat/lng in matrix (Phase 4 unblocks it)

### D6: Pipeline reorder — swap steps 05 and 06
- Simplest approach: renumber so listing_summaries becomes 05, details_results becomes 06
- Maintains the principle: all scraping (01–04) before all processing (05–09)
- Integration tests already assert scraping-before-processing ordering

### D7: `pgeocode` removal
- If zipcode geocoding is fully removed, `pgeocode` has no remaining use
- Remove from `Pipfile` in Phase 6 after confirming no references remain

### D8: Single-zone per run (no multi-zone loop)
- Current architecture: one zone per pipeline run (matches old single-zipcode behavior)
- Multi-zone support (outer loop) deferred as a separate future enhancement
- Config accepts one `search_zone_name`, one `start_lat`, one `start_long`

---

## Interaction with Existing Plans

### `dev/active/fix-concerns/`
- Stage 5 (Performance) is independent and unaffected by this refactor
- Stages 1–4 are already complete

### `dev/active/feature-engineering/`
- Blocked on lat/lng columns in amenities matrix (Phase 4 of this refactor)
- Prerequisites section cites "Multi-zipcode upgrade Stage 4" — update to reference Phase 4 here
- `dest_lat`/`dest_long` already in config (prerequisite met)

### Cross-zone contamination bug (CONCERNS.md)
- `property_review_aggregator.py` currently loads ALL `reviews_*` files from `outputs/04_reviews_scrape/` — no zipcode filtering
- This refactor resolves it: review files keep `reviews_{zone}_{id}.json` naming; `task_chain()` should filter by zone prefix
