# AirDNA Per-Listing Refactor — Tasks

## Stage 1: AGENTS.md Update
- [x] Add "Ask to switch to Agent mode when planning is complete" to Plan Mode Rules

## Stage 2: Directory Swap + Pipeline Reorder
- [x] Swap `STAGE_ORDER` in `pipeline_cache_manager.py`: `search` before `airdna`
- [x] Swap `STAGE_OUTPUT_DIRS`: search → `outputs/01_search_results`, airdna → `outputs/02_comp_sets`
- [x] Update `scraper/airbnb_searcher.py`: 2 refs `02_search_results` → `01_search_results`
- [x] Update `scraper/airdna_scraper.py`: 1 ref `01_comp_sets` → `02_comp_sets`
- [x] Update `main.py`: all refs to `01_comp_sets` → `02_comp_sets`, `02_search_results` → `01_search_results`
- [x] Reorder `run_tasks_from_config`: `scrape_airdna` block after search
- [x] Update `README.md`: all dir refs
- [x] Update `tests/unit/test_compile_comp_sets.py`: dir refs
- [x] Update `tests/unit/test_details_fileset_build.py`: dir refs
- [x] Run `pipenv run pytest` — all tests pass (234 passed)

## Stage 3: Rewrite AirDNA Scraper
- [x] Write tests for new `scrape_listing` method (red)
- [x] Write tests for `_build_rentalizer_url` (red)
- [x] Write tests for min_days_available filtering (red)
- [x] Replace `__init__`: `listing_ids` instead of `comp_set_ids`, add `min_days_available`
- [x] Add `_build_rentalizer_url(listing_id)` method
- [x] Add `scrape_listing(page, listing_id)` — extract from rentalizer page
- [x] Update `save_results` — write `listing_{id}.json`
- [x] Add Days_Available filter with logging
- [x] Remove: `_scroll_to_bottom`, `_should_continue_scrolling`, `_extract_listing_id`, `_extract_property_data`, `scrape_comp_set`, `_build_comp_set_url`
- [x] Update module docstring and `AIRDNA_BASE_URL`
- [x] Run `pipenv run pytest` — all tests pass (234 passed, 28 new)

## Stage 4: Update main.py Integration
- [x] Remove `self.airdna_comp_set_ids` from `__init__` and `load_configs`
- [x] Add `self.min_days_available` from config
- [x] Update `scrape_airdna` block: call `get_area_search_results()`, pass IDs to scraper
- [x] Update `compile_comp_sets`: glob `listing_*.json`
- [x] Remove comp-set-file-bypass in `get_area_search_results` (lines 117-123)
- [x] Run `pipenv run pytest` — all tests pass

## Stage 5: Update Config
- [x] Remove `airdna_comp_set_ids` from `config.json`
- [x] Add `min_days_available: 100` to `config.json`

## Stage 6: Update Tests
- [x] Delete stale test cases for removed behavior
- [x] Update `test_compile_comp_sets.py` for `listing_*.json` pattern
- [x] Update `test_get_area_search_results.py` — remove comp-set-exists case
- [x] Run `pipenv run pytest` — full green (233 passed, 84% coverage)
