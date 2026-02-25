# Consolidate Outputs — Context

## Key Decisions

1. **`reports/` stays at root** — final human-readable reports (`.md` and `.json`), not intermediate pipeline data
2. **`outputs/` is intermediate pipeline data only** — numbered by config flag order (01–09)
3. **Infrastructure stays at root** — `cache/summaries/` and `logs/` are not pipeline outputs; `CacheManager` keys are content-based hashes with no directory names embedded
4. **`scrape_airdna` included as `01_`** — despite being a somewhat separate AirDNA workflow
5. **`scrape_reviews` gets two separate numbers** — `02_search_results` (listing discovery) and `03_reviews_scraped` (actual reviews) since they're conceptually distinct outputs
6. **`area_review_aggregator` NOT restructured** — no new `reports_dir` field needed since it keeps writing to `reports/`; the `correlation_analyzer` and `description_analyzer` already have both `output_dir` and `reports_dir` fields
7. **Data migration is mandatory** — especially `property_generated_summaries/` → `outputs/06_generated_summaries/` to preserve the file-existence idempotency cache and avoid reprocessing (costly OpenAI API calls)

## Key Files to Modify

### Source Modules (10 files)

| File | Changes | Lines |
|---|---|---|
| `scraper/airdna_scraper.py` | Change default `output_dir` | L471 |
| `scraper/airbnb_searcher.py` | Change write path + add `makedirs` | L64 |
| `scraper/reviews_scraper.py` | Change write path + add `makedirs` | L55 |
| `scraper/details_scraper.py` | Change write path + add `makedirs` | L37 |
| `scraper/details_fileset_build.py` | Change read+write paths (6 refs) + add `makedirs` | L152, L175, L177, L181, L186, L191 |
| `review_aggregator/property_review_aggregator.py` | Change 7 path refs + add `makedirs` | L214, L227, L232, L238, L246, L285, L308 |
| `review_aggregator/area_review_aggregator.py` | Change 2 read paths (summaries input) | L67, L84 |
| `review_aggregator/data_extractor.py` | Change default `summary_dir` + output path + add `makedirs` | L51, L236 |
| `review_aggregator/correlation_analyzer.py` | Change default `output_dir` + 2 read paths | L77, L83, L96 |
| `review_aggregator/description_analyzer.py` | Change default `output_dir` + 2 read paths | L48, L54, L66 |
| `main.py` | Change 2 search results path refs | L103, L106 |

### Test Files (2–4 files)

| File | Changes |
|---|---|
| `tests/conftest.py` | L212: `mock_summary_files_dir` fixture dir name; L242: `mock_review_files_dir` fixture dir name |
| `tests/unit/test_area_review_aggregator.py` | Verify mocked `os.listdir` patches — filenames unchanged, but may need to verify no hardcoded dir construction |
| `tests/integration/test_pipeline_integration.py` | Uses `mock_summary_files_dir` from conftest (covered by conftest change) |
| `tests/unit/test_data_extractor.py` | Uses `mock_summary_files_dir` from conftest (covered by conftest change) |

### Config/Meta Files (1 file)

| File | Changes |
|---|---|
| `.gitignore` | L214: Replace `property_*` with `outputs/` |

### Files NOT Changed

| File | Reason |
|---|---|
| `utils/cache_manager.py` | `cache_dir = "cache/summaries"` stays at root; keys are content-based |
| `utils/cost_tracker.py` | `logs/cost_tracking.json` stays at root |
| `review_aggregator/openai_aggregator.py` | Uses `CacheManager` internally; no path changes |
| `config.json` | No directory paths stored here |
| `Makefile` | No references to output directories |
| `tests/unit/test_cache_manager.py` | Uses `tmp_path` fixtures |
| `tests/unit/test_openai_aggregator.py` | Uses mocks |
| `tests/unit/test_description_analyzer.py` | Tests override `output_dir`/`reports_dir` to `tmp_path` |

## Two Caching Mechanisms

### 1. OpenAI Response Cache (`CacheManager`) — UNAFFECTED

- **Location**: `utils/cache_manager.py`, cache dir: `cache/summaries/`
- **Key format**: `{listing_id}_{md5(prompt)[:12]}_{md5(reviews)[:12]}`
- **No directory names in keys** — purely content-based
- **TTL**: 90 days (from `config.json`)
- **Used by**: `OpenAIAggregator.generate_summary()` → all aggregator modules

### 2. File-Existence Idempotency Cache — MUST UPDATE

- **Location**: `review_aggregator/property_review_aggregator.py` method `rag_description_generation_chain()` (L216-255)
- **How it works**: Lists `property_generated_summaries/` to find existing summaries, builds a dict of already-processed listing IDs, then `filter_out_processed_reviews()` skips them
- **Risk**: If directory references aren't updated, ALL listings would appear unprocessed and get re-submitted to OpenAI (expensive!)
- **Also read by**: `area_review_aggregator.py` (L67, L84) and `data_extractor.py` (L51, L63)

## Pipeline Dependency Chain

```
scrape_airdna ─────────────────────────────────── outputs/01_comp_sets/
  (independent)

scrape_reviews ───────────────────────────────┬── outputs/02_search_results/
                                              └── outputs/03_reviews_scraped/
                                                          │
scrape_details ──────────────────────────────── outputs/04_details_scraped/
          │                                               │
build_details ───────────────────────────────── outputs/05_details_results/
  reads: outputs/04_details_scraped/                      │
          │                                               │
          ├─── analyze_correlations ────────── outputs/08_correlation_results/ + reports/
          │      reads: outputs/05_details_results/
          │
          └─── analyze_descriptions ───────── outputs/09_description_analysis/ + reports/
                 reads: outputs/05_details_results/

aggregate_reviews ──────────────────────────── outputs/06_generated_summaries/
  reads: outputs/03_reviews_scraped/                      │
                                                          │
          ├─── aggregate_summaries ────────── reports/ (NO CHANGE)
          │      reads: outputs/06_generated_summaries/
          │
          └─── extract_data ───────────────── outputs/07_extracted_data/
                 reads: outputs/06_generated_summaries/
```

## STYLE_GUIDE Notes

Per `docs/STYLE_GUIDE.md`:
- "No magic strings or hardcoded values in business logic" — the current codebase violates this (all paths are hardcoded string literals). This refactor at minimum consolidates the paths but does NOT add a central path config. A follow-up task could extract these into a config module.
- Logging must use `logging` module (already the case)
- Prefer OOP (already the case — Pydantic models)
