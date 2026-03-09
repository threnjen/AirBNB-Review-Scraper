# Multi-Zipcode Pipeline Upgrade — Plan

Evolve the single-zipcode sequential pipeline into a multi-zipcode, two-phase architecture. All scraping across all zipcodes completes before any processing begins. Add latitude/longitude to the amenities matrix, introduce a point-of-interest config, renumber step files to reflect the new execution order.

---

## Stage 1: Config Schema Update
**Goal**: `config.json` supports a list of zipcodes and a destination lat/long point of interest.
**Success Criteria**:
- `config.json` contains `zipcodes` (list), `dest_lat` (float), `dest_long` (float)
- `load_config()` returns all three fields correctly
- `main.py` `AirBnbReviewAggregator.zipcode` property replaced with `zipcodes` returning the list
- All 342 existing tests pass
**Status**: Complete

### Changes
- **`config.json`**: Add `dest_lat` and `dest_long` as top-level numeric fields. *Note: user has already added these manually.*
- **`main.py`**: Replace the `zipcode` property (which reads `config.get("zipcode")`) with a `zipcodes` property returning `config.get("zipcodes", [])`.
- **`tests/unit/test_main.py`**: New — 3 tests for `zipcodes` property and config values.
- No other files need changes — individual step modules read `config.get("zipcode")` which will be injected per-zipcode in Stage 2.

---

## Stage 2: Multi-Zipcode Pipeline Orchestration
**Goal**: `main.py` loops over all zipcodes in two execution phases: scraping, then processing.
**Success Criteria**:
- For each zipcode, steps 01–04 + `listing_summaries` run in order
- Only after ALL zipcodes finish scraping, steps `details_results` through 09 run for each zipcode
- Each step module still receives `config.get("zipcode")` with the correct current zipcode
- New integration test verifies ordering: all scraping calls precede all processing calls
- All existing tests pass
**Status**: Not Started

### Changes
- **`main.py`**: Split `PIPELINE_STEPS` into `SCRAPING_STEPS` and `PROCESSING_STEPS`. Refactor `run_tasks_from_config()` with two outer loops:
  - Loop 1: for each zipcode → inject `config["zipcode"]` → run each enabled scraping step
  - Loop 2: for each zipcode → inject `config["zipcode"]` → run each enabled processing step
- **`utils/pipeline_cache_manager.py`**: Reorder `STAGE_ORDER` so `listing_summaries` precedes `details_results`. Add `details_results` to `CASCADE_TARGET_STAGES` (it is now a processing-phase stage).
- **`tests/integration/test_pipeline_integration.py`**: Add `TestMultiZipcodeOrchestration` class with a test that mocks `importlib.import_module`, runs with 2 zipcodes, and asserts last scraping call index < first processing call index.

### Design Decision: Zipcode Injection
Rather than changing every step module's `run(config, pipeline_cache)` signature, `main.py` sets `config["zipcode"]` before each step call. All 9 step modules already read `config.get("zipcode")` — no changes needed in step files for this stage.

---

## Stage 3: Renumber Pipeline Step Files
**Goal**: Step file names on disk reflect the new execution order.
**Success Criteria**:
- `steps/05_listing_summaries.py` exists (was `06_listing_summaries.py`)
- `steps/06_details_results.py` exists (was `05_details_results.py`)
- Module paths in `SCRAPING_STEPS`/`PROCESSING_STEPS` updated
- `py_compile` succeeds on both renamed files
- All tests pass
**Status**: Not Started

### New Numbering

| Old File | New File | Stage Name |
|----------|----------|------------|
| `01_search_results.py` | `01_search_results.py` | unchanged |
| `02_details_scrape.py` | `02_details_scrape.py` | unchanged |
| `03_airdna_data.py` | `03_airdna_data.py` | unchanged |
| `04_reviews_scrape.py` | `04_reviews_scrape.py` | unchanged |
| `06_listing_summaries.py` | **`05_listing_summaries.py`** | renumbered |
| `05_details_results.py` | **`06_details_results.py`** | moved to processing |
| `07_area_summary.py` | `07_area_summary.py` | unchanged |
| `08_correlation_results.py` | `08_correlation_results.py` | unchanged |
| `09_description_analysis.py` | `09_description_analysis.py` | unchanged |

### Changes
- `mv steps/06_listing_summaries.py steps/05_listing_summaries.py`
- `mv steps/05_details_results.py steps/06_details_results.py`
- **`main.py`**: Update module paths in both step lists
- **Tests**: Update any imports referencing old step module numbers (grep for `steps.05_` and `steps.06_`)
- `STAGE` constants inside the renamed step files do not change (they use stage names like `"listing_summaries"`, not numbers)
- `STAGE_OUTPUT_DIRS` in `pipeline_cache_manager.py` is keyed by stage name, not number — no change needed

---

## Stage 4: Add Latitude/Longitude to Amenities Matrix
**Goal**: Each listing's lat/lng appears as columns in `property_amenities_matrix_*.csv`.
**Success Criteria**:
- `property_amenities_matrix_{zipcode}.csv` contains `latitude` and `longitude` columns
- `property_amenities_matrix_cleaned_{zipcode}.csv` also retains these columns
- New unit test in `test_details_fileset_build.py` asserts lat/lng columns are present
- Existing tests pass
**Status**: Not Started

### Data Source
Step 02 details scrape JSON files contain coordinates at the top level:
```json
{"coordinates": {"latitude": 45.3364, "longitude": -121.9674}, ...}
```
Step 01 search results also have coordinates but use a misspelled key (`"longitud"` instead of `"longitude"`). Step 02 is the canonical source.

### Changes
- **`scraper/details_fileset_build.py`** → `parse_basic_details()`: After extracting `room_type`, read `property_details.get("coordinates", {})` and store `latitude` and `longitude` into `self.property_details[property_id]`.
- **`scraper/details_fileset_build.py`** → `clean_amenities_df()`: Verify `latitude` and `longitude` are NOT in `drop_cols`. They should pass through to both raw and cleaned CSVs.
- **`tests/unit/test_details_fileset_build.py`**: Add test fixture with coordinates in mock details JSON, assert output DataFrame contains `latitude` and `longitude` columns with correct values.

---

## Stage 5: Feature Engineering (Placeholder)
**Goal**: Placeholder for future geo-spatial feature engineering — to be designed separately.
**Success Criteria**: Planning document exists; no code changes.
**Status**: Deferred

### Planned Scope (design deferred)
1. **Distance-to-POI**: Haversine distance from each listing's lat/lng to `dest_lat`/`dest_long`. New column `distance_to_poi_km`.
2. **Distance bucketing**: Categorical bins (e.g., <5km, 5–15km, 15–30km, 30+km).
3. **Spatial density**: Listing count within radius, nearest-neighbor distances.
4. **ML integration**: Add distance features to `ml/train.py` `select_features()` and `NUMERIC_FEATURES`.
5. **Correlation integration**: Add to `NUMERIC_COLUMNS` in `review_aggregator/correlation_analyzer.py`.

### Future Files
- `utils/geo_utils.py` (new) — haversine and spatial utility functions
- `scraper/details_fileset_build.py` — distance calculation during matrix build
- `ml/train.py` — feature selection updates
- `review_aggregator/correlation_analyzer.py` — numeric columns update

---

## Dependencies

```
Stage 1 (Config) → Stage 2 (Orchestration) → Stage 3 (Renumber)
                                                    ↓
Stage 4 (Lat/Lng) — can run in parallel with Stages 2–3
                                                    ↓
Stage 5 (Feature Engineering) — depends on Stages 1 + 4
```
