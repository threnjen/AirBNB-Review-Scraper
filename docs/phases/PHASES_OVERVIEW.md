# Stabilization Refactor - Phases Overview

## Project Context

This refactor stabilizes the AirBNB Review Scraper pipeline. The goal is to fix bugs, complete the broken `AreaRagAggregator`, and add integration tests. Weaviate code remains dormant but preserved for future RAG expansion.

## Phase Summary Table

| Phase | Name | Status | Dependencies | Deliverables |
|-------|------|--------|--------------|--------------|
| 1 | Bug Fixes | Planned | None | Fixed `save_json`, cleaned dead imports |
| 2 | AreaRagAggregator Rewrite | Planned | Phase 1 | Working area-level summary generation |
| 3 | Integration Tests + QA | Planned | Phase 2 | Test suite, QA validation |

## Phase Dependencies

```
Phase 1 (Bug Fixes)
    ↓
Phase 2 (AreaRagAggregator)
    ↓
Phase 3 (Tests + QA)
```

## Success Criteria (Overall)

1. `python main.py` with `aggregate_reviews: true` completes without errors
2. `python main.py` with `aggregate_summaries: true` generates area-level JSON output
3. Integration tests pass: `pytest tests/`
4. No new linting errors introduced

## Key Files Reference

| File | Purpose |
|------|---------|
| `main.py` | Entry point - orchestrates pipeline via `AirBnbReviewAggregator` |
| `review_aggregator/property_review_aggregator.py` | Per-property OpenAI summarization (working) |
| `review_aggregator/area_review_aggregator.py` | Area-level summarization (broken - Phase 2 target) |
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
