# Codebase Concerns

**Analysis Date:** 2026-03-08

---

## Tech Debt

**`pipeline_cache` parameter accepted but ignored in `scrape_reviews`:**
- Issue: `scrape_reviews` in `scraper/reviews_scraper.py` accepts a `pipeline_cache` parameter (line 24), documents it in the docstring, and it is passed in from `steps/04_reviews_scrape.py`, but the parameter is never used inside the function body. Per-file freshness skipping (like `details_scraper.py` does) was never implemented here.
- Files: `scraper/reviews_scraper.py`, `steps/04_reviews_scrape.py`
- Impact: Every run re-checks disk for existing files via `os.path.exists` rather than the TTL-aware `pipeline_cache.is_file_fresh`, so stale-file detection for reviews ignores the TTL window entirely.
- Fix approach: Add a `pipeline_cache.is_file_fresh("reviews_scrape", output_path)` guard inside the per-listing loop, mirroring the pattern in `scraper/details_scraper.py` lines 28-33.

**`compile_airdna_data` duplicated between `main.py` and `steps/03_airdna_data.py`:**
- Issue: An identical `compile_airdna_data` function exists in both `main.py` (lines 52-71) and `steps/03_airdna_data.py`. The comment in `main.py` acknowledges this: `# ----- kept for test_compile_airdna_data -----`.
- Files: `main.py`, `steps/03_airdna_data.py`
- Impact: Two divergent copies will drift. Changes to the step version won't reach the `main.py` version tested by `tests/unit/test_compile_airdna_data.py`.
- Fix approach: Update `test_compile_airdna_data.py` to import from `steps.03_airdna_data`, then remove the copy from `main.py`.

**`LY_Revenue` field always hardcoded to `0.0`:**
- Issue: `AirDNAScraper.scrape_listing` always sets `"LY_Revenue": 0.0` (lines 377, 351 in `scraper/airdna_scraper.py`). Last-year revenue is never extracted from the AirDNA page.
- Files: `scraper/airdna_scraper.py`
- Impact: Any downstream analysis that relies on `LY_Revenue` will silently receive `0.0` for every property.
- Fix approach: Implement extraction in `_extract_kpi_metrics` or document the field as unsupported and remove it from the schema.

**`config.json` loaded at call-time inside per-listing loops:**
- Issue: `property_review_aggregator.py` calls `load_json_file("config.json")` inside `prompt_replacement` (line 82), which is called once per listing. `area_review_aggregator.py` does the same inside `task_chain` (line 92).
- Files: `review_aggregator/property_review_aggregator.py`, `review_aggregator/area_review_aggregator.py`
- Impact: Disk I/O on every listing iteration; also means the config cannot be injected for testing without patching the file system.
- Fix approach: Pass `iso_code` as a constructor argument or load config once at init time.

**`prompts/prompt.json` loaded inside per-listing loop:**
- Issue: `property_review_aggregator.py` calls `load_json_file("prompts/prompt.json")` inside `process_single_listing` (line 119), which is called for every listing in the run.
- Files: `review_aggregator/property_review_aggregator.py`
- Impact: File I/O on every OpenAI call; prompt template is re-read hundreds of times per pipeline run.
- Fix approach: Load prompt once in `task_chain` and pass to `process_single_listing`.

**`get_cache_stats` method is a stub:**
- Issue: `PipelineCacheManager.get_cache_stats` (lines 516-532 in `utils/pipeline_cache_manager.py`) initializes a `stats["stages"]` dict but never populates it, always returning `{}` for the stages key.
- Files: `utils/pipeline_cache_manager.py`
- Impact: Any caller expecting per-stage cache statistics receives an empty object.
- Fix approach: Populate `stats["stages"]` by iterating `STAGE_ORDER` and calling `is_stage_fresh` for a given zipcode, or remove the method if it is unused.

**`clear_stage` marked deprecated but still present with no runtime warning:**
- Issue: `PipelineCacheManager.clear_stage` (lines 305-318) has a docstring `.. deprecated:: Use clear_stage_for_zipcode`. The old method wipes the entire output directory regardless of zipcode.
- Files: `utils/pipeline_cache_manager.py`
- Impact: Risk of cross-zipcode data loss if any code accidentally calls the deprecated method. No deprecation warning is emitted at runtime.
- Fix approach: Add a `warnings.warn` call and verify no callers remain, then remove.

---

## Known Bugs

**`sub_details` array accessed without bounds check at index 1 and 2:**
- Symptoms: `IndexError` crash when parsing properties whose `sub_description.items` list has fewer than 3 elements (e.g. studio apartments showing only guest count and one detail).
- Files: `scraper/details_fileset_build.py` lines 83-91
- Trigger: Any listing where the Airbnb API returns a `sub_description.items` array shorter than 3 entries. Index 3 is guarded (`len(sub_details) > 3`) but indexes 1 and 2 are not.
- Workaround: The outer `parse_basic_details` call is wrapped in a check in `build_fileset` but the `IndexError` will propagate unhandled to the caller, causing that property to be silently dropped.

**`bathrooms` variable may be unassigned when `beds` branch is taken:**
- Symptoms: `UnboundLocalError: local variable 'bathrooms' referenced before assignment` when `sub_details[2]` contains "beds" and `sub_details[3]` is missing or does not contain "baths".
- Files: `scraper/details_fileset_build.py` lines 87-96
- Trigger: A listing where index 2 is "N beds" and index 3 does not exist or does not contain "baths". The else-branch on line 91 assigns `bathrooms` from `sub_details[2]` splitting on "baths", but that line is only reached when "beds" is NOT in `sub_details[2]`, making the assignment unreachable in the "beds" case.
- Workaround: None; bathroom count will be missing for affected properties.

**`get_overall_mean_rating` divides by zero on empty reviews dict:**
- Symptoms: `ZeroDivisionError` crash when `reviews` dict is empty.
- Files: `review_aggregator/property_review_aggregator.py` line 67
- Trigger: Called in `task_chain` (line 223) after loading all review files. If the review output directory is empty (no files scraped yet), `reviews` is an empty dict and `len(reviews)` is 0.
- Workaround: None; the pipeline will crash before processing begins.

**`locationer` returns `None` on error, caller unpacks as tuple:**
- Symptoms: `TypeError: cannot unpack non-iterable NoneType object` when an invalid ISO code or postal code is provided.
- Files: `scraper/location_calculator.py` line 22, `scraper/airbnb_searcher.py` line 17
- Trigger: `locationer` returns `None` on exception but `airbnb_searcher` unconditionally unpacks the result into `ne_lat, sw_lat, ne_lon, sw_lon`.
- Workaround: Ensure `config.json` contains a valid `zipcode` and `iso_code` before running.

**`scrape_index` progress counter is incorrect during retry passes:**
- Symptoms: Logged "property X of Y" counts reset to 1 on each retry pass; the denominator `remaining` reflects total missing listings but `scrape_index` counts only within the current pass iteration, so the logged fraction is misleading.
- Files: `scraper/reviews_scraper.py` lines 68, 85
- Trigger: Any run that exceeds the 20% failure threshold and triggers a retry pass.
- Workaround: Logging-only issue; does not affect correctness of scraping.

---

## Security Considerations

**Hardcoded relative path `config.json` loaded throughout the codebase:**
- Risk: All modules that call `load_json_file("config.json")` or `open("config.json")` resolve relative to the process working directory. If the tool is ever invoked from a directory other than the repo root (e.g. in a test harness, container, or CI job), a different `config.json` may be loaded silently or the load will fail with a confusing error.
- Files: `utils/pipeline_cache_manager.py:67`, `review_aggregator/openai_aggregator.py:44`, `review_aggregator/property_review_aggregator.py:82`, `review_aggregator/area_review_aggregator.py:92`, `utils/cost_tracker.py:40`, `main.py:45`, `scraper/airdna_scraper.py:567`
- Current mitigation: `.env` is git-ignored; `OPENAI_API_KEY` is loaded via environment variable by the OpenAI SDK automatically.
- Recommendations: Use `Path(__file__).parent` to anchor config loading to a known directory, or pass config as a dependency rather than reading from disk in constructors.

**AirDNA scraper requires Chrome with remote debugging port open:**
- Risk: Running Chrome with `--remote-debugging-port=9222` exposes a CDP endpoint on localhost. If the machine is multi-user or runs in a shared environment, any local process can attach to the browser and access the authenticated AirDNA session.
- Files: `scraper/airdna_scraper.py`, `config.json` key `airdna_cdp_url`
- Current mitigation: CDP URL defaults to `localhost:9222` (not bound to external interface).
- Recommendations: Document the security implication in the README; consider using a dedicated browser profile with minimal stored credentials.

**Broad `except Exception: pass` silently swallows failures in `OpenAIAggregator.__init__`:**
- Risk: If `config.json` contains invalid types for `model`, `temperature`, etc., the exception is silently swallowed (line 54 in `review_aggregator/openai_aggregator.py`) and the object is initialized with defaults — including potentially the wrong model name. Same pattern in `utils/cost_tracker.py:45`.
- Files: `review_aggregator/openai_aggregator.py:54`, `utils/cost_tracker.py:45`
- Current mitigation: None.
- Recommendations: Catch only `(FileNotFoundError, json.JSONDecodeError, KeyError, TypeError)` as is already done in `utils/pipeline_cache_manager.py:93`.

---

## Performance Bottlenecks

**AirDNA scraper sleeps 10-15 seconds between every listing, not configurable:**
- Problem: `time.sleep(random.uniform(10, 15))` is called unconditionally after every page load (line 530 in `scraper/airdna_scraper.py`), plus a mandatory `PAGE_LOAD_WAIT_SECONDS = 5` delay per page (line 363). At 12.5s average, scraping 500 listings takes ~2.5 hours ignoring network latency.
- Files: `scraper/airdna_scraper.py`
- Cause: Anti-detection rate limiting; necessary but hardcoded and cannot be tuned via config.
- Improvement path: Expose sleep range in `config.json` so it can be tightened for internal/trusted environments.

**`_extract_header_metrics` and `_extract_kpi_metrics` each fetch full page body text independently:**
- Problem: `page.locator("body").inner_text()` is called separately in both `_extract_kpi_metrics` (line 275) and `_extract_header_metrics` (line 218 fallback path) on the same page object within a single `scrape_listing` call.
- Files: `scraper/airdna_scraper.py`
- Cause: The two methods were developed independently without sharing the page text.
- Improvement path: Fetch full page text once in `scrape_listing` and pass it to both extraction methods as a parameter.

**All review files loaded into memory at once in `property_review_aggregator.py`:**
- Problem: `task_chain` builds a single `reviews` dict containing every review for every listing (lines 196-204). For large zip codes with thousands of listings and hundreds of reviews each, this can exhaust available RAM.
- Files: `review_aggregator/property_review_aggregator.py`
- Cause: Batch-load design; no streaming or pagination.
- Improvement path: Process listings one at a time by iterating review files directly rather than loading all into memory first.

**`boxed_search` is hardcoded to a 2×2 = 4 grid, not configurable:**
- Problem: `airbnb_searcher` always calls `boxed_search(..., dimensions=2)` (line 44 of `scraper/airbnb_searcher.py`), creating exactly 4 search boxes. The code logs a warning when any box hits the 280-result cap but cannot automatically subdivide or use a finer grid.
- Files: `scraper/airbnb_searcher.py`
- Cause: `dimensions` parameter exists on the inner function but is never exposed to `config.json`.
- Improvement path: Add a `search_dimensions` key to `config.json` and pass it through; or implement adaptive subdivision when the 280-result cap is detected.

---

## Fragile Areas

**`details_fileset_build.py` — rigid Airbnb API response structure assumed:**
- Files: `scraper/details_fileset_build.py` lines 81-96
- Why fragile: `sub_description.items` is accessed at hardcoded indices 1, 2, and 3 to extract bedroom/bath counts. If Airbnb changes the order of fields in the `items` array or returns a shorter list, parsing silently produces wrong values or crashes.
- Safe modification: Add `len(sub_details) > N` guards before each index access; parse by searching for "bedrooms"/"beds"/"baths" substrings across all items rather than relying on position.
- Test coverage: `tests/unit/test_details_fileset_build.py` exists but likely uses fixture data that matches the current expected structure.

**`AirDNAScraper` — text-regex extraction tightly coupled to AirDNA page layout:**
- Files: `scraper/airdna_scraper.py` methods `_extract_kpi_metrics`, `_extract_header_metrics`
- Why fragile: All metric extraction uses `re.search` against `page.locator("body").inner_text()`. Any change to the AirDNA page layout (label rewordings, whitespace changes, new fields inserted before existing ones) will silently produce zero values for affected metrics. The `_is_empty_result` check only catches complete failures where ALL four KPI metrics drop to zero simultaneously; partial failures (e.g. only `ADR` returns 0) are not detected.
- Safe modification: Add per-metric validation logging; test with `inspect_mode=True` after any AirDNA UI update.
- Test coverage: `tests/unit/test_airdna_scraper.py` exists but cannot easily test against real page rendering.

**`property_review_aggregator.py` — `"?"` heuristic for detecting incomplete LLM responses:**
- Files: `review_aggregator/property_review_aggregator.py` lines 161-168
- Why fragile: `get_unfinished_aggregated_reviews` flags any summary containing `"?"` as incomplete and re-processes it. Valid summaries that include question marks in quoted review text or rhetorical questions will trigger false re-processing, wasting API budget. Conversely, a truncated summary with no question marks will not be retried.
- Safe modification: Replace with a structural check (e.g. presence of all 5 expected section headers) or a minimum length threshold.
- Test coverage: Covered by `tests/unit/test_property_review_aggregator.py` but only with simple fixture strings.

**`area_review_aggregator.py` — `os.listdir` on hardcoded path without existence guard:**
- Files: `review_aggregator/area_review_aggregator.py` lines 53-54
- Why fragile: Calls `os.listdir("outputs/05_listing_summaries/")` directly. If the directory does not exist (stage 06 never ran), this raises `FileNotFoundError` rather than returning gracefully.
- Safe modification: Add an `os.path.isdir` guard before `os.listdir`, matching the pattern in `scraper/details_fileset_build.py:194-199`.
- Test coverage: `tests/unit/test_area_review_aggregator.py` exists.

**`PipelineCacheManager` — `STAGE_ORDER`, `CASCADE_TARGET_STAGES`, `STAGE_OUTPUT_DIRS` declared as Pydantic instance fields:**
- Files: `utils/pipeline_cache_manager.py` lines 29-56
- Why fragile: These three collections are declared as Pydantic `BaseModel` field annotations with default values. Pydantic treats them as per-instance fields, meaning they can be overwritten on any instance. They are intended to be class-level constants; treating them as mutable instance state is misleading and could lead to subtle bugs if one code path mutates them.
- Safe modification: Declare them as `ClassVar` (from `typing`) or move them to module-level constants outside the class.
- Test coverage: `tests/unit/test_pipeline_cache_manager.py` and `tests/unit/test_pipeline_cache_mtime.py` exist.

---

## Scaling Limits

**Single-zipcode pipeline design:**
- Current capacity: One zipcode per run; all output paths are scoped to a single `config["zipcode"]` value.
- Limit: Running multiple zipcodes requires multiple sequential invocations; there is no batch mode, parallelism, or per-zipcode isolation of in-memory state within a single `AirBnbReviewAggregator` instance.
- Scaling path: Add a `zipcodes: list[str]` config key and loop over zipcodes in `run_tasks_from_config`, reinitializing stateful objects per zipcode.

**Cost log `requests` list is unbounded per session:**
- Current capacity: `CostTracker.session_stats["requests"]` grows by one entry per API call. The on-disk log is capped at 100 sessions (`utils/cost_tracker.py` line 221) but individual sessions can contain thousands of request records, all held in memory.
- Limit: Memory and disk usage grow unbounded within a single long session.
- Scaling path: Cap the in-memory `requests` list or move to append-only per-request logging.

---

## Dependencies at Risk

**`pyairbnb` (unofficial Airbnb scraping library):**
- Risk: Unofficial, reverse-engineered client. Airbnb API changes or Terms of Service enforcement can break all search, detail, and review scraping without warning. No official support or SLA.
- Impact: Steps 01, 02, and 04 (`search_results`, `details_scrape`, `reviews_scrape`) become non-functional simultaneously.
- Migration plan: Monitor the `pyairbnb` repo for breakage; build a fallback using direct HTTP requests with a maintained cookie/session strategy, or accept breakage as an operational risk.

**`playwright` CDP connection depends on a user-managed Chrome session:**
- Risk: AirDNA scraping depends on the user manually launching Chrome with `--remote-debugging-port=9222` and being authenticated. Session expiry, Chrome updates, or AirDNA UI redesigns will break the scraper silently (empty metrics returned, not an exception).
- Impact: Step 03 (`airdna_data`) produces zero-value data silently for all affected listings.
- Migration plan: Add an authenticated session pre-check before the scraping loop begins; abort and log an error rather than silently recording zeros.

---

## Missing Critical Features

**No validation that `config.json` is in the required working directory before pipeline starts:**
- Problem: Every module resolves `config.json` as a relative path. If `main.py` is invoked from the wrong directory, multiple modules fail independently with unhelpful `FileNotFoundError` messages rather than a single clear startup error.
- Blocks: Clean user experience and any CI/CD usage outside the repo root.

**No cross-zipcode review file isolation in `property_review_aggregator.py`:**
- Problem: `task_chain` loads ALL files in `outputs/04_reviews_scrape/` that start with `"reviews_"`, regardless of zipcode (line 197). If multiple zipcodes have been scraped, reviews from other zipcodes will be included in the current area's analysis.
- Files: `review_aggregator/property_review_aggregator.py` line 197
- Blocks: Accurate results for any user who runs the pipeline against more than one zipcode.

---

## Test Coverage Gaps

**`scraper/reviews_scraper.py` — `pipeline_cache` parameter not exercised:**
- What's not tested: The `pipeline_cache` argument is accepted but never used in the function; tests cannot verify cache-skip behavior because the feature is not implemented.
- Files: `scraper/reviews_scraper.py`, `tests/unit/test_reviews_scraper.py`
- Risk: Dead parameter creates false confidence that TTL-based skipping works for reviews.
- Priority: Medium

**`scraper/details_fileset_build.py` — edge cases in `parse_basic_details`:**
- What's not tested: Listings with `sub_description.items` shorter than 3 items, studios (0 bedrooms), or properties missing the "baths" substring entirely.
- Files: `scraper/details_fileset_build.py`, `tests/unit/test_details_fileset_build.py`
- Risk: `IndexError` or `UnboundLocalError` in production on non-standard listing data.
- Priority: High

**`scraper/location_calculator.py` — `None` return on error path:**
- What's not tested: The path where `locationer` returns `None` and the caller (`airbnb_searcher`) tries to unpack it, which raises `TypeError`.
- Files: `scraper/location_calculator.py`, `tests/unit/test_location_calculator.py`
- Risk: Uncaught crash on invalid postal/ISO code input with no helpful error message.
- Priority: High

**`review_aggregator/property_review_aggregator.py` — zero reviews edge case:**
- What's not tested: `get_overall_mean_rating` being called with an empty reviews dict, causing `ZeroDivisionError`.
- Files: `review_aggregator/property_review_aggregator.py`, `tests/unit/test_property_review_aggregator.py`
- Risk: Pipeline crashes before any LLM calls are made when no review files exist.
- Priority: High

**`utils/pipeline_cache_manager.py` — `get_cache_stats` stub behavior:**
- What's not tested: The `get_cache_stats` method always returns an empty `stages` dict; no tests verify this behavior or document the expected populated format.
- Files: `utils/pipeline_cache_manager.py`, `tests/unit/test_pipeline_cache_manager.py`
- Risk: Silent API contract breakage if callers expect stage-level data.
- Priority: Low

---

*Concerns audit: 2026-03-08*
