## Key Files

| File | Role |
|------|------|
| `utils/pipeline_cache_manager.py` | **New** — TTL-based pipeline cache manager |
| `utils/cache_manager.py` | Existing OpenAI-specific cache — reference pattern for Pydantic `BaseModel` cache class |
| `main.py` | Pipeline orchestrator — `load_configs()` + `run_tasks_from_config()`. Entry point for all cache checks |
| `config.json` | Boolean flags + parameters; adding `pipeline_cache_*` and `force_refresh_*` keys |
| `scraper/reviews_scraper.py` | Reviews scraper — adding per-file TTL skip logic |
| `scraper/details_scraper.py` | Details scraper — adding per-file TTL skip logic |
| `scraper/airbnb_searcher.py` | Search — cache check happens at `main.py` level |
| `scraper/details_fileset_build.py` | Fileset builder — cache check happens at `main.py` level |
| `review_aggregator/property_review_aggregator.py` | Property aggregation — enhancing `filter_out_processed_reviews()` with TTL awareness |
| `review_aggregator/area_review_aggregator.py` | Area aggregation — recording outputs post-completion |
| `tests/unit/test_pipeline_cache_manager.py` | **New** — unit tests for `PipelineCacheManager` |
| `tests/conftest.py` | Shared test fixtures — adding pipeline cache fixtures |
| `cache/pipeline_metadata.json` | **New** (runtime) — metadata tracking timestamps per stage/file |

## Decisions

| Decision | Chose | Over | Reason |
|----------|-------|------|--------|
| Cache architecture | New `PipelineCacheManager` class | Extending existing `CacheManager` | `CacheManager` is OpenAI-specific (content-hashed keys, prompt+reviews signatures). Pipeline caching uses file-path-based, stage-level grouping. Single responsibility. |
| Timestamp source | Explicit metadata JSON (`cache/pipeline_metadata.json`) | Filesystem `mtime` (`os.path.getmtime()`) | `mtime` is fragile — git operations, file copies, and rsync reset it. Explicit metadata is portable across local/S3. |
| TTL scope | Single global TTL (`pipeline_cache_ttl_days`) | Per-stage TTL values | User preference. Simpler config. `force_refresh_*` flags provide per-stage escape hatches. |
| Scraper integration | Optional `pipeline_cache=None` parameter | Required dependency | Backward compatible. Scrapers remain callable without caching. Easier unit testing. |
| Stage-level vs file-level | Both: stage-level for single-output stages, file-level for multi-file stages | Stage-level only | Reviews/details produce hundreds of files. Skipping at stage level would lose granularity for partial runs or newly added listings. |

## Pipeline Stages Covered (0–6)

| # | Stage Name | Config Flag | Outputs | Cache Granularity |
|---|-----------|------------|---------|-------------------|
| 0 | `airdna` | `scrape_airdna` | `outputs/01_comp_sets/comp_set_{zipcode}.json` | Stage-level |
| 1 | `search` | (implicit in `get_area_search_results`) | `outputs/02_search_results/search_results_{zipcode}.json` | File-level |
| 2 | `reviews` | `scrape_reviews` | `outputs/03_reviews_scraped/reviews_{zipcode}_{id}.json` | File-level (per listing) |
| 3 | `details` | `scrape_details` | `outputs/04_details_scraped/property_details_{room_id}.json` | File-level (per listing) |
| 4 | `build_details` | `build_details` | 4 files in `outputs/05_details_results/` | Stage-level |
| 5 | `aggregate_reviews` | `aggregate_reviews` | `outputs/06_generated_summaries/generated_summaries_{zipcode}_{id}.json` | File-level (per listing) |
| 6 | `aggregate_summaries` | `aggregate_summaries` | `reports/area_summary_{zipcode}.json/.md` | Stage-level |

## Stages NOT Covered (7–9)

Stages 7–9 (`extract_data`, `analyze_correlations`, `analyze_descriptions`) are excluded per user requirement ("up to aggregate summaries"). They continue to use boolean config flags only — no TTL caching.

## Metadata Format

`cache/pipeline_metadata.json`:
```json
{
  "airdna": {
    "outputs/01_comp_sets/comp_set_97067.json": "2026-02-25T10:30:00",
    "_completed": "2026-02-25T10:30:05"
  },
  "reviews": {
    "outputs/03_reviews_scraped/reviews_97067_12345.json": "2026-02-25T10:31:00",
    "outputs/03_reviews_scraped/reviews_97067_67890.json": "2026-02-25T10:31:15"
  }
}
```

## Technical Risks

- **Metadata file corruption**: If the process crashes mid-write to `pipeline_metadata.json`, the file could be truncated. Mitigated by atomic write (write to temp file, then rename).
- **Metadata drift**: If output files are manually deleted but metadata still records them as fresh, the pipeline would skip them. Mitigated by checking both metadata freshness AND file existence in `is_file_fresh()`.
- **Large metadata files**: If thousands of listings are scraped, metadata JSON could grow large. Acceptable for now — JSON is O(number of files), not O(file content).
- **Concurrent runs**: No file locking on metadata. Not a current concern (pipeline is single-threaded) but noted for future.
