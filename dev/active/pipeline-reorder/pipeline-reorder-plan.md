## Stage 1: Rename Config Flags & Update Cache Manager
**Goal**: Align all config toggle names, force-refresh flag names, output directory names, and pipeline cache stage names to the new 9-step convention. Add `search_results` toggle.
**Success Criteria**:
- `config.json` has 9 toggle flags + 9 force-refresh flags, named to match output directories, in pipeline order
- `PipelineCacheManager.STAGE_ORDER` lists 9 stages in new order
- `STAGE_OUTPUT_DIRS` maps each stage to its correctly numbered directory
- `expected_outputs` returns correct file paths for all 9 stages
- `area_summary` stage combines outputs from `AreaRagAggregator` and `DataExtractor`
- All cache-related tests updated and passing
**Status**: Complete

## Stage 2: Update Hardcoded Paths in Scraper & Aggregator Modules
**Goal**: Update all hardcoded output directory references in `scraper/` and `review_aggregator/` modules to use the new directory names.
**Success Criteria**:
- No references to old directory names remain in any module
- All modules compile cleanly
- All unit tests for these modules updated and passing
**Status**: Complete

## Stage 3: Create `steps/` Runner Files & Refactor `main.py`
**Goal**: Create 9 step-runner files in `steps/`, each containing the orchestration logic for one pipeline stage. Refactor `main.py` to loop through steps sequentially.
**Success Criteria**:
- `steps/01_search_results.py` through `steps/09_description_analysis.py` each expose a `run()` function
- `main.py` `run_tasks_from_config()` calls each step runner in order, gated by its config flag
- `compile_comp_sets` moves into `steps/05_comp_sets.py`
- `get_area_search_results` logic moves into `steps/01_search_results.py`
- Step 7 (`area_summary`) runs both `AreaRagAggregator` and `DataExtractor`
- Integration test and all unit tests pass
- Docs updated
**Status**: Complete
