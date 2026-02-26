# Context: Zipcode-Scoped Cache

## Key Files
- `utils/pipeline_cache_manager.py` — `PipelineCacheManager`: `clear_stage`, `is_stage_fresh`, `record_stage_complete`, `cascade_force_refresh`
- `utils/local_file_handler.py` — `LocalFileHandler.clear_directory`
- `main.py` — `AirBnbReviewAggregator.run_tasks_from_config` (10 stage blocks), `get_area_search_results`
- `review_aggregator/property_review_aggregator.py` — already has per-listing resume via `filter_out_processed_reviews`
- `review_aggregator/area_review_aggregator.py` — already filters by `generated_summaries_{self.zipcode}_*`
- `tests/unit/test_pipeline_cache_manager.py` — 30+ existing unit tests
- `tests/integration/test_pipeline_integration.py` — integration tests

## Decisions
- Completion key convention: `_completed:{zipcode}` (no schema migration)
- `details`/`build_details`: derive listing IDs from `search_results_{zipcode}.json` to scope clears
- `clear_stage()` retained as deprecated full-wipe fallback; `main.py` uses `clear_stage_for_zipcode()`
- `cascade_force_refresh` and `_apply_init_cascade` unchanged (they only set flags)
- Three-way return: `"skip"` / `"resume"` / `"clear_and_run"` (string literals)
- `cascade_force_refresh` only called on `"clear_and_run"` path
- `record_stage_complete` and `is_stage_fresh` gain required `zipcode` parameter
