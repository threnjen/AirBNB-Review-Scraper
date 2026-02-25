- [x] **Stage 1: Task Documentation Setup**
  - [x] Create `dev/active/pipeline-cache/pipeline-cache-plan.md`
  - [x] Create `dev/active/pipeline-cache/pipeline-cache-context.md`
  - [x] Create `dev/active/pipeline-cache/pipeline-cache-tasks.md`

- [x] **Stage 2: Config Changes**
  - [x] Add `pipeline_cache_enabled`, `pipeline_cache_ttl_days`, and 7 `force_refresh_*` keys to `config.json`
  - [x] Update `load_configs()` in `main.py` to read new keys
  - [x] Verify: `pipenv run python -m py_compile main.py`

- [x] **Stage 3: Tests (Red)**
  - [x] Create `tests/unit/test_pipeline_cache_manager.py` with `TestPipelineCacheManager`
  - [x] Update `isolate_tests` fixture with new config keys
  - [x] Confirm tests fail (module not yet implemented)

- [x] **Stage 4: Core Implementation**
  - [x] Create `utils/pipeline_cache_manager.py` with `PipelineCacheManager` class
  - [x] Implement `_load_metadata()` and `_save_metadata()` (atomic write)
  - [x] Implement `is_file_fresh(stage_name, file_path)` — TTL + file existence check
  - [x] Implement `is_stage_fresh(stage_name)` — checks all outputs + force_refresh
  - [x] Implement `record_output(stage_name, file_path)` — writes timestamp
  - [x] Implement `record_stage_complete(stage_name)` — marks completion
  - [x] Implement `clear_stage(stage_name)` — removes stage metadata
  - [x] Implement `get_cache_stats()` — summary counts
  - [x] Verify: `pipenv run python -m py_compile utils/pipeline_cache_manager.py`
  - [x] Verify: `pipenv run pytest tests/unit/test_pipeline_cache_manager.py -v` — all 17 pass

- [x] **Stage 5: Pipeline Integration**
  - [x] Instantiate `PipelineCacheManager` in `main.py` `__init__`
  - [x] Wrap AirDNA stage (stage 0) with cache check in `run_tasks_from_config()`
  - [x] Wrap reviews stage (stage 2) with cache check + per-file skip in `scrape_reviews()`
  - [x] Wrap details stage (stage 3) with cache check + per-file skip in `scrape_details()`
  - [x] Wrap build_details stage (stage 4) with cache check
  - [x] Add `pipeline_cache` to `PropertyRagAggregator`, TTL-aware `filter_out_processed_reviews()`
  - [x] Wrap aggregate_summaries stage (stage 6) with cache check, record outputs in `AreaRagAggregator`
  - [x] Verify: `pipenv run python -m py_compile main.py`
  - [x] Verify: `pipenv run pytest` — 251 passed (no new regressions)

- [x] **Stage 6: Integration Tests & Verification**
  - [x] Add `TestPipelineCacheIntegration` to `tests/integration/test_pipeline_integration.py` (4 tests)
  - [x] Run `pipenv run pytest` — 251 passed, coverage 82.77% (≥75%)
  - [x] `pipeline_cache_manager.py` coverage: 89%

- [x] **Stage 7: Documentation**
  - [x] Add "Pipeline Caching (TTL)" section to `README.md`
  - [x] Update `pipeline-cache-plan.md` — all stages Complete
  - [x] Update `pipeline-cache-tasks.md` — all boxes checked
