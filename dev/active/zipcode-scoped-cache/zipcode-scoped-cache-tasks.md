# Tasks: Zipcode-Scoped Cache

## Stage 1: Cache Manager Core
- [ ] Add `clear_files_matching` to `LocalFileHandler`
- [ ] Add `_get_listing_ids_for_zipcode` to `PipelineCacheManager`
- [ ] Add `clear_stage_for_zipcode` to `PipelineCacheManager`
- [ ] Update `record_stage_complete` to accept `zipcode`
- [ ] Update `is_stage_fresh` to accept `zipcode`
- [ ] Add `should_run_stage` method

## Stage 2: Wire Up main.py
- [ ] Replace all `clear_stage()` calls with `clear_stage_for_zipcode()`
- [ ] Replace all `is_stage_fresh()` calls with zipcode param
- [ ] Replace all `record_stage_complete()` calls with zipcode param
- [ ] Replace binary if/else with three-way `should_run_stage` pattern

## Stage 3: Tests
- [ ] Write tests for `clear_files_matching`
- [ ] Write tests for `clear_stage_for_zipcode`
- [ ] Write tests for scoped `is_stage_fresh` / `record_stage_complete`
- [ ] Write tests for `should_run_stage` (skip, resume, clear_and_run)
- [ ] Write tests for `_get_listing_ids_for_zipcode`
- [ ] Update existing unit tests for new signatures
- [ ] Update integration tests for new signatures
- [ ] Run full suite: `pipenv run pytest tests/ -x -q`
