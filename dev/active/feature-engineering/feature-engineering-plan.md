# Feature Engineering — Plan (Placeholder)

This is a placeholder for future geo-spatial feature engineering. Full design will happen after Stage 4 of the multi-zipcode upgrade is complete (lat/lng columns exist in the amenities matrix).

---

## Stage 1: Distance-to-POI Feature
**Goal**: Calculate haversine distance from each listing to the configured point of interest.
**Success Criteria**: `distance_to_poi_km` column in both raw and cleaned amenities matrix CSVs.
**Status**: Not Started

### Planned Scope
- New `utils/geo_utils.py` with `haversine(lat1, lon1, lat2, lon2) -> float` function
- `DetailsFilesetBuilder` reads `dest_lat`/`dest_long` from config, calculates distance per listing
- Unit tests for haversine accuracy and edge cases

---

## Stage 2: Distance Bucketing
**Goal**: Create categorical distance bins for analysis.
**Success Criteria**: `distance_bucket` column added to matrix.
**Status**: Not Started

### Planned Scope
- Configurable bin edges (e.g., `[0, 5, 15, 30, float('inf')]`)
- Labels (e.g., "nearby", "moderate", "distant", "far")
- Integration with correlation analyzer

---

## Stage 3: ML & Correlation Integration
**Goal**: Distance features feed into ML model and correlation analysis.
**Success Criteria**: `distance_to_poi_km` in `ml/train.py` `NUMERIC_FEATURES` and `correlation_analyzer.py` `NUMERIC_COLUMNS`.
**Status**: Not Started

---

## Prerequisites
- Multi-zipcode upgrade Stage 1 (config has `dest_lat`/`dest_long`) — **done**
- Multi-zipcode upgrade Stage 4 (lat/lng in matrix) — **not started**
