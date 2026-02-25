# Consolidate Outputs — Task Checklist

## Stage 1: Add Missing `os.makedirs` Calls
- [x] `scraper/airbnb_searcher.py` — add `os.makedirs` before L64 write
- [x] `scraper/reviews_scraper.py` — add `os.makedirs` before L55 write
- [x] `scraper/details_scraper.py` — add `os.makedirs` before L37 write
- [x] `scraper/details_fileset_build.py` — add `os.makedirs` before L175 write
- [x] `review_aggregator/property_review_aggregator.py` — add `os.makedirs` before first write in `rag_description_generation_chain()`
- [x] Verify: `pipenv run python -m py_compile` on all 5 files

## Stage 2: Update Scraper Module Paths
- [x] `scraper/airdna_scraper.py` L471: `"property_comp_sets"` → `"outputs/01_comp_sets"`
- [x] `scraper/airbnb_searcher.py` L64: `"property_search_results/"` → `"outputs/02_search_results/"`
- [x] `main.py` L103: `"property_search_results/"` → `"outputs/02_search_results/"`
- [x] `main.py` L106: `"property_search_results/"` → `"outputs/02_search_results/"`
- [x] `scraper/reviews_scraper.py` L55: `"property_reviews_scraped/"` → `"outputs/03_reviews_scraped/"`
- [x] `scraper/details_scraper.py` L37: `"property_details_scraped/"` → `"outputs/04_details_scraped/"`
- [x] `scraper/details_fileset_build.py` L152: `"property_details_scraped"` → `"outputs/04_details_scraped"` (read)
- [x] `scraper/details_fileset_build.py` L175: `"property_details_results/"` → `"outputs/05_details_results/"` (CSV write)
- [x] `scraper/details_fileset_build.py` L177: update log message string
- [x] `scraper/details_fileset_build.py` L181: `"property_details_results/"` → `"outputs/05_details_results/"` (house_rules)
- [x] `scraper/details_fileset_build.py` L186: `"property_details_results/"` → `"outputs/05_details_results/"` (descriptions)
- [x] `scraper/details_fileset_build.py` L191: `"property_details_results/"` → `"outputs/05_details_results/"` (highlights)
- [x] Verify: `pipenv run python -m py_compile` on all changed files

## Stage 3: Update Review Aggregator Module Paths
- [x] `review_aggregator/property_review_aggregator.py` L214: delete path → `"outputs/06_generated_summaries/..."`
- [x] `review_aggregator/property_review_aggregator.py` L227: listdir → `"outputs/03_reviews_scraped/"`
- [x] `review_aggregator/property_review_aggregator.py` L232: read path → `"outputs/03_reviews_scraped/..."`
- [x] `review_aggregator/property_review_aggregator.py` L238: listdir → `"outputs/06_generated_summaries/"` (IDEMPOTENCY)
- [x] `review_aggregator/property_review_aggregator.py` L246: read path → `"outputs/06_generated_summaries/..."`
- [x] `review_aggregator/property_review_aggregator.py` L285: write path → `"outputs/06_generated_summaries/..."`
- [x] `review_aggregator/property_review_aggregator.py` L308: write path → `"outputs/06_generated_summaries/..."`
- [x] `review_aggregator/area_review_aggregator.py` L67: listdir → `"outputs/06_generated_summaries/"`
- [x] `review_aggregator/area_review_aggregator.py` L84: read path → `"outputs/06_generated_summaries/..."`
- [x] `review_aggregator/area_review_aggregator.py`: verify `output_dir` stays `"reports"` (NO CHANGE)
- [x] `review_aggregator/data_extractor.py` L51: `summary_dir` default → `"outputs/06_generated_summaries"`
- [x] `review_aggregator/data_extractor.py` L236: output_path → `"outputs/07_extracted_data/area_data_{zipcode}.json"` + add `os.makedirs`
- [x] `review_aggregator/correlation_analyzer.py` L77: `output_dir` → `"outputs/08_correlation_results"`
- [x] `review_aggregator/correlation_analyzer.py` L78: verify `reports_dir` stays `"reports"` (NO CHANGE)
- [x] `review_aggregator/correlation_analyzer.py` L83: csv_path → `"outputs/05_details_results/..."`
- [x] `review_aggregator/correlation_analyzer.py` L96: desc_path → `"outputs/05_details_results/..."`
- [x] `review_aggregator/description_analyzer.py` L48: `output_dir` → `"outputs/09_description_analysis"`
- [x] `review_aggregator/description_analyzer.py` L49: verify `reports_dir` stays `"reports"` (NO CHANGE)
- [x] `review_aggregator/description_analyzer.py` L54: csv_path → `"outputs/05_details_results/..."`
- [x] `review_aggregator/description_analyzer.py` L66: desc_path → `"outputs/05_details_results/..."`
- [x] Verify: `pipenv run python -m py_compile` on all changed files

## Stage 4: Verify Infrastructure Caches — NO Code Changes
- [x] Confirm `utils/cache_manager.py` L24 `cache_dir` unchanged (`"cache/summaries"`)
- [x] Confirm `utils/cost_tracker.py` L52 log path unchanged (`"logs/cost_tracking.json"`)
- [x] Confirm `review_aggregator/openai_aggregator.py` cache logic unchanged

## Stage 5: Update Tests
- [x] `tests/conftest.py` L212: `tmp_path / "property_generated_summaries"` → `tmp_path / "outputs" / "06_generated_summaries"`
- [x] `tests/conftest.py` L242: `tmp_path / "property_reviews_scraped"` → `tmp_path / "outputs" / "03_reviews_scraped"`
- [x] `tests/conftest.py` L54-58: verify `tmp_cache_dir` unchanged
- [x] Review `tests/unit/test_area_review_aggregator.py` — verify mocked `os.listdir` patches work (filenames unchanged)
- [x] Review `tests/integration/test_pipeline_integration.py` — verify fixtures and mocks compatible
- [x] Review `tests/unit/test_data_extractor.py` — verify `summary_dir` override via fixture works
- [x] Review `tests/unit/test_description_analyzer.py` — verify `output_dir`/`reports_dir` overrides unchanged
- [x] Verify: `pipenv run pytest` passes

## Stage 6: Update `.gitignore` and Migrate Data
- [x] `.gitignore` L214: replace `property_*` with `outputs/`
- [x] Verify `reports/` is NOT gitignored
- [x] Create `outputs/` subdirectories (01 through 09)
- [x] Move `property_comp_sets/*` → `outputs/01_comp_sets/`
- [x] Move `property_search_results/*` → `outputs/02_search_results/`
- [x] Move `property_reviews_scraped/*` → `outputs/03_reviews_scraped/`
- [x] Move `property_details_scraped/*` → `outputs/04_details_scraped/`
- [x] Move `property_details_results/*` → `outputs/05_details_results/`
- [x] Move `property_generated_summaries/*` → `outputs/06_generated_summaries/` (CRITICAL — preserves idempotency cache)
- [x] Move `area_data_*.json` → `outputs/07_extracted_data/`
- [x] Move `property_correlation_results/correlation_*` → `outputs/08_correlation_results/`
- [x] Move `property_correlation_results/description_*` → `outputs/09_description_analysis/`
- [x] Delete `generated_summaries_97067.json` from root (legacy artifact)
- [x] Remove empty old `property_*` directories
- [x] Verify: no `property_*` dirs at root; `outputs/` tree intact; `reports/` unchanged

## Final Verification
- [x] `pipenv run python -m py_compile main.py` — compiles
- [x] `pipenv run pytest` — all tests pass (1 pre-existing unrelated failure in test_cache_manager)
- [x] `.gitignore` covers `outputs/`
- [x] `reports/` is committable (not gitignored)
- [ ] Present staged files and suggested commit message, wait for user review
