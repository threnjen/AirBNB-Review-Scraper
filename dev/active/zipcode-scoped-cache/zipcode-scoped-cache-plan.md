# Filesystem-Driven Cache — mtime-based, no metadata flags

## Problem

The previous cache implementation (`_completed:{zipcode}` flags in `pipeline_metadata.json`) has three bugs:

1. **Legacy metadata mismatch**: Existing metadata only has `_completed` keys (no zipcode suffix). The code now looks for `_completed:97067`, which doesn't exist — so every stage returns `"resume"` and re-runs despite having valid cached files on disk.

2. **Zipcode-in-filename assumption fails for 3 stages**: `is_stage_fresh` filters output files by `zipcode in filepath`. This fails for `airdna` (filenames use listing IDs, not zipcodes), `details` (same), and `build_details` (filenames have no zipcode at all). These stages can never be "fresh".

3. **No expected-output enumeration**: The system checks files *recorded in metadata*, not files *expected by the pipeline*. If metadata is missing/corrupt/incomplete, stages re-run even when all output files exist on disk.

## Solution

Replace metadata-driven freshness with filesystem-driven freshness using `os.path.getmtime` for TTL checks. Each stage declares its expected output files; freshness = all expected files exist on disk with mtime within TTL. Drop `pipeline_metadata.json` entirely. Rename `build_details` outputs to include zipcode.

## Stage 1: PipelineCacheManager Rewrite
**Goal**: `expected_outputs`, mtime-based `is_stage_fresh`, `get_missing_outputs`, rewritten `should_run_stage` and `clear_stage_for_zipcode`
**Success Criteria**: Unit tests pass for all new methods; no references to `_load_metadata`, `_save_metadata`, `record_output`, `record_stage_complete`, or `_completed` keys
**Status**: Not Started

- Add `expected_outputs(stage_name, zipcode)` — returns list of expected file paths
  - Fixed-count stages: paths derived from zipcode alone
  - Listing-dynamic stages (`airdna`, `reviews`, `details`, `aggregate_reviews`): derive listing IDs from search results file
  - Metric-dynamic stage (`analyze_correlations`): uses `correlation_metrics` from config
  - `build_details`: 5 files with zipcode in names (new convention)
- Add `_is_file_fresh_by_mtime(file_path)` — checks `os.path.getmtime` against TTL
- Rewrite `is_file_fresh(stage_name, file_path)` — uses mtime, no metadata
- Rewrite `is_stage_fresh(stage_name, zipcode)` — calls `expected_outputs`, checks all files exist + mtime fresh; no `_completed` flag
- Add `get_missing_outputs(stage_name, zipcode)` — returns subset of expected files that are missing or stale
- Rewrite `should_run_stage(stage_name, zipcode)` — `force_refresh` → `"clear_and_run"`, all fresh → `"skip"`, else → `"resume"`
- Rewrite `clear_stage_for_zipcode(stage_name, zipcode)` — calls `expected_outputs`, deletes only those files; never wipes full directory
- Remove: `_load_metadata`, `_save_metadata`, `_is_timestamp_fresh`, `record_output`, `record_stage_complete`, `metadata_path` field
- Retain `clear_stage` as deprecated full-wipe fallback
- Retain `cascade_force_refresh`, `_apply_init_cascade` unchanged
- Store `correlation_metrics` from config for `expected_outputs` to use

## Stage 2: Rename build_details Outputs
**Goal**: All `build_details` output files include zipcode in filenames
**Success Criteria**: `DetailsFilesetBuilder.build_fileset()` writes `*_{zipcode}.*` files; downstream consumers (`CorrelationAnalyzer`, `DescriptionAnalyzer`) accept zipcode-parameterized paths
**Status**: Not Started

- `DetailsFilesetBuilder`: accept `zipcode` param, write to `property_amenities_matrix_{zipcode}.csv`, etc.
- `CorrelationAnalyzer.load_property_data`: accept zipcode-parameterized path
- `DescriptionAnalyzer.load_property_data`: accept zipcode-parameterized path
- Update `main.py` `build_details` block to pass zipcode and reference new filenames

## Stage 3: Wire Up main.py
**Goal**: All 10 stage blocks use new pattern; no `record_output` / `record_stage_complete` calls
**Success Criteria**: Pipeline skips stages when all expected files exist; resumes from partial progress; `force_refresh` clears only expected outputs for the one zipcode
**Status**: Not Started

- Remove all `record_output` and `record_stage_complete` calls
- `"clear_and_run"` path: call `clear_stage_for_zipcode` (deletes only expected outputs for the active zipcode), then `cascade_force_refresh`, then run
- `"resume"` path: run stage (scrapers already do per-file `is_file_fresh` internally)
- `"skip"` path: log and continue

## Stage 4: Update Tests
**Goal**: All tests reflect mtime-based freshness, no metadata assertions
**Success Criteria**: `pipenv run pytest tests/ -x -q` passes, coverage ≥ 84%
**Status**: Not Started

- Delete tests that assert on `_completed` keys, `record_output`, `record_stage_complete`, `_load_metadata`, `_save_metadata`
- Add tests for `expected_outputs` (fixed-count stages, listing-dynamic stages, missing search results)
- Add tests for `_is_file_fresh_by_mtime` (fresh, stale, missing)
- Add tests for mtime-based `is_stage_fresh` (all present+fresh, some missing, some stale, empty)
- Add tests for `get_missing_outputs`
- Add tests for rewritten `clear_stage_for_zipcode` (deletes only expected files for one zipcode)
- Update integration tests to remove metadata-based assertions
- Update `test_get_area_search_results.py` to remove `record_output`/`record_stage_complete` expectations

## Stage 5: Cleanup
**Goal**: Remove stale artifacts
**Success Criteria**: No stale task docs, no stale metadata file
**Status**: Not Started

- Delete `dev/active/airdna-per-listing-refactor/` (all stages complete)
- Delete `cache/pipeline_metadata.json` (no longer used)
- Remove `cache/` directory creation from `__init__` if no longer needed
