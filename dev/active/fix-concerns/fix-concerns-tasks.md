# Fix CONCERNS.md Issues — Tasks

## Stage 1: Known Bugs (Crash Prevention)
- [x] 1.1 — Write failing test: short `sub_details` arrays (0, 1, 2 elements) in `test_details_fileset_build.py`
- [x] 1.1 — Refactor `parse_basic_details` to use substring search + bounds guards
- [x] 1.2 — Write failing test: `sub_details[2]` = "3 beds", no index 3
- [x] 1.2 — Fix `bathrooms` assignment (resolved by 1.1 refactor)
- [x] 1.3 — Write failing test: `get_overall_mean_rating({})` → expect `0.0`
- [x] 1.3 — Add empty-dict guard to `get_overall_mean_rating`
- [x] 1.4 — Write failing test: invalid ISO code → expect `ValueError`
- [x] 1.4 — Replace `return` with `raise ValueError(...)` in `locationer`
- [x] 1.5 — Fix `scrape_index` progress log to show overall progress
- [x] Run full test suite: `pipenv run pytest` — 333 passed

## Stage 2: Security Hardening
- [x] 2.1 — Write test: `OpenAIAggregator.__init__` logs warning on bad config
- [x] 2.1 — Narrow `except Exception: pass` → specific types + `logger.warning` in `openai_aggregator.py`
- [x] 2.2 — Write test: `CostTracker.__init__` logs warning on bad config
- [x] 2.2 — Narrow `except Exception: pass` → specific types + `logger.warning` in `cost_tracker.py`
- [x] 2.3 — Add `load_config()` utility in `tiny_file_handler.py` for repo-root resolution
- [x] 2.3 — Update all 7 callers to use `load_config()`
- [x] 2.3 — Add test: config loads from non-repo-root cwd
- [x] 2.4 — Add security note to `README.md` re: CDP port exposure
- [x] Run full test suite: `pipenv run pytest` — 336 passed

## Stage 3: Fragile Area Guards
- [x] 3.1 — Write failing test: missing `outputs/05_listing_summaries/` dir → expect empty list
- [x] 3.1 — Add `os.path.isdir` guard in `area_review_aggregator.py`
- [x] 3.2 — Read `prompts/prompt.json` to identify structural markers for complete summaries
- [x] 3.2 — Write failing tests: valid summary with "?", truncated summary without "?"
- [x] 3.2 — Replace `"?" in value` with structural check in `get_unfinished_aggregated_reviews`
- [x] 3.3 — Change `STAGE_ORDER`, `CASCADE_TARGET_STAGES`, `STAGE_OUTPUT_DIRS` to `ClassVar` in `pipeline_cache_manager.py`
- [x] 3.4 — Add `warnings.warn(...)` to `clear_stage` in `pipeline_cache_manager.py`
- [x] 3.4 — Write test asserting `DeprecationWarning` emitted
- [x] 3.4 — Verify no production callers of `clear_stage` remain
- [x] 3.5 — Grep for `get_cache_stats` callers; decide: populate or remove
- [x] 3.5 — Removed `get_cache_stats` stub and its test (no production callers)
- [x] Run full test suite: `pipenv run pytest` — 339 passed

## Stage 4: Tech Debt Cleanup
- [x] 4.1 — Write test: `pipeline_cache.is_file_fresh` called when cache provided in `reviews_scraper`
- [x] 4.1 — Replace `os.path.exists` with `pipeline_cache.is_file_fresh` (fallback to `os.path.exists` when None)
- [x] 4.2 — Update `test_compile_airdna_data.py` to import from `steps.03_airdna_data`; adjust fixture for `zipcode` param
- [x] 4.2 — Delete `compile_airdna_data` method + comment from `main.py`
- [x] 4.3 — Add comment to `LY_Revenue: 0.0` lines in `airdna_scraper.py`
- [x] 4.4 — Hoist `load_json_file("config.json")` out of `prompt_replacement` loop in `property_review_aggregator.py`
- [x] 4.4 — Hoist `load_json_file("config.json")` out of `task_chain` loop in `area_review_aggregator.py`
- [x] 4.5 — Hoist `load_json_file("prompts/prompt.json")` out of `process_single_listing` loop
- [x] Run full test suite: `pipenv run pytest` — 342 passed

## Stage 5: Performance Improvements
- [ ] 5.1 — Write test: AirDNA sleep range read from config (defaults to 10/15)
- [ ] 5.1 — Make `time.sleep(random.uniform(...))` configurable in `airdna_scraper.py`
- [ ] 5.2 — Write test: `page.locator("body").inner_text()` called once per listing
- [ ] 5.2 — Fetch page text once in `scrape_listing`, pass to both extraction methods
- [ ] 5.3 — Write test: `search_dimensions` parameter produces expected grid box count
- [ ] 5.3 — Accept `search_dimensions` from config in `airbnb_searcher.py`
- [ ] 5.4 — Document per-listing streaming as future improvement (DEFERRED — no implementation)
- [ ] Run full test suite: `pipenv run pytest`
