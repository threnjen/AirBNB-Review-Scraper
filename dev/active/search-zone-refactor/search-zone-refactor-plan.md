# Search Zone Refactor — Plan

Replace the zipcode-based pipeline model with a lat/lng center + Euclidean mile radius search. Introduce `search_zone_name` as the universal identifier in all file paths, cache keys, and prompt placeholders. Reorder pipeline so all scraping precedes processing. Add per-listing lat/lng to the amenities matrix.

---

## Phase 1: Config & Search Zone Foundation

**Goal**: Replace zipcode config keys with `start_lat`, `start_long`, `search_radius_miles`, and `search_zone_name`. Remove the `zipcodes` array.

**Success Criteria**:
- `config.json` has `start_lat`, `start_long`, `search_radius_miles`, `search_zone_name` — no `zipcodes` key
- `main.py` injects `search_zone_name` into step config where `zipcode` was previously injected
- `tests/fixtures/sample_data.json` uses new keys
- All tests compile and pass

**Status**: Complete

---

## Phase 2: Refactor Airbnb Searcher — Lat/Lng Radius Search

**Goal**: Replace zipcode geocoding with direct lat/lng bounding box calculation and Euclidean radius filtering.

**Success Criteria**:
- `location_calculator.py` has `bounding_box_from_center(lat, lon, radius_miles)` returning `(ne_lat, sw_lat, ne_lon, sw_lon)`
- `airbnb_searcher` accepts `start_lat`, `start_long`, `search_radius_miles`, `search_zone_name` — no `zipcode` parameter
- Post-search filter discards listings outside the Euclidean radius (bounding box is a square; trim to circle)
- Search results saved as `search_results_{search_zone_name}.json`
- `load_search_results()` in `steps/__init__.py` uses `search_zone_name`
- Old `locationer()` function removed or deprecated
- Tests for new radius calculation and post-search filtering

**Status**: Complete

---

## Phase 3: Rename All Output Files — Zipcode to Zone Name

**Goal**: Replace every `_{zipcode}` suffix in output filenames, cache keys, and prompt placeholders with `_{search_zone_name}`. Drop zone prefix from per-listing files.

**Success Criteria**:
- All output files use `{search_zone_name}` instead of `{zipcode}` in their names
- Per-listing files drop zone prefix: `listing_summary_{listing_id}.json` (was `listing_summary_{zipcode}_{listing_id}.json`)
- Cache manager `expected_outputs()` uses zone name everywhere
- Prompt templates use `{SEARCH_ZONE_HERE}` instead of `{ZIP_CODE_HERE}`; prompt text updated accordingly
- `zipcode_prompt.json` renamed to `zone_prompt.json`
- No remaining `zipcode` references in output file paths
- All tests pass

**Status**: Not Started

---

## Phase 4: Add Per-Listing Lat/Lng to Amenities Matrix

**Goal**: Extract latitude/longitude from scraped property details and add as columns in the amenities matrix.

**Success Criteria**:
- `property_amenities_matrix_{zone}.csv` and cleaned variant include `latitude` and `longitude` columns
- Values sourced from `property_details_{id}.json` → `coordinates.latitude` / `coordinates.longitude`
- `latitude` and `longitude` are NOT dropped in `clean_amenities_df()`
- Tests verify columns appear in both raw and cleaned matrix
- Feature engineering plan prerequisites are met (unblocks `dev/active/feature-engineering/`)

**Status**: Not Started

---

## Phase 5: Reorder Pipeline Steps — Scraping Before Processing

**Goal**: All scraping steps execute before all data processing/summary steps. Move `details_results` after `listing_summaries`.

**Success Criteria**:
- Pipeline order: search → details_scrape → airdna_data → reviews_scrape → listing_summaries → details_results → area_summary → correlation → description_analysis
- Step files renumbered: `05_listing_summaries` (was 06), `06_details_results` (was 05)
- `main.py` `PIPELINE_STEPS` updated
- Cache manager `STAGE_ORDER` updated
- All tests pass (including ordering assertions in integration tests)

**Status**: Not Started

---

## Phase 6: Final Zipcode Sweep & Documentation

**Goal**: Remove every remaining "zipcode" reference across the codebase. Update all documentation and planning files.

**Success Criteria**:
- `grep -ri "zipcode\|zip_code\|zip code" --include="*.py" --include="*.json"` returns zero hits in source files
- `pgeocode` removed from `Pipfile` if no longer needed
- All parameter names, variable names, comments, docstrings updated
- `README.md` updated with new config format and pipeline diagram
- Planning docs (`.planning/codebase/`) updated
- `dev/active/feature-engineering/feature-engineering-plan.md` prerequisites updated
- All tests pass

**Status**: Not Started

---

## Phase Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3 ──┐
                                    ├──► Phase 6
Phase 4 (independent) ────────────┤
Phase 5 (independent) ────────────┘
```

- Phases 1 → 2 → 3 are strictly sequential (each builds on prior config/naming changes)
- Phase 4 (lat/lng columns) and Phase 5 (reorder steps) are independent of each other and can run after Phase 3 or in parallel
- Phase 6 must be last (final sweep depends on all other phases being complete)
