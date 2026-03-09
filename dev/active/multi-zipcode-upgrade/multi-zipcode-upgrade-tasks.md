# Multi-Zipcode Pipeline Upgrade — Tasks

## Stage 1: Config Schema Update
- [x] Add `dest_lat` and `dest_long` to `config.json` *(user has already done this)*
- [x] Replace `main.py` `AirBnbReviewAggregator.zipcode` property with `zipcodes` returning the list
- [x] Verify: `load_config()` returns `zipcodes` as list, `dest_lat`/`dest_long` as floats
- [x] Verify: `pipenv run pytest tests/ -x` — 345 tests pass

## Stage 2: Multi-Zipcode Pipeline Orchestration
- [ ] Split `PIPELINE_STEPS` into `SCRAPING_STEPS` and `PROCESSING_STEPS` in `main.py`
- [ ] Refactor `run_tasks_from_config()` — two outer loops (scraping all zips, processing all zips) with `config["zipcode"]` injection
- [ ] Update `STAGE_ORDER` in `pipeline_cache_manager.py` — move `listing_summaries` before `details_results`
- [ ] Add `details_results` to `CASCADE_TARGET_STAGES` in `pipeline_cache_manager.py`
- [ ] Write integration test: `TestMultiZipcodeOrchestration.test_scraping_completes_before_processing`
- [ ] Run test RED first, then implement, then GREEN
- [ ] Verify: `pipenv run pytest tests/ -x` — all tests pass

## Stage 3: Renumber Pipeline Step Files
- [ ] `mv steps/06_listing_summaries.py steps/05_listing_summaries.py`
- [ ] `mv steps/05_details_results.py steps/06_details_results.py`
- [ ] Update module paths in `SCRAPING_STEPS`/`PROCESSING_STEPS` in `main.py`
- [ ] Grep tests for `steps.05_` and `steps.06_` imports — update if any
- [ ] Verify: `pipenv run python -m py_compile steps/05_listing_summaries.py`
- [ ] Verify: `pipenv run python -m py_compile steps/06_details_results.py`
- [ ] Verify: `pipenv run pytest tests/ -x` — all tests pass

## Stage 4: Add Latitude/Longitude to Amenities Matrix
- [ ] Write unit test: mock details JSON with `coordinates`, assert `latitude`/`longitude` columns in output DataFrame
- [ ] Run test RED
- [ ] In `DetailsFilesetBuilder.parse_basic_details()`, extract `coordinates.latitude` and `coordinates.longitude`
- [ ] Verify `latitude`/`longitude` not in `clean_amenities_df()` `drop_cols`
- [ ] Run test GREEN
- [ ] Verify: `pipenv run pytest tests/ -x` — all tests pass

## Stage 5: Feature Engineering (Placeholder)
- [ ] Planning document exists at `dev/active/feature-engineering/feature-engineering-plan.md`
- [ ] No code changes — this is a deferred stage

## Commit Points
- **After Stage 1**: `feat(config): support multi-zipcode list and destination POI coordinates`
- **After Stages 2–3**: `feat(pipeline): multi-zipcode two-phase orchestration with step renumbering`
- **After Stage 4**: `feat(matrix): add listing latitude/longitude to amenities matrix`
