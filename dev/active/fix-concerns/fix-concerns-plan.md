# Fix CONCERNS.md Issues — Plan

Address all 24 concerns across 5 categories in 5 phases, prioritized by severity: crash-causing bugs → security hardening → fragile-area guards → tech debt cleanup → performance improvements. Each phase is independently verifiable via `pipenv run pytest`.

---

## Stage 1: Known Bugs (Crash Prevention)
**Goal**: Eliminate 5 bugs that cause crashes (`IndexError`, `UnboundLocalError`, `ZeroDivisionError`, `TypeError`, misleading logs).
**Success Criteria**:
- Empty `sub_details` arrays (0–2 elements) produce graceful defaults instead of `IndexError`
- `bathrooms` is always assigned before use — no `UnboundLocalError`
- `get_overall_mean_rating({})` returns `0.0` instead of raising `ZeroDivisionError`
- `locationer()` with invalid input raises `ValueError` instead of returning `None`
- `scrape_index` accumulates across retry passes
- All existing tests pass; new tests added for each fix

**Status**: Complete
- **File**: `scraper/details_fileset_build.py` lines 81–96
- **Change**: Refactor `parse_basic_details` to search for "bedrooms"/"beds"/"baths" substrings across all `sub_details` items rather than hard-indexing positions 1, 2, 3. Guard every index access with `len()` check.
- **Test**: Add cases to `tests/unit/test_details_fileset_build.py` for `sub_details` arrays with 0, 1, and 2 elements.

### 1.2 — Fix `bathrooms` unbound variable
- **File**: `scraper/details_fileset_build.py` lines 87–96
- **Change**: Likely resolved by 1.1's refactor. If not, initialize `bathrooms = None` before conditionals; only assign to property dict when non-None.
- **Test**: Add case where `sub_details[2]` = "3 beds" and `sub_details[3]` is absent.

### 1.3 — Fix `get_overall_mean_rating` divide-by-zero
- **File**: `review_aggregator/property_review_aggregator.py` line 74
- **Change**: Add `if not reviews: return 0.0` at function entry.
- **Test**: Add test passing empty `{}` to `get_overall_mean_rating`.

### 1.4 — Fix `locationer` returning None
- **Files**: `scraper/location_calculator.py` line 19; `scraper/airbnb_searcher.py` lines 15–17
- **Change**: Replace `return` (implicit None) in `locationer` with `raise ValueError(f"Could not geocode postal_code={postal_code}, iso_code={iso_code}")`. Caller naturally propagates.
- **Test**: Update `tests/unit/test_location_calculator.py` — assert `ValueError` raised on invalid input.

### 1.5 — Fix `scrape_index` counter reset on retry
- **File**: `scraper/reviews_scraper.py` lines 68, 84–85
- **Change**: Move `scrape_index = 0` before the outer retry loop so it accumulates. Log as "property N of TOTAL_NEEDED".
- **Test**: Logging-only. Verify existing tests pass.

---

## Stage 2: Security Hardening
**Goal**: Narrow silent exception swallowing, document CDP risk, improve config path resolution.
**Success Criteria**:
- Bad config in `OpenAIAggregator.__init__` and `CostTracker.__init__` logs a warning with the exception type
- Only expected exception types are caught (no bare `except Exception`)
- README documents the security implication of `--remote-debugging-port=9222`
- Config loading uses repo-root-anchored path resolution

**Status**: Complete
- **File**: `review_aggregator/openai_aggregator.py` lines 58–60
- **Change**: `except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:` + `logger.warning(...)`. Follow pattern in `utils/pipeline_cache_manager.py:93`.
- **Test**: Add test verifying warning logged on bad config.

### 2.2 — Narrow exception handling in `CostTracker.__init__`
- **File**: `utils/cost_tracker.py` lines 45–46
- **Change**: Same as 2.1.
- **Test**: Add test verifying warning logged on bad config.

### 2.3 — Anchor config.json path resolution
- **Files**: 7 files that call `load_json_file("config.json")` with a relative path
- **Change**: Add an `anchored_config_path()` helper or update `load_json_file` to resolve relative to repo root via `Path(__file__).resolve().parent.parent`. Scope boundary: path anchoring only, not full dependency injection.
- **Test**: Verify tests pass. Add test that config loads correctly from a different working directory.

### 2.4 — Document AirDNA CDP security implication
- **File**: `README.md`
- **Change**: Add a "Security Notes" section documenting the `--remote-debugging-port=9222` exposure risk in multi-user environments.
- **Test**: N/A (docs only).

---

## Stage 3: Fragile Area Guards
**Goal**: Harden 5 fragile areas to prevent silent failures and misleading state.
**Success Criteria**:
- `area_review_aggregator` returns empty list when `outputs/05_listing_summaries/` doesn't exist
- Incomplete LLM response detection uses structural check, not `"?"` substring
- `STAGE_ORDER` etc. are `ClassVar` — Pydantic no longer treats them as instance fields
- `clear_stage` emits `DeprecationWarning`
- `get_cache_stats` either populated or removed

**Status**: Complete
- **File**: `review_aggregator/area_review_aggregator.py` lines 53–54
- **Change**: Guard `os.listdir` with `if not os.path.isdir(...): return []`.
- **Test**: Add test for missing directory → graceful empty result.

### 3.2 — Replace `"?"` heuristic for incomplete LLM responses
- **File**: `review_aggregator/property_review_aggregator.py` lines 161–168
- **Change**: Replace `"?" in value` with structural check (expected section headers or minimum length). Examine `prompts/prompt.json` during implementation to determine markers.
- **Test**: Add cases for valid summary with "?" (false positive) and truncated summary without "?" (false negative).

### 3.3 — Declare pipeline cache constants as `ClassVar`
- **File**: `utils/pipeline_cache_manager.py` lines 29–56
- **Change**: `from typing import ClassVar`. Change annotations to `ClassVar[list[str]]`, `ClassVar[set[str]]`, `ClassVar[dict[str, str]]`.
- **Test**: Verify `tests/unit/test_pipeline_cache_manager.py` and `test_pipeline_cache_mtime.py` pass.

### 3.4 — Add deprecation warning to `clear_stage`
- **File**: `utils/pipeline_cache_manager.py` lines 305–318
- **Change**: `import warnings; warnings.warn("clear_stage is deprecated, use clear_stage_for_zipcode", DeprecationWarning, stacklevel=2)`.
- **Test**: Add test asserting `DeprecationWarning` is emitted. Verify no production callers remain.

### 3.5 — Implement or remove `get_cache_stats` stub
- **File**: `utils/pipeline_cache_manager.py` lines 516–532
- **Change**: Grep for callers. If none, remove. If used, populate `stats["stages"]`.
- **Test**: If kept, add test for enabled cache with populated stage stats.

---

## Stage 4: Tech Debt Cleanup
**Goal**: Remove duplication, wire up unused parameters, hoist repeated I/O out of loops.
**Success Criteria**:
- `reviews_scraper` uses `pipeline_cache.is_file_fresh()` for cache decisions
- Single `compile_airdna_data` definition lives in `steps/03_airdna_data.py`; test imports from there
- `config.json` and `prompts/prompt.json` loaded once per run, not per-listing
- `LY_Revenue` field is documented as unsupported

**Status**: Complete

### 4.1 — Wire `pipeline_cache` in `reviews_scraper`
- **File**: `scraper/reviews_scraper.py` line 47
- **Change**: Replace `os.path.exists(output_path)` with `pipeline_cache.is_file_fresh("reviews_scrape", output_path)` when `pipeline_cache` is provided. Fall back to `os.path.exists` when None.
- **Test**: Add test verifying `is_file_fresh` called when cache is provided.

### 4.2 — Remove duplicated `compile_airdna_data` from `main.py`
- **Files**: `main.py` lines 48–71; `tests/unit/test_compile_airdna_data.py` line 18
- **Change**: Update test to import from `steps.03_airdna_data` (that version takes `zipcode: str`, not `self`). Adjust test fixture. Then delete the method + comment from `main.py`.
- **Test**: Re-run `tests/unit/test_compile_airdna_data.py`.

### 4.3 — Document `LY_Revenue` field as unsupported
- **File**: `scraper/airdna_scraper.py` lines 360, 376
- **Change**: Add comment: `# Not extractable from AirDNA Rentalizer page; placeholder for future implementation`.
- **Test**: N/A (comment only). Existing tests pass.

### 4.4 — Hoist config.json load out of per-listing loops
- **Files**: `review_aggregator/property_review_aggregator.py` line 82; `review_aggregator/area_review_aggregator.py` line 92
- **Change**: Load `iso_code` once in `task_chain()`, pass as parameter to `prompt_replacement` / use as local.
- **Test**: Verify `load_json_file` mock called once, not per-listing.

### 4.5 — Hoist `prompt.json` load out of per-listing loop
- **File**: `review_aggregator/property_review_aggregator.py` line 119
- **Change**: Load prompt once in `task_chain()`, pass `generated_prompt` to `process_single_listing`.
- **Test**: Verify prompt loaded once.

---

## Stage 5: Performance Improvements
**Goal**: Reduce unnecessary I/O and make hardcoded delays configurable.
**Success Criteria**:
- AirDNA sleep range readable from `config.json` with 10/15 default
- Page body text fetched once per listing, shared between extraction methods
- Search grid dimensions configurable via `config.json` with default 2
- Per-listing review streaming documented as future improvement (deferred)

**Status**: Not Started

### 5.1 — Make AirDNA sleep range configurable
- **File**: `scraper/airdna_scraper.py` lines 532–534
- **Change**: Read `airdna_sleep_min` / `airdna_sleep_max` from config. Default 10/15.
- **Test**: Add test that config values are respected.

### 5.2 — Share page body text between extraction methods
- **File**: `scraper/airdna_scraper.py`
- **Change**: In `scrape_listing`, call `page.locator("body").inner_text()` once, pass result to `_extract_header_metrics` and `_extract_kpi_metrics`.
- **Test**: Verify `inner_text` mock called once per listing.

### 5.3 — Make search grid dimensions configurable
- **File**: `scraper/airbnb_searcher.py` line 44
- **Change**: Accept `search_dimensions` from config (default 2). Pass through to `boxed_search`.
- **Test**: Add test that dimension values produce expected grid box count.

### 5.4 — Per-listing review streaming (DEFERRED)
- **File**: `review_aggregator/property_review_aggregator.py` lines 196–204
- **Rationale**: Highest-risk refactor, low urgency. Document as known improvement. Implement only if memory pressure is observed.
