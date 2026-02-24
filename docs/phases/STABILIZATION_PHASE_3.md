# Phase 3: Integration Tests and QA

**Status:** Planned  
**Dependencies:** Phase 2 (AreaRagAggregator Rewrite)  
**Deliverables:** Integration test suite, QA validation completed

---

## Overview

Add integration tests to validate the full pipeline and create QA documentation for manual verification. Focus on integration tests (not unit tests) per project requirements.

---

## Task 1: Create Test Directory Structure

### Commands to Run

```bash
mkdir -p tests
touch tests/__init__.py
```

---

## Task 2: Create Integration Test File

### File to Create

`tests/test_pipeline_integration.py`

### File Contents

```python
#!/usr/bin/env python3
"""
Integration tests for the AirBNB Review Scraper pipeline.
Tests the full flow from data loading to summary generation.
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from review_aggregator.property_review_aggregator import PropertyRagAggregator
from review_aggregator.area_review_aggregator import AreaRagAggregator
from review_aggregator.openai_aggregator import OpenAIAggregator
from utils.cache_manager import CacheManager
from utils.cost_tracker import CostTracker
from utils.local_file_handler import LocalFileHandler

import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


class TestOpenAIAggregatorIntegration:
    """Test OpenAI aggregator components work together."""

    def test_aggregator_initializes(self):
        """Test that OpenAIAggregator initializes without errors."""
        aggregator = OpenAIAggregator()
        assert aggregator.model is not None
        assert aggregator.cache_manager is not None
        assert aggregator.cost_tracker is not None
        logger.info("✓ OpenAIAggregator initializes correctly")

    def test_token_estimation(self):
        """Test token estimation produces reasonable values."""
        aggregator = OpenAIAggregator()
        sample_text = "This is a test review for token estimation."
        tokens = aggregator.estimate_tokens(sample_text)
        assert tokens > 0
        assert tokens < 100  # Simple sentence should be under 100 tokens
        logger.info(f"✓ Token estimation: {tokens} tokens for sample text")

    def test_cache_manager_operations(self):
        """Test cache manager can store and retrieve values."""
        cache_manager = CacheManager()
        
        # Skip if caching disabled
        stats = cache_manager.get_cache_stats()
        if not stats.get("enabled"):
            logger.info("⊘ Cache disabled, skipping cache test")
            return
        
        test_key = "test_integration_key"
        test_value = "test_integration_value"
        
        cache_manager.set(test_key, test_value)
        retrieved = cache_manager.get(test_key)
        
        assert retrieved == test_value
        logger.info("✓ Cache manager stores and retrieves values")


class TestLocalFileHandler:
    """Test file handler operations."""

    def test_save_json_creates_directory(self):
        """Test that save_json creates parent directories."""
        handler = LocalFileHandler()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = os.path.join(tmpdir, "nested", "dir", "test.json")
            test_data = {"key": "value"}
            
            handler.save_json(nested_path, test_data)
            
            assert os.path.exists(nested_path)
            with open(nested_path, "r") as f:
                loaded = json.load(f)
            assert loaded == test_data
            
        logger.info("✓ save_json creates nested directories")

    def test_load_json(self):
        """Test JSON loading."""
        handler = LocalFileHandler()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, "test.json")
            test_data = {"reviews": ["good", "bad"]}
            
            with open(test_path, "w") as f:
                json.dump(test_data, f)
            
            loaded = handler.load_json(test_path)
            assert loaded == test_data
            
        logger.info("✓ load_json reads files correctly")


class TestPropertyRagAggregator:
    """Test property-level aggregator initialization."""

    def test_aggregator_initializes(self):
        """Test PropertyRagAggregator initializes with required parameters."""
        aggregator = PropertyRagAggregator(
            num_listings_to_summarize=3,
            review_thresh_to_include_prop=5,
            zipcode="97067"
        )
        
        assert aggregator.zipcode == "97067"
        assert aggregator.num_listings_to_summarize == 3
        assert aggregator.openai_aggregator is not None
        logger.info("✓ PropertyRagAggregator initializes correctly")

    def test_mean_rating_calculation(self):
        """Test mean rating calculation logic."""
        aggregator = PropertyRagAggregator(
            num_listings_to_summarize=3,
            review_thresh_to_include_prop=5,
            zipcode="97067"
        )
        
        sample_reviews = [
            {"rating": 5, "review": "Great!"},
            {"rating": 4, "review": "Good"},
            {"rating": 3, "review": "Okay"},
        ]
        
        mean = aggregator.get_listing_id_mean_rating(sample_reviews)
        expected = round((5 + 4 + 3) / 3, 4)
        assert mean == expected
        logger.info(f"✓ Mean rating calculation: {mean}")


class TestAreaRagAggregator:
    """Test area-level aggregator initialization."""

    def test_aggregator_initializes(self):
        """Test AreaRagAggregator initializes with required parameters."""
        aggregator = AreaRagAggregator(
            num_listings=5,
            review_thresh_to_include_prop=5,
            zipcode="97067"
        )
        
        assert aggregator.zipcode == "97067"
        assert aggregator.num_listings == 5
        assert aggregator.openai_aggregator is not None
        logger.info("✓ AreaRagAggregator initializes correctly")


def run_all_tests():
    """Run all integration tests."""
    logger.info("\n" + "=" * 60)
    logger.info("INTEGRATION TESTS")
    logger.info("=" * 60 + "\n")
    
    test_classes = [
        TestOpenAIAggregatorIntegration,
        TestLocalFileHandler,
        TestPropertyRagAggregator,
        TestAreaRagAggregator,
    ]
    
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        logger.info(f"\n--- {test_class.__name__} ---")
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    getattr(instance, method_name)()
                    passed += 1
                except AssertionError as e:
                    logger.error(f"✗ {method_name}: {e}")
                    failed += 1
                except Exception as e:
                    logger.error(f"✗ {method_name}: {type(e).__name__}: {e}")
                    failed += 1
    
    logger.info("\n" + "=" * 60)
    logger.info(f"RESULTS: {passed} passed, {failed} failed")
    logger.info("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
```

---

## Task 3: Add pytest Configuration

### File to Create

`pytest.ini`

### File Contents

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
python_classes = Test*
addopts = -v --tb=short
log_cli = true
log_cli_level = INFO
```

---

## Task 4: Update Pipfile for pytest

### File to Edit

`Pipfile`

### Add to [dev-packages] section

```toml
[dev-packages]
pytest = "*"
```

### After editing, run

```bash
pipenv install --dev
```

---

## QA Test Plan

### Pre-Conditions

1. Python environment set up with all dependencies
2. `OPENAI_API_KEY` environment variable set
3. At least 5 property review files in `property_reviews_scraped/`
4. Cache directory exists: `cache/summaries/`

### Test Case 1: Property Summary Generation

**Objective:** Verify PropertyRagAggregator generates summaries from reviews

**Steps:**
1. Set `config.json`:
   ```json
   {
     "scrape_reviews": false,
     "scrape_details": false,
     "build_details": false,
     "aggregate_reviews": true,
     "aggregate_summaries": false,
     "num_listings_to_summarize": 2,
     "zipcode": "97067"
   }
   ```
2. Run: `python main.py`
3. Check logs for "Processing listing" messages
4. Verify new files created in `property_generated_summaries/`

**Expected Result:**
- Pipeline completes without errors
- 2 new summary files created (or uses cached if already exist)
- Each file contains JSON with `{listing_id: summary_text}` structure

**Pass Criteria:** ☐ Pass ☐ Fail

---

### Test Case 2: Area Summary Generation

**Objective:** Verify AreaRagAggregator generates area summary from property summaries

**Pre-Condition:** At least 3 property summaries exist in `property_generated_summaries/`

**Steps:**
1. Set `config.json`:
   ```json
   {
     "scrape_reviews": false,
     "scrape_details": false,
     "build_details": false,
     "aggregate_reviews": false,
     "aggregate_summaries": true,
     "num_summary_to_process": 5,
     "zipcode": "97067"
   }
   ```
2. Run: `python main.py`
3. Check logs for "Found X property summaries" message
4. Verify `generated_summaries_97067.json` created in root directory

**Expected Result:**
- Pipeline completes without errors
- Area summary file created with structure:
  ```json
  {
    "zipcode": "97067",
    "num_properties_analyzed": 5,
    "area_summary": "..."
  }
  ```
- Summary contains area-level insights about common themes

**Pass Criteria:** ☐ Pass ☐ Fail

---

### Test Case 3: Cache Functionality

**Objective:** Verify caching prevents redundant API calls

**Steps:**
1. Run property aggregation once (Test Case 1)
2. Note the cost summary logged
3. Run same aggregation again
4. Compare cost summary

**Expected Result:**
- Second run shows cached responses used
- Cost is lower (or zero) for cached content
- Log shows "Cache Statistics: X valid"

**Pass Criteria:** ☐ Pass ☐ Fail

---

### Test Case 4: Error Handling - Missing Files

**Objective:** Verify graceful handling when no property summaries exist

**Steps:**
1. Create empty temp directory (or use new zipcode with no data)
2. Set `config.json` to `aggregate_summaries: true` with unused zipcode
3. Run: `python main.py`

**Expected Result:**
- Pipeline logs "No property summaries found for zipcode..."
- Exits gracefully without crash
- No empty output file created

**Pass Criteria:** ☐ Pass ☐ Fail

---

### Test Case 5: Integration Test Suite

**Objective:** Verify all integration tests pass

**Steps:**
1. Run: `python tests/test_pipeline_integration.py`
2. Or with pytest: `pytest tests/ -v`

**Expected Result:**
- All tests pass
- Output shows "RESULTS: X passed, 0 failed"

**Pass Criteria:** ☐ Pass ☐ Fail

---

## Success Criteria

1. [ ] `tests/test_pipeline_integration.py` created with all test classes
2. [ ] `pytest.ini` configured
3. [ ] All integration tests pass: `python tests/test_pipeline_integration.py`
4. [ ] QA Test Cases 1-5 all pass
5. [ ] No regressions in existing functionality

---

## Commit Message

```
test: add integration tests and QA validation

- Create tests/test_pipeline_integration.py with component tests
- Add pytest.ini configuration
- Test OpenAI aggregator, cache manager, file handler
- Test PropertyRagAggregator and AreaRagAggregator initialization
- Verify Phase 1-2 bug fixes work correctly
```
