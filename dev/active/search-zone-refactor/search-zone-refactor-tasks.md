# Search Zone Refactor — Tasks

Checklist of work items per phase. Mark items `[x]` as they are completed.

---

## Phase 1: Config & Search Zone Foundation

- [x] Update `config.json`: remove `zipcodes` array, add `start_lat`, `start_long`, `search_radius_miles`, `search_zone_name`
- [x] Update `main.py`: remove `zipcodes` property, inject `search_zone_name` into step config where `zipcode` was injected
- [x] Update `tests/fixtures/sample_data.json`: replace `"zipcode": "97067"` with new config keys
- [x] Update `tests/conftest.py`: update any fixtures referencing zipcode config
- [x] Write tests for config validation (zone name is filesystem-safe, lat/lng are valid floats, radius > 0)
- [x] Run full test suite — all tests pass

---

## Phase 2: Refactor Airbnb Searcher — Lat/Lng Radius Search

- [ ] Add `bounding_box_from_center(lat, lon, radius_miles)` to `scraper/location_calculator.py`
- [ ] Write tests for `bounding_box_from_center` — correct degree offsets, edge cases
- [ ] Refactor `scraper/airbnb_searcher.py`: new signature accepting `start_lat`, `start_long`, `search_radius_miles`, `search_zone_name`
- [ ] Add post-search Euclidean distance filter (handle pyairbnb `"longitud"` typo key)
- [ ] Write tests for post-search radius filtering
- [ ] Update search result save path to `search_results_{search_zone_name}.json`
- [ ] Update `steps/__init__.py` `load_search_results()` to use `search_zone_name`
- [ ] Update `steps/01_search_results.py` to pass new config keys
- [ ] Remove or deprecate `locationer()` function
- [ ] Run full test suite — all tests pass

---

## Phase 3: Rename All Output Files — Zipcode to Zone Name

### Step files (zipcode → search_zone_name in config reads and file paths)
- [ ] `steps/02_details_scrape.py` — cache key uses `search_zone_name`
- [ ] `steps/03_airdna_data.py` — `comp_set_{zone}.json`, cache key
- [ ] `steps/04_reviews_scrape.py` — passes zone name to `scrape_reviews()`
- [ ] `steps/05_details_results.py` — matrix files use zone name
- [ ] `steps/06_listing_summaries.py` — passes zone name to `PropertyAggregator`
- [ ] `steps/07_area_summary.py` — passes zone name to `AreaAggregator`
- [ ] `steps/08_correlation_results.py` — passes zone name to `CorrelationAnalyzer`
- [ ] `steps/09_description_analysis.py` — passes zone name to `DescriptionAnalyzer`

### Scrapers
- [ ] `scraper/reviews_scraper.py` — rename `zipcode` param → `zone_name`; file path `reviews_{zone}_{id}.json`
- [ ] `scraper/details_fileset_build.py` — rename `zipcode` field → `zone_name`; all output file paths

### Aggregators
- [ ] `review_aggregator/property_review_aggregator.py` — rename `zipcode` field → `zone_name`; listing summary files become `listing_summary_{listing_id}.json` (drop zone prefix)
- [ ] `review_aggregator/property_review_aggregator.py` — filter review files by `reviews_{zone_name}_` prefix (fix cross-zone contamination bug)
- [ ] `review_aggregator/area_review_aggregator.py` — rename `zipcode` field; update file filter to `listing_summary_` prefix; update output path
- [ ] `review_aggregator/correlation_analyzer.py` — rename `zipcode` → `zone_name` in all paths
- [ ] `review_aggregator/description_analyzer.py` — rename `zipcode` → `zone_name` in all paths

### Cache Manager
- [ ] `utils/pipeline_cache_manager.py` — rename all `zipcode` parameters → `zone_name`
- [ ] `utils/pipeline_cache_manager.py` — update all `expected_outputs()` file path patterns
- [ ] `utils/pipeline_cache_manager.py` — rename `clear_stage_for_zipcode()` → `clear_stage_for_zone()`
- [ ] `utils/pipeline_cache_manager.py` — update `listing_summaries` expected outputs to `listing_summary_{lid}.json` (no zone prefix)

### Prompts
- [ ] `prompts/prompt.json` — replace `{ZIP_CODE_HERE}` with `{SEARCH_ZONE_HERE}`; update prompt text
- [ ] `prompts/zipcode_prompt.json` — rename file to `zone_prompt.json`; replace placeholder; update text
- [ ] Update all code that loads `zipcode_prompt.json` to load `zone_prompt.json`

### Tests
- [ ] Update `tests/unit/test_pipeline_cache_manager.py` — all zipcode references
- [ ] Update `tests/unit/test_property_review_aggregator.py` — zipcode references and `{ZIP_CODE_HERE}`
- [ ] Update `tests/unit/test_area_review_aggregator.py` — zipcode filter assertions
- [ ] Update `tests/integration/test_pipeline_integration.py` — zipcode references throughout
- [ ] Run full test suite — all tests pass

---

## Phase 4: Add Per-Listing Lat/Lng to Amenities Matrix

- [ ] In `scraper/details_fileset_build.py` `build_fileset()`: extract `coordinates.latitude` and `coordinates.longitude` from each property details JSON
- [ ] Store lat/lng in `self.property_details[property_id]`
- [ ] Verify `clean_amenities_df()` does NOT drop `latitude`/`longitude` columns
- [ ] Write tests: lat/lng columns present in both raw and cleaned matrix output
- [ ] Write tests: missing coordinates handled gracefully (default to None/NaN)
- [ ] Run full test suite — all tests pass

---

## Phase 5: Reorder Pipeline Steps — Scraping Before Processing

- [ ] Rename `steps/06_listing_summaries.py` → `steps/05_listing_summaries.py`
- [ ] Rename `steps/05_details_results.py` → `steps/06_details_results.py`
- [ ] Update `main.py` `PIPELINE_STEPS` order
- [ ] Update `utils/pipeline_cache_manager.py` `STAGE_ORDER`
- [ ] Update `utils/pipeline_cache_manager.py` `STAGE_OUTPUT_DIRS` (if numbering changes in dir names)
- [ ] Update test references to step numbers and ordering expectations
- [ ] Run full test suite — all tests pass

---

## Phase 6: Final Zipcode Sweep & Documentation

### Code cleanup
- [ ] Global search: rename all remaining `zipcode` variable/parameter names → `zone_name`/`search_zone_name`
- [ ] Remove `pgeocode` from `Pipfile` (if no longer used)
- [ ] Remove `mock_pgeocode` fixture from `tests/conftest.py` (if no longer used)
- [ ] Verify: `grep -ri "zipcode\|zip_code\|zip code" --include="*.py" --include="*.json"` returns zero hits

### Documentation
- [ ] Update `README.md` — new config format, search model, pipeline diagram
- [ ] Update `.planning/codebase/ARCHITECTURE.md` — search model, file paths, pipeline flow
- [ ] Update `.planning/codebase/STRUCTURE.md` — output file naming conventions
- [ ] Update `.planning/codebase/CONVENTIONS.md` — naming patterns if applicable
- [ ] Update `.planning/codebase/CONCERNS.md` — mark cross-zone contamination as resolved; update scaling limits
- [ ] Update `.planning/codebase/INTEGRATIONS.md` — search model description
- [ ] Update `dev/active/feature-engineering/feature-engineering-plan.md` — update prerequisites to reference this refactor's Phase 4

### Final verification
- [ ] Run full test suite — all 342+ tests pass
- [ ] Verify all output directory names are consistent
- [ ] Run `pipenv run python -m py_compile main.py` — compiles cleanly
