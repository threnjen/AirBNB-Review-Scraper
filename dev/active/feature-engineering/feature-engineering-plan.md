# Feature Engineering — Plan

## Stage 1: DIST_TO_POI Feature
**Goal**: Calculate Manhattan surface distance (miles) from each listing to the configured POI.
**Success Criteria**: `DIST_TO_POI` column in both raw and cleaned amenities matrix CSVs; `latitude`/`longitude` columns preserved.
**Status**: Complete

### Implemented Scope
- New `utils/geo_utils.py` with `manhattan_surface_distance(lat1, lon1, lat2, lon2) -> float` (miles)
- `DetailsFilesetBuilder` accepts `poi_lat`/`poi_long`, extracts coordinates from property JSON, computes `DIST_TO_POI`
- `clean_amenities_df()` preserves `latitude`, `longitude`, `DIST_TO_POI` and coerces `DIST_TO_POI` to float
- `steps/06_details_results.py` passes `poi_lat`/`poi_long` from config
- Unit tests in `tests/unit/test_geo_utils.py` and `tests/unit/test_details_fileset_build.py`

---

## Stage 2: ML & Correlation Integration
**Goal**: Distance features feed into ML model and correlation analysis.
**Success Criteria**: `DIST_TO_POI` in `ml/train.py` `NUMERIC_FEATURES` and `correlation_analyzer.py` `NUMERIC_COLUMNS`.
**Status**: Complete
