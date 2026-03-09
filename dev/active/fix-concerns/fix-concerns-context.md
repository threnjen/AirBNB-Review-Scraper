# Fix CONCERNS.md Issues — Context

## Project Overview

A 9-stage sequential ETL pipeline that scrapes Airbnb/AirDNA listing data, processes reviews with OpenAI, and generates analysis reports. Orchestrated by `main.py` → `AirBnbReviewAggregator`, each stage is a module in `steps/` with a `run(config, pipeline_cache)` entry point. Stages communicate via filesystem outputs in `outputs/01_*` through `outputs/09_*`. Cache decisions handled by `PipelineCacheManager` (TTL-based, per-stage skip/resume/clear). LLM work is isolated to stages 06–09 via `OpenAIAggregator`.

## Key Files Affected

### Scraper Layer
| File | Concerns | Steps |
|------|----------|-------|
| `scraper/details_fileset_build.py` | `sub_details` index crash, `bathrooms` unbound | 1.1, 1.2 |
| `scraper/location_calculator.py` | Returns `None` on error → caller crash | 1.4 |
| `scraper/airbnb_searcher.py` | Unpacks `None` from `locationer`; hardcoded grid dimensions | 1.4, 5.3 |
| `scraper/reviews_scraper.py` | `pipeline_cache` unused; counter reset on retry | 1.5, 4.1 |
| `scraper/airdna_scraper.py` | `LY_Revenue` stub; hardcoded sleep; double page text fetch | 4.3, 5.1, 5.2 |

### Aggregator Layer
| File | Concerns | Steps |
|------|----------|-------|
| `review_aggregator/property_review_aggregator.py` | Divide-by-zero; `"?"` heuristic; per-listing config/prompt I/O | 1.3, 3.2, 4.4, 4.5 |
| `review_aggregator/area_review_aggregator.py` | Missing dir guard; per-listing config I/O | 3.1, 4.4 |
| `review_aggregator/openai_aggregator.py` | Broad `except Exception: pass` | 2.1 |

### Utilities
| File | Concerns | Steps |
|------|----------|-------|
| `utils/pipeline_cache_manager.py` | `ClassVar` needed; `clear_stage` deprecated; `get_cache_stats` stub | 3.3, 3.4, 3.5 |
| `utils/cost_tracker.py` | Broad `except Exception: pass` | 2.2 |

### Orchestrator
| File | Concerns | Steps |
|------|----------|-------|
| `main.py` | Duplicated `compile_airdna_data` | 4.2 |

### Tests
| File | Covers Steps |
|------|-------------|
| `tests/unit/test_details_fileset_build.py` | 1.1, 1.2 |
| `tests/unit/test_property_review_aggregator.py` | 1.3, 3.2 |
| `tests/unit/test_location_calculator.py` | 1.4 |
| `tests/unit/test_reviews_scraper.py` | 1.5, 4.1 |
| `tests/unit/test_openai_aggregator.py` | 2.1 |
| `tests/unit/test_cost_tracker.py` | 2.2 |
| `tests/unit/test_area_review_aggregator.py` | 3.1 |
| `tests/unit/test_pipeline_cache_manager.py` | 3.3, 3.4, 3.5 |
| `tests/unit/test_compile_airdna_data.py` | 4.2 |

## Existing Patterns to Follow

### Cache freshness check (`scraper/details_scraper.py` lines 28–33)
```python
if pipeline_cache and pipeline_cache.is_file_fresh("details_scrape", output_path):
    logger.info(f"Skipping listing {room_id} — cached details are fresh.")
    properties_scraped += 1
    continue
```
Replicate this in `reviews_scraper.py` (Step 4.1).

### Specific exception handling (`utils/pipeline_cache_manager.py` line 93)
```python
except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
    logger.warning(f"Could not load config overrides: {e}")
```
Replicate this in `openai_aggregator.py` and `cost_tracker.py` (Steps 2.1, 2.2).

### Directory existence guard (`scraper/details_fileset_build.py` lines 194–199)
Check `os.path.isdir(...)` before calling `os.listdir(...)`. Replicate in `area_review_aggregator.py` (Step 3.1).

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Raise `ValueError` from `locationer` (not sentinel tuple) | AGENTS.md: "fail fast with descriptive errors" |
| Path anchoring only for config.json (not full DI) | Scope boundary — full DI is a separate architectural task |
| Remove `get_cache_stats` if no callers exist | Dead code removal preferred over maintaining stubs |
| Document `LY_Revenue` rather than remove | Avoids breaking downstream consumers |
| Defer per-listing streaming (Step 5.4) | Highest risk, lowest urgency |
| Refactor `sub_details` parsing to substring search | More resilient than positional indexing against Airbnb API changes |

## Dependencies Between Steps

- Steps 1.1 and 1.2 should be done together (same function, same refactor)
- Step 4.2 (remove dup `compile_airdna_data`) requires updating test import first
- Step 2.3 (config path anchoring) is cross-cutting; all other steps should land first
- Step 3.2 requires reading `prompts/prompt.json` to determine structural markers
- Steps 4.4 and 4.5 touch the same file; combine into one commit

## Environment

- Python via **pipenv**: `pipenv run pytest`, `pipenv run python -m py_compile <file>`
- Test framework: pytest with fixtures in `tests/fixtures/`
- Config: `config.json` at repo root
- Prompts: `prompts/*.json`
