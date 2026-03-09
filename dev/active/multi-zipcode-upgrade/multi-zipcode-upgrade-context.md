# Multi-Zipcode Pipeline Upgrade — Context

## Key Files

### Entry Points & Config
| File | Role |
|------|------|
| `main.py` | Pipeline orchestrator. `PIPELINE_STEPS` list + `run_tasks_from_config()` loop. `AirBnbReviewAggregator.zipcode` property reads `config.get("zipcode")`. |
| `config.json` | All pipeline config. Already has `zipcodes` list and `dest_lat`/`dest_long`. Individual steps enabled via boolean flags. |
| `utils/tiny_file_handler.py` | `load_config()` reads `config.json` from repo root. |

### Step Modules (all expose `run(config, pipeline_cache)`)
| File | Stage Name | Phase |
|------|------------|-------|
| `steps/01_search_results.py` | `search_results` | Scraping |
| `steps/02_details_scrape.py` | `details_scrape` | Scraping |
| `steps/03_airdna_data.py` | `airdna_data` | Scraping |
| `steps/04_reviews_scrape.py` | `reviews_scrape` | Scraping |
| `steps/06_listing_summaries.py` | `listing_summaries` | Scraping |
| `steps/05_details_results.py` | `details_results` | Processing |
| `steps/07_area_summary.py` | `area_summary` | Processing |
| `steps/08_correlation_results.py` | `correlation_results` | Processing |
| `steps/09_description_analysis.py` | `description_analysis` | Processing |

Every step reads `config.get("zipcode")` to get the current zipcode.

### Cache Manager
| File | Role |
|------|------|
| `utils/pipeline_cache_manager.py` | `STAGE_ORDER`, `CASCADE_TARGET_STAGES`, `STAGE_OUTPUT_DIRS`. Freshness via mtime. Cascade logic auto-refreshes downstream analysis stages. |

### Data File Producers/Consumers for Lat/Lng
| File | Role |
|------|------|
| `scraper/airbnb_searcher.py` | Step 01 output: search results JSON. Contains `coordinates.latitude` and `coordinates.longitud` (misspelled). |
| `scraper/details_scraper.py` | Step 02 output: per-listing detail JSON. Contains `coordinates.latitude` and `coordinates.longitude` (correct). |
| `scraper/details_fileset_build.py` | Step 05: `DetailsFilesetBuilder`. Reads step 02 JSON → builds `property_amenities_matrix_*.csv`. Currently does NOT extract coordinates. |
| `review_aggregator/correlation_analyzer.py` | Step 08: reads `property_amenities_matrix_*.csv`. Has `NUMERIC_COLUMNS` and `AMENITY_COLUMNS` lists. |
| `review_aggregator/description_analyzer.py` | Step 09: reads `property_amenities_matrix_cleaned_*.csv`. |
| `ml/train.py` | ML model: reads cleaned CSV. `NUMERIC_FEATURES` = `["capacity", "bedrooms", "beds", "bathrooms"]`. |

### Tests
| File | Relevance |
|------|-----------|
| `tests/integration/test_pipeline_integration.py` | Pipeline integration tests. New multi-zipcode ordering test goes here. |
| `tests/unit/test_details_fileset_build.py` | Unit tests for `DetailsFilesetBuilder`. Lat/lng extraction test goes here. |
| `tests/unit/test_pipeline_cache_manager.py` | Cache manager tests. May need update if `CASCADE_TARGET_STAGES` changes. |
| `tests/unit/test_pipeline_cache_mtime.py` | Mtime-based cache tests. |

## Key Decisions

1. **Zipcode injection pattern**: `main.py` sets `config["zipcode"]` before calling each step. This avoids changing every step module's `run()` signature. All steps continue using `config.get("zipcode")`.

2. **Two-phase execution**: All zipcodes complete scraping (01–04 + listing_summaries) before any zipcode starts processing (details_results + 07–09). Enables future cross-zipcode data merging.

3. **`listing_summaries` stays in scraping phase**: It generates per-property LLM summaries (uses reviews from step 04). It runs per-zipcode alongside the other scraping steps.

4. **Step renumbering on disk**: File names updated so `listing_summaries` = 05, `details_results` = 06. Reflects new execution order.

5. **Lat/lng source**: Step 02 details scrape JSON (correct `"longitude"` spelling) rather than step 01 search results (`"longitud"` misspelling in pyairbnb output).

6. **Feature engineering deferred**: Stage 5 is a placeholder — full design will happen separately after lat/lng columns exist in the matrix.

## Output Directory Structure (unchanged)
Output directories are keyed by stage name in `STAGE_OUTPUT_DIRS`, not by step number. Renumbering step files does NOT require renaming output directories.

```
outputs/01_search_results/     → search_results_{zipcode}.json
outputs/02_details_scrape/     → property_details_{listing_id}.json
outputs/03_airdna_data/        → listing_{id}.json, comp_set_{zipcode}.json
outputs/04_reviews_scrape/     → reviews_{zipcode}_{listing_id}.json
outputs/05_details_results/    → property_amenities_matrix_{zipcode}.csv (+ cleaned, descriptions, etc.)
outputs/06_listing_summaries/  → listing_summary_{zipcode}_{listing_id}.json
outputs/08_correlation_results/ → correlation_stats_{metric}_{zipcode}.json
outputs/09_description_analysis/ → description_quality_stats_{zipcode}.json
```
