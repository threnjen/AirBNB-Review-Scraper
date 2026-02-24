# Stabilization Refactor - Phases Overview

## Project Context

This refactor stabilizes the AirBNB Review Scraper pipeline. The goal is to fix bugs, complete the broken `AreaRagAggregator`, add data extraction/aggregation for area-level insights, and add integration tests. Weaviate code remains dormant but preserved for future RAG expansion.

## Phase Summary Table

| Phase | Name | Status | Dependencies | Deliverables |
|-------|------|--------|--------------|--------------|
| 1 | Bug Fixes | Planned | None | Fixed `save_json`, cleaned dead imports |
| 2 | AreaRagAggregator Rewrite | Planned | Phase 1 | Working area-level summary generation |
| 3 | Data Extraction & Aggregation | Planned | Phase 2 | Structured JSON with area pros/cons weighted by reviews |
| 4 | Integration Tests + QA | Planned | Phase 3 | Test suite, QA validation |

## Phase Dependencies

```
Phase 1 (Bug Fixes)
    ↓
Phase 2 (AreaRagAggregator)
    ↓
Phase 3 (Data Extraction)
    ↓
Phase 4 (Tests + QA)
```

## Success Criteria (Overall)

1. `python main.py` with `aggregate_reviews: true` completes without errors
2. `python main.py` with `aggregate_summaries: true` generates area-level JSON output
3. `python main.py` with `extract_data: true` generates `area_data_{zipcode}.json`
4. Integration tests pass: `pytest tests/`
5. No new linting errors introduced

## Key Files Reference

| File | Purpose |
|------|---------|
| `main.py` | Entry point - orchestrates pipeline via `AirBnbReviewAggregator` |
| `review_aggregator/property_review_aggregator.py` | Per-property OpenAI summarization (working) |
| `review_aggregator/area_review_aggregator.py` | Area-level summarization (broken - Phase 2 target) |
| `review_aggregator/data_extractor.py` | Data extraction & aggregation (NEW - Phase 3) |
| `review_aggregator/openai_aggregator.py` | OpenAI client with chunking/caching |
| `utils/local_file_handler.py` | File I/O utilities (has bug - Phase 1 target) |
| `utils/tiny_file_handler.py` | Simple JSON load/save helpers |
| `config.json` | Pipeline configuration toggles |
| `prompts/prompt.json` | Property-level LLM prompt template |
| `prompts/zipcode_prompt.json` | Area-level LLM prompt template |

## Directory Structure

```
property_reviews_scraped/      # Raw review JSON per listing
property_details_scraped/      # Raw property details per listing
property_generated_summaries/  # Per-property AI summaries (output of PropertyRagAggregator)
property_search_results/       # Search results by zipcode
prompts/                       # LLM prompt templates
```

## Status Legend

- **Planned** - Not yet started
- **In Progress** - Currently being worked on
- **Complete** - Finished and verified
- **Deferred** - Postponed to future work
