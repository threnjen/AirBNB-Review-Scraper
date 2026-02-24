# Phase 3: DataExtractor Context

## Key Files
- `review_aggregator/data_extractor.py` — NEW: Main class to create
- `tests/unit/test_data_extractor.py` — NEW: Test file
- `main.py` — Integration point (lines 10, 33, 57, 140+)
- `config.json` — Add `extract_data` flag
- `review_aggregator/openai_aggregator.py` — Pattern reference
- `property_generated_summaries/` — Input data source

## Input Format
Files: `property_generated_summaries/generated_summaries_{zipcode}_{listing_id}.json`
Structure: `{"listing_id": "summary text with 'Mentions: X of Y Reviews' patterns"}`

## Output Format
File: `area_data_{zipcode}.json`
Structure: See STABILIZATION_PHASE_3.md Output Structure section

## Decisions
- Load individual files from `property_generated_summaries/` (not root combined file)
- Use `OpenAIAggregator.generate_summary()` for LLM calls
- Save output to project root
