## Stage 1: Task Documentation Setup

**Goal**: Create the three-file task directory so a fresh context can pick up and review work at any point.
**Success Criteria**: Files exist under `dev/active/pipeline-cache/` with plan, context, and tasks.
**Status**: Complete

---

## Stage 2: Config Changes

**Goal**: Add all new config keys to `config.json` and wire them into `main.py` `load_configs()`.
**Success Criteria**: Config loads without errors; new keys are present with defaults.
**Status**: Complete

**Changes**:
- `config.json`: Add `pipeline_cache_enabled` (bool), `pipeline_cache_ttl_days` (int), and seven `force_refresh_*` booleans
- `main.py`: Update `load_configs()` to read new keys into instance attributes

---

## Stage 3: Tests (Red)

**Goal**: Write unit tests for `PipelineCacheManager` before implementation.
**Success Criteria**: Tests exist in `tests/unit/test_pipeline_cache_manager.py` and fail because the module doesn't exist yet.
**Status**: Complete

**Changes**:
- Create `tests/unit/test_pipeline_cache_manager.py` with `TestPipelineCacheManager` class
- Add fixtures to `tests/conftest.py`: `tmp_pipeline_cache_dir`, `pipeline_cache_manager`
- Update `isolate_tests` fixture to include new config keys

---

## Stage 4: Core Implementation

**Goal**: Create `PipelineCacheManager` class in `utils/pipeline_cache_manager.py`.
**Success Criteria**: Module compiles; all unit tests from Stage 3 pass.
**Status**: Complete

**Changes**:
- Create `utils/pipeline_cache_manager.py` — Pydantic `BaseModel` class with:
  - `_load_metadata()`, `_save_metadata()`
  - `is_file_fresh()`, `is_stage_fresh()`
  - `record_output()`, `record_stage_complete()`
  - `clear_stage()`, `get_cache_stats()`

---

## Stage 5: Pipeline Integration

**Goal**: Wire `PipelineCacheManager` into the pipeline orchestrator and all stage modules (stages 0–6).
**Success Criteria**: Running pipeline twice skips all stages on second run; logs confirm cache hits.
**Status**: Complete

**Changes**:
- `main.py`: Instantiate `PipelineCacheManager`, wrap stages 0–6 in cache checks, record outputs
- `scraper/reviews_scraper.py`: Add `pipeline_cache=None` param, per-file freshness check
- `scraper/details_scraper.py`: Same pattern as reviews
- `review_aggregator/property_review_aggregator.py`: Use `is_file_fresh()` on summaries so stale ones regenerate
- `review_aggregator/area_review_aggregator.py`: Record outputs after completion

---

## Stage 6: Integration Tests & Verification

**Goal**: Verify end-to-end cache behavior and test suite health.
**Success Criteria**: All tests pass; coverage ≥75%.
**Status**: Complete

**Changes**:
- Add integration test verifying cache skip on second run and force-refresh behavior
- Run full test suite and coverage check

---

## Stage 7: Documentation

**Goal**: Document the caching system for users and future agents.
**Success Criteria**: README updated; task plan files reflect completion.
**Status**: Complete

**Changes**:
- Add "Pipeline Caching" section to `README.md`
- Update plan and tasks files to reflect completion
