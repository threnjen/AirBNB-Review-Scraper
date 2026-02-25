# Consolidate Pipeline Outputs Under `outputs/`

## Overview

Move all intermediate pipeline directories (`property_*` dirs and root-level `area_data_*.json`) under a numbered `outputs/` tree. Final report files stay in `reports/` at the project root. Infrastructure (`cache/`, `logs/`) stays at root. All paths are hardcoded per-module — every reference must be updated individually, including file-existence idempotency checks.

### Design Principles

- `outputs/` holds **intermediate pipeline data** — numbered by config flag order
- `reports/` stays at root — it's the **final destination** for human-readable reports
- `cache/` and `logs/` stay at root — infrastructure, not pipeline data
- `CacheManager` keys are content-based hashes (no directory names) — **unaffected** by directory renames
- File-existence idempotency caching (listing skip logic) **must** reference new paths or all listings get reprocessed

### New Directory Structure

```
outputs/
├── 01_comp_sets/              # scrape_airdna
├── 02_search_results/         # scrape_reviews (searcher)
├── 03_reviews_scraped/        # scrape_reviews (reviews)
├── 04_details_scraped/        # scrape_details
├── 05_details_results/        # build_details
├── 06_generated_summaries/    # aggregate_reviews
├── 07_extracted_data/         # extract_data (was root-level file)
├── 08_correlation_results/    # analyze_correlations (.json stats)
└── 09_description_analysis/   # analyze_descriptions (.json stats)

reports/                       # STAYS AT ROOT — final .md + .json reports
cache/                         # STAYS AT ROOT — OpenAI response cache
logs/                          # STAYS AT ROOT — cost tracking
```

### Mapping: Config Flag → Old Directory → New Directory

| Config Flag | Old Output Path | New Output Path |
|---|---|---|
| `scrape_airdna` | `property_comp_sets/` | `outputs/01_comp_sets/` |
| `scrape_reviews` (searcher) | `property_search_results/` | `outputs/02_search_results/` |
| `scrape_reviews` (reviews) | `property_reviews_scraped/` | `outputs/03_reviews_scraped/` |
| `scrape_details` | `property_details_scraped/` | `outputs/04_details_scraped/` |
| `build_details` | `property_details_results/` | `outputs/05_details_results/` |
| `aggregate_reviews` | `property_generated_summaries/` | `outputs/06_generated_summaries/` |
| `aggregate_summaries` | `reports/` | `reports/` **(NO CHANGE)** |
| `extract_data` | `area_data_{zipcode}.json` (ROOT) | `outputs/07_extracted_data/` |
| `analyze_correlations` | `property_correlation_results/` + `reports/` | `outputs/08_correlation_results/` + `reports/` |
| `analyze_descriptions` | `property_correlation_results/` + `reports/` | `outputs/09_description_analysis/` + `reports/` |

---

## Stage 1: Add Missing `os.makedirs` Calls

**Goal**: Ensure all writers create their output directories before writing.
**Success Criteria**: All modules create output directory if missing; compile successfully.
**Status**: Not Started

Five modules write to directories without ensuring they exist. Add `os.makedirs(dir_path, exist_ok=True)` before each file write.

### 1a. `scraper/airbnb_searcher.py`

**Location**: Before line 64 (the `open()` call)
**Current code** (lines 63-67):
```python
    with open(
        f"property_search_results/search_results_{zipcode}.json", "w", encoding="utf-8"
    ) as f:
```
**Change**: Add `os.makedirs("outputs/02_search_results", exist_ok=True)` before the `open()`. (Combine with Stage 2 path rename.)

### 1b. `scraper/reviews_scraper.py`

**Location**: Before line 55 (the `open()` call)
**Current code** (lines 54-59):
```python
            with open(
                f"property_reviews_scraped/reviews_{zipcode}_{id}.json",
                "w",
                encoding="utf-8",
            ) as f:
```
**Change**: Add `os.makedirs("outputs/03_reviews_scraped", exist_ok=True)` before the `open()`.

### 1c. `scraper/details_scraper.py`

**Location**: Before line 37 (the `open()` call)
**Current code** (lines 36-41):
```python
            with open(
                f"property_details_scraped/property_details_{room_id}.json",
                "w",
                encoding="utf-8",
            ) as f:
```
**Change**: Add `os.makedirs("outputs/04_details_scraped", exist_ok=True)` before the `open()`.

### 1d. `scraper/details_fileset_build.py`

**Location**: Before line 175 (first write to results dir)
**Current code** (line 175):
```python
        amenities_df.to_csv("property_details_results/property_amenities_matrix.csv")
```
**Change**: Add `os.makedirs("outputs/05_details_results", exist_ok=True)` before the CSV write.

### 1e. `review_aggregator/property_review_aggregator.py`

**Location**: Before line 285 (the `save_json_file()` call)
**Current code** (lines 284-287):
```python
            save_json_file(
                filename=f"property_generated_summaries/generated_summaries_{self.zipcode}_{listing_id}.json",
                data={listing_id: generated_summaries[listing_id]},
            )
```
**Change**: Add `os.makedirs("outputs/06_generated_summaries", exist_ok=True)` before the first write in the method (before the first-pass loop).

---

## Stage 2: Update Scraper Module Paths

**Goal**: Point all scraper output/input paths to `outputs/` subdirectories.
**Success Criteria**: Scraper modules compile; paths resolve to `outputs/` tree.
**Status**: Not Started

### 2a. `scraper/airdna_scraper.py` — Line 471

**Old**: `output_dir: str = "property_comp_sets"`
**New**: `output_dir: str = "outputs/01_comp_sets"`

(This module already has `os.makedirs(output_dir, exist_ok=True)` on line 480.)

### 2b. `scraper/airbnb_searcher.py` — Line 64

**Old**: `f"property_search_results/search_results_{zipcode}.json"`
**New**: `f"outputs/02_search_results/search_results_{zipcode}.json"`

### 2c. `main.py` — Lines 103 and 106

Two references to search results path in `get_area_search_results()`:

**Old** (line 103):
```python
        elif os.path.isfile(
            f"property_search_results/search_results_{self.zipcode}.json"
        ):
```
**New**:
```python
        elif os.path.isfile(
            f"outputs/02_search_results/search_results_{self.zipcode}.json"
        ):
```

**Old** (line 106):
```python
            with open(
                f"property_search_results/search_results_{self.zipcode}.json",
```
**New**:
```python
            with open(
                f"outputs/02_search_results/search_results_{self.zipcode}.json",
```

### 2d. `scraper/reviews_scraper.py` — Line 55

**Old**: `f"property_reviews_scraped/reviews_{zipcode}_{id}.json"`
**New**: `f"outputs/03_reviews_scraped/reviews_{zipcode}_{id}.json"`

### 2e. `scraper/details_scraper.py` — Line 37

**Old**: `f"property_details_scraped/property_details_{room_id}.json"`
**New**: `f"outputs/04_details_scraped/property_details_{room_id}.json"`

### 2f. `scraper/details_fileset_build.py` — Lines 152, 175, 177, 181, 186, 191

**Line 152** (read path):
- **Old**: `os.path.join("property_details_scraped", file_name)`
- **New**: `os.path.join("outputs/04_details_scraped", file_name)`

**Line 175** (write CSV):
- **Old**: `"property_details_results/property_amenities_matrix.csv"`
- **New**: `"outputs/05_details_results/property_amenities_matrix.csv"`

**Line 177** (log message):
- **Old**: `"Details fileset built and saved to property_details_results/property_amenities_matrix.csv"`
- **New**: `"Details fileset built and saved to outputs/05_details_results/property_amenities_matrix.csv"`

**Line 181** (write JSON):
- **Old**: `"property_details_results/house_rules_details.json"`
- **New**: `"outputs/05_details_results/house_rules_details.json"`

**Line 186** (write JSON):
- **Old**: `"property_details_results/property_descriptions.json"`
- **New**: `"outputs/05_details_results/property_descriptions.json"`

**Line 191** (write JSON):
- **Old**: `"property_details_results/neighborhood_highlights.json"`
- **New**: `"outputs/05_details_results/neighborhood_highlights.json"`

---

## Stage 3: Update Review Aggregator Module Paths (Including Idempotency Caching)

**Goal**: Point all aggregator intermediate output paths to `outputs/`. Preserve file-existence idempotency logic.
**Success Criteria**: All aggregator modules compile; idempotency logic references new paths correctly; `reports/` references unchanged.
**Status**: Not Started

### 3a. `review_aggregator/property_review_aggregator.py` — 7 path references

This module has **two caching mechanisms**:
1. **OpenAI response cache** (`CacheManager`) — unaffected (content-based keys)
2. **File-existence idempotency** — lists `property_generated_summaries/` to find already-processed listings; skips them via `filter_out_processed_reviews()`. **ALL directory references must be updated or all listings get reprocessed.**

**Line 214** (delete path in `remove_empty_reviews()`):
- **Old**: `f"property_generated_summaries/generated_summaries_{self.zipcode}_{empty_id}.json"`
- **New**: `f"outputs/06_generated_summaries/generated_summaries_{self.zipcode}_{empty_id}.json"`

**Line 227** (listdir — input reviews):
- **Old**: `os.listdir("property_reviews_scraped/")`
- **New**: `os.listdir("outputs/03_reviews_scraped/")`

**Line 232** (read path — load reviews):
- **Old**: `load_json_file(filename=f"property_reviews_scraped/{file}")`
- **New**: `load_json_file(filename=f"outputs/03_reviews_scraped/{file}")`

**Line 238** (listdir — **IDEMPOTENCY CACHE** — finds already-processed listings):
- **Old**: `os.listdir("property_generated_summaries/")`
- **New**: `os.listdir("outputs/06_generated_summaries/")`

**Line 246** (read path — load existing summaries):
- **Old**: `load_json_file(filename=f"property_generated_summaries/{file}")`
- **New**: `load_json_file(filename=f"outputs/06_generated_summaries/{file}")`

**Line 285** (write path — first pass save):
- **Old**: `f"property_generated_summaries/generated_summaries_{self.zipcode}_{listing_id}.json"`
- **New**: `f"outputs/06_generated_summaries/generated_summaries_{self.zipcode}_{listing_id}.json"`

**Line 308** (write path — third pass save):
- **Old**: `f"property_generated_summaries/generated_summaries_{self.zipcode}_{listing_id}.json"`
- **New**: `f"outputs/06_generated_summaries/generated_summaries_{self.zipcode}_{listing_id}.json"`

### 3b. `review_aggregator/area_review_aggregator.py` — 2 path references + NO changes to output_dir

**`output_dir` field stays `"reports"`** — this module writes final reports, not intermediate data.

**Line 67** (listdir — reads cached summaries):
- **Old**: `os.listdir("property_generated_summaries/")`
- **New**: `os.listdir("outputs/06_generated_summaries/")`

**Line 84** (read path):
- **Old**: `f"property_generated_summaries/{file}"`
- **New**: `f"outputs/06_generated_summaries/{file}"`

### 3c. `review_aggregator/data_extractor.py` — 2 changes

**Line 51** (default `summary_dir` field):
- **Old**: `summary_dir: str = "property_generated_summaries"`
- **New**: `summary_dir: str = "outputs/06_generated_summaries"`

Note: The `load_property_summaries()` method uses `self.summary_dir` for listing files and `f"{self.summary_dir}/{filename}"` for reading — no additional hardcoded path changes needed there. The filename filter `startswith(f"generated_summaries_{self.zipcode}_")` stays unchanged (filename prefix not affected).

**Line 236** (output_path — currently writes to root):
- **Old**: `output_path = f"area_data_{self.zipcode}.json"`
- **New**: Add `os.makedirs("outputs/07_extracted_data", exist_ok=True)` before, then `output_path = f"outputs/07_extracted_data/area_data_{self.zipcode}.json"`

Also update the log message on the next line accordingly.

### 3d. `review_aggregator/correlation_analyzer.py` — 3 changes

**Line 77** (default `output_dir`):
- **Old**: `output_dir: str = "property_correlation_results"`
- **New**: `output_dir: str = "outputs/08_correlation_results"`

**Line 78** (`reports_dir`): **NO CHANGE** — stays `"reports"`

**Line 83** (read CSV path):
- **Old**: `csv_path = "property_details_results/property_amenities_matrix.csv"`
- **New**: `csv_path = "outputs/05_details_results/property_amenities_matrix.csv"`

**Line 96** (read descriptions path):
- **Old**: `desc_path = "property_details_results/property_descriptions.json"`
- **New**: `desc_path = "outputs/05_details_results/property_descriptions.json"`

### 3e. `review_aggregator/description_analyzer.py` — 3 changes

**Line 48** (default `output_dir`):
- **Old**: `output_dir: str = "property_correlation_results"`
- **New**: `output_dir: str = "outputs/09_description_analysis"`

**Line 49** (`reports_dir`): **NO CHANGE** — stays `"reports"`

**Line 54** (read CSV path):
- **Old**: `csv_path = "property_details_results/property_amenities_matrix.csv"`
- **New**: `csv_path = "outputs/05_details_results/property_amenities_matrix.csv"`

**Line 66** (read descriptions path):
- **Old**: `desc_path = "property_details_results/property_descriptions.json"`
- **New**: `desc_path = "outputs/05_details_results/property_descriptions.json"`

---

## Stage 4: Verify Infrastructure Caches — NO Code Changes

**Goal**: Confirm `CacheManager`, `CostTracker`, and `OpenAIAggregator` caching are unaffected.
**Success Criteria**: All paths verified unchanged; documented in this plan.
**Status**: Not Started

### Verified: No changes needed

- **`utils/cache_manager.py` L24**: `cache_dir: str = "cache/summaries"` — stays at root
- **Cache key generation** (L47-56): Keys are `{listing_id}_{md5(prompt)[:12]}_{md5(reviews)[:12]}` — purely content-based, no directory names
- **`utils/cost_tracker.py` L52**: `logs/cost_tracking.json` — stays at root
- **`review_aggregator/openai_aggregator.py` L209-223**: Cache lookup/write in `generate_summary()` — uses `CacheManager` internally, no directory names

---

## Stage 5: Update Tests

**Goal**: All test fixtures and mocks reference new directory names.
**Success Criteria**: `pipenv run pytest` passes.
**Status**: Not Started

### 5a. `tests/conftest.py`

**Line 212** (`mock_summary_files_dir` fixture):
- **Old**: `summary_dir = tmp_path / "property_generated_summaries"`
- **New**: `summary_dir = tmp_path / "outputs" / "06_generated_summaries"`

**Line 242** (`mock_review_files_dir` fixture):
- **Old**: `review_dir = tmp_path / "property_reviews_scraped"`
- **New**: `review_dir = tmp_path / "outputs" / "03_reviews_scraped"`

**Lines 54-58** (`tmp_cache_dir`): **NO CHANGE** — `cache/summaries` stays at root

### 5b. `tests/unit/test_area_review_aggregator.py`

This file mocks `os.listdir` in many places. The listdir calls themselves don't pass path arguments in the test (they're patched globally), so **no changes to mock return values are needed** — the filenames like `generated_summaries_97067_*.json` are unchanged.

However, verify that any test that constructs temp directories with old names is updated.

**Line 316** (TestSaveResults): `nested_dir = tmp_path / "nested" / "reports"` — **NO CHANGE** (tests `output_dir` override, `reports` is still the real target)

### 5c. `tests/integration/test_pipeline_integration.py`

Tests mock `os.listdir` with old filenames — filenames stay the same so return values are fine. Check for any test that constructs temp directories with old names.

The `mock_summary_files_dir` fixture from conftest is used here — covered by 5a.

### 5d. `tests/unit/test_data_extractor.py`

Tests mock `os.path.exists` and `os.listdir` on the `data_extractor` module. Since `DataExtractor.summary_dir` default changes from `"property_generated_summaries"` to `"outputs/06_generated_summaries"`, any test that creates an extractor and checks the default value should be reviewed.

The extractor fixture in tests should work since it overrides `summary_dir` via the `mock_summary_files_dir` fixture (which is updated in 5a).

### 5e. `tests/unit/test_description_analyzer.py`

**Lines 449-451**: Test overrides `analyzer.output_dir` and `analyzer.reports_dir` to `str(tmp_path)` — **NO CHANGE** (test uses tmp_path, not defaults)

### 5f. No changes needed:
- `tests/unit/test_cache_manager.py` — uses `tmp_path` fixtures, no hardcoded output dirs
- `tests/unit/test_openai_aggregator.py` — uses mocks, no hardcoded output dirs

---

## Stage 6: Update `.gitignore` and Migrate Data

**Goal**: Clean up root, preserve existing data, update ignore rules.
**Success Criteria**: No `property_*` dirs at root; `outputs/` contains all pipeline data; `reports/` unchanged; `.gitignore` covers `outputs/`.
**Status**: Not Started

### 6a. Update `.gitignore`

**Line 214**: Replace `property_*` with `outputs/`

The existing rule `*.json` (line 213) and `*.csv` (line 214) already cover data files. Adding `outputs/` ensures the entire directory tree is ignored.

Also verify: `reports/` is NOT in `.gitignore` (it currently isn't) — final reports should be committable.

### 6b. Migrate existing data

Run these commands to move existing output data into the new structure:

```bash
mkdir -p outputs/{01_comp_sets,02_search_results,03_reviews_scraped,04_details_scraped,05_details_results,06_generated_summaries,07_extracted_data,08_correlation_results,09_description_analysis}

# Move files (use -f to handle empty dirs gracefully)
[ -d property_comp_sets ] && mv property_comp_sets/* outputs/01_comp_sets/ 2>/dev/null
[ -d property_search_results ] && mv property_search_results/* outputs/02_search_results/ 2>/dev/null
[ -d property_reviews_scraped ] && mv property_reviews_scraped/* outputs/03_reviews_scraped/ 2>/dev/null
[ -d property_details_scraped ] && mv property_details_scraped/* outputs/04_details_scraped/ 2>/dev/null
[ -d property_details_results ] && mv property_details_results/* outputs/05_details_results/ 2>/dev/null
[ -d property_generated_summaries ] && mv property_generated_summaries/* outputs/06_generated_summaries/ 2>/dev/null
[ -f area_data_*.json ] && mv area_data_*.json outputs/07_extracted_data/ 2>/dev/null
[ -d property_correlation_results ] && mv property_correlation_results/correlation_* outputs/08_correlation_results/ 2>/dev/null
[ -d property_correlation_results ] && mv property_correlation_results/description_* outputs/09_description_analysis/ 2>/dev/null
```

**CRITICAL**: Moving `property_generated_summaries/*` → `outputs/06_generated_summaries/` preserves the file-existence idempotency cache. Without this, `aggregate_reviews` would reprocess all listings (expensive OpenAI API calls).

### 6c. Clean up root artifacts

```bash
# Remove legacy root-level artifact (not written by current code)
rm -f generated_summaries_97067.json

# Remove empty old directories
rmdir property_comp_sets property_search_results property_reviews_scraped property_details_scraped property_details_results property_generated_summaries property_correlation_results 2>/dev/null
```

---

## Verification

1. `pipenv run python -m py_compile main.py` — all imports resolve
2. Compile-check each changed module: `pipenv run python -m py_compile scraper/airdna_scraper.py scraper/airbnb_searcher.py scraper/reviews_scraper.py scraper/details_scraper.py scraper/details_fileset_build.py review_aggregator/property_review_aggregator.py review_aggregator/area_review_aggregator.py review_aggregator/data_extractor.py review_aggregator/correlation_analyzer.py review_aggregator/description_analyzer.py`
3. `pipenv run pytest` — full test suite passes
4. Verify `.gitignore` covers `outputs/`
5. Verify `reports/` is NOT gitignored (final reports should be committable)
6. Manually confirm existing migrated data in correct directories
