# Phase 3: DataExtractor Tasks

## Stage 1: Test Setup
- [ ] Create `tests/unit/test_data_extractor.py`
- [ ] Write `test_load_property_summaries_empty_dir`
- [ ] Write `test_load_property_summaries_with_files`
- [ ] Write `test_extract_data_from_summary_basic`
- [ ] Write `test_aggregate_extractions_positive`
- [ ] Write `test_aggregate_extractions_percentage`
- [ ] Write `test_run_extraction_no_summaries`
- [ ] Verify tests fail (ImportError expected)

## Stage 2: Core Implementation
- [ ] Create `review_aggregator/data_extractor.py`
- [ ] Implement `POSITIVE_CATEGORIES` constant
- [ ] Implement `NEGATIVE_CATEGORIES` constant
- [ ] Implement `DataExtractor` class with Pydantic
- [ ] Implement `load_property_summaries()`
- [ ] Implement `extract_data_from_summary()`
- [ ] Implement `aggregate_extractions()`
- [ ] Implement `run_extraction()`
- [ ] Verify syntax: `pipenv run python -m py_compile`
- [ ] Verify tests pass

## Stage 3: Integration
- [ ] Add import to `main.py`
- [ ] Add `self.extract_data` in `__init__`
- [ ] Add config loading in `load_configs()`
- [ ] Add pipeline step in `run_tasks_from_config()`
- [ ] Add `extract_data` to `config.json`
- [ ] Run full test suite

## Stage 4: Manual Verification
- [ ] Set `extract_data: true` in config
- [ ] Run `pipenv run python main.py`
- [ ] Verify `area_data_97067.json` created
- [ ] Verify JSON structure matches spec
