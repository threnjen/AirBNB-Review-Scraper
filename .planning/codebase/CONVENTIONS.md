# Coding Conventions

**Analysis Date:** 2026-03-08

## Naming Patterns

**Files:**
- Source modules: `snake_case.py` (e.g., `pipeline_cache_manager.py`, `area_review_aggregator.py`)
- Step modules: numbered prefix + underscore + description (e.g., `01_search_results.py`, `06_listing_summaries.py`)
- Test files: `test_` prefix mirroring source name (e.g., `test_pipeline_cache_manager.py`)
- Output files at runtime: `{type}_{zipcode}_{listing_id}.json` (e.g., `reviews_97067_12345.json`)

**Classes:**
- PascalCase (e.g., `PipelineCacheManager`, `OpenAIAggregator`, `AreaAggregator`, `CostTracker`)
- Test classes use `Test` prefix (e.g., `TestPipelineCacheManager`, `TestCostTracker`)

**Functions/Methods:**
- `snake_case` throughout (e.g., `get_listing_id_mean_rating`, `task_chain`)
- Private helpers prefixed with single underscore (e.g., `_is_file_fresh_by_mtime`, `_get_listing_ids_for_zipcode`, `_apply_init_cascade`)

**Variables:**
- `snake_case` for all local variables
- SCREAMING_SNAKE_CASE for module-level constants (e.g., `PIPELINE_STEPS`, `STAGE`, `TESTS_DIR`, `FIXTURES_DIR`)
- Class-level constants are uppercase Pydantic fields (e.g., `STAGE_ORDER`, `STAGE_OUTPUT_DIRS`, `CASCADE_TARGET_STAGES`)

**Type Annotations:**
- Used consistently in method signatures with modern union syntax where appropriate (e.g., `str | None`)
- `typing` module imports used for `List`, `Optional`, `Dict`, `Any` in older-style annotations; newer files use built-in generics
- Return types annotated on all significant methods

## Code Style

**Formatting:**
- `black` (listed as dev dependency in `Pipfile`)
- `ruff` for linting (`.ruff_cache/` present, version 0.15.2)

**Linting:**
- `ruff` is configured and active (cache evidence of version 0.15.2)
- No explicit `ruff.toml` or `pyproject.toml` found; ruff uses defaults

**Line Length:**
- Standard Black default (88 characters), inferred from Black usage

## Import Organization

**Order observed across source files:**
1. Standard library (`glob`, `json`, `logging`, `os`, `sys`, `time`, `pathlib`, `typing`, `datetime`, `shutil`)
2. Third-party packages (`pandas`, `pydantic`, `openai`, `tiktoken`, `pgeocode`)
3. Internal project imports (`from utils.x import ...`, `from review_aggregator.x import ...`, `from scraper.x import ...`)

**Style:**
- No `__future__` imports observed
- Relative imports not used; all project imports are absolute
- No barrel (`__init__.py`) re-exports beyond empty `__init__.py` files

## Class Design

**Pydantic BaseModel pattern:**
All stateful classes inherit from `pydantic.BaseModel`:
```python
class OpenAIAggregator(BaseModel):
    client: OpenAI = Field(default_factory=lambda: OpenAI())
    model: str = "gpt-4.1-mini"
    cost_tracker: CostTracker = Field(default_factory=CostTracker)
    class Config:
        arbitrary_types_allowed = True
```
- Configuration loading from `config.json` happens in `__init__` via `super().__init__(**kwargs)` followed by `load_json_file("config.json")`
- Config loading is wrapped in `try/except` to fall back to field defaults silently

**Non-Pydantic classes:**
- Simple utility classes (`LocalFileHandler`) use plain `class` with no base
- Module-level functions (`locationer`, `load_json_file`, `save_json_file`) used for stateless utilities

## Error Handling

**Patterns:**
- External calls (API, file I/O, config loading) are wrapped in broad `try/except Exception` blocks at class init, logging and silently continuing with defaults:
  ```python
  try:
      config = load_json_file("config.json")
      self.enable_cache = config.get("pipeline_cache_enabled", ...)
  except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
      logger.warning(f"Failed to load pipeline cache config, using defaults: {e}")
  ```
- Specific exceptions are caught where the failure type matters (e.g., `PipelineCacheManager.__init__` catches a typed tuple)
- OpenAI retry logic uses broad `except Exception` and logs attempts:
  ```python
  except Exception as e:
      logger.info(f"OpenAI API error for listing {listing_id} (attempt {attempt + 1}): {str(e)}")
  ```
- Functions that cannot proceed return `None` (e.g., `call_openai_with_retry`, `locationer`, pipeline generators)
- Guard clauses used for early exit: `if not reviews: return None`

## Logging

**Framework:** Python `logging` module, configured at module level

**Setup pattern used in every module:**
```python
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)
```

**When/how to log:**
- `logger.info()` for operational progress: inputs loaded, items processed, outputs saved
- `logger.warning()` for recoverable issues: missing files, config not found
- `logger.error()` for unexpected failures in scraper/network calls
- `logger.info()` also used in some places where `logger.error()` would be more appropriate (e.g., `cost_tracker.log_session` error path)
- f-strings used throughout for log message formatting

## Comments

**Style observed:**
- Docstrings on all classes and significant methods using Google/NumPy-style (Args/Returns sections)
- Inline comments used sparingly for non-obvious logic (e.g., cascade logic, token chunking decisions)
- Commented-out code present in some files (e.g., `location_calculator.py` has two commented `logger.info` lines; `property_review_aggregator.py` has commented preprocessing lines) — treat as documentation of removed behavior, not dead code to preserve
- Module-level docstrings present on test files

**Docstring example:**
```python
def expected_outputs(self, stage_name: str, zipcode: str) -> list[str]:
    """Return the list of file paths a stage should produce for *zipcode*.

    Args:
        stage_name: Pipeline stage identifier.
        zipcode: Active zipcode.

    Returns:
        List of expected output file paths. Empty if the stage is unknown
        or prerequisite data (e.g. search results) is missing.
    """
```

## Function Design

**Size:** Methods tend toward single responsibility; complex orchestration (`task_chain`) is allowed to be long when it represents a linear pipeline

**Parameters:** Keyword arguments used at call sites for clarity when multiple args of same type are passed

**Return Values:**
- `None` returned on failure or empty-input guard conditions
- Explicit `Optional[str]` / `str | None` annotations on methods that may return None
- Methods that only perform side effects return `None` implicitly or `bool` for success/failure (e.g., `log_session` returns `bool`)

## Module Design

**Step modules pattern** (`steps/XX_name.py`):
Each step exposes a single public `run(config: dict, pipeline_cache: PipelineCacheManager) -> None` function and a module-level `STAGE` constant:
```python
STAGE = "listing_summaries"

def run(config: dict, pipeline_cache: PipelineCacheManager) -> None:
    action = pipeline_cache.should_run_stage(STAGE, zipcode)
    if action == "skip":
        return
    if action == "clear_and_run":
        pipeline_cache.clear_stage_for_zipcode(STAGE, zipcode)
    # ... do work ...
    pipeline_cache.notify_stage_ran(STAGE)
```

**Exports:**
- No `__all__` declarations observed
- Public API is implicit (everything not prefixed with `_`)

---

*Convention analysis: 2026-03-08*
