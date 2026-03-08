# Testing Patterns

**Analysis Date:** 2026-03-08

## Test Framework

**Runner:**
- pytest, version pinned via `Pipfile` (`pytest = "*"`, resolved to 9.0.2 per cache)
- Config: `pytest.ini` at repo root

**Plugins:**
- `pytest-cov` — coverage reporting
- `pytest-mock` — `mocker` fixture (available but `unittest.mock` is preferred in practice)
- `freezegun` — time freezing (listed in dev deps; available for time-sensitive tests)

**Run Commands:**
```bash
make test              # Run all tests with coverage (pipenv run pytest)
make test-fast         # Run tests without coverage, fail on first failure (-x --no-cov)
make coverage          # Run with detailed HTML + term-missing report
pipenv run pytest      # Direct invocation; reads pytest.ini automatically
```

## Test File Organization

**Location:**
- All tests under `tests/` directory at repo root
- Unit tests: `tests/unit/test_*.py`
- Integration tests: `tests/integration/test_*.py`
- Shared fixtures: `tests/conftest.py`
- JSON fixtures: `tests/fixtures/sample_data.json`

**Naming:**
- Test files: `test_{source_module_name}.py` mirroring the module under test
  - `utils/pipeline_cache_manager.py` → `tests/unit/test_pipeline_cache_manager.py`
  - `review_aggregator/area_review_aggregator.py` → `tests/unit/test_area_review_aggregator.py`
- Test classes: `Test{ClassName}` or `Test{ClassName}{MethodGroup}` when a class has many methods
- Test functions: `test_{behavior_description}` in plain English (e.g., `test_force_refresh_overrides_file_freshness`)

**Structure:**
```
tests/
├── __init__.py
├── conftest.py                          # Shared fixtures for all tests
├── fixtures/
│   └── sample_data.json                 # JSON fixtures for reviews, config, prompts
├── unit/
│   ├── __init__.py
│   ├── test_area_review_aggregator.py
│   ├── test_airdna_scraper.py
│   ├── test_compile_comp_sets.py
│   ├── test_correlation_analyzer.py
│   ├── test_cost_tracker.py
│   ├── test_description_analyzer.py     # TDD: tests written before implementation
│   ├── test_details_fileset_build.py
│   ├── test_get_area_search_results.py
│   ├── test_local_file_handler.py
│   ├── test_location_calculator.py
│   ├── test_openai_aggregator.py
│   ├── test_pipeline_cache_manager.py
│   ├── test_pipeline_cache_mtime.py
│   ├── test_property_review_aggregator.py
│   ├── test_reviews_scraper.py
│   └── test_tiny_file_handler.py
└── integration/
    ├── __init__.py
    └── test_pipeline_integration.py
```

## Test Structure

**Suite Organization:**
```python
class TestOpenAIAggregator:
    """Tests for OpenAIAggregator class."""

    @pytest.fixture
    def aggregator(self, tmp_logs_dir):
        """Create an OpenAIAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {"openai": {"model": "gpt-4.1-mini", ...}}
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.openai_aggregator import OpenAIAggregator
                agg = OpenAIAggregator()
                agg.cost_tracker.log_file = str(tmp_logs_dir / "cost.json")
                return agg

    def test_estimate_tokens_valid_text(self, aggregator):
        """Test token estimation for valid text."""
        tokens = aggregator.estimate_tokens("This is a sample review text.")
        assert isinstance(tokens, int)
        assert tokens > 0
```

**Patterns:**
- All tests organized into classes (no bare test functions in source files)
- One class per logical grouping; large classes split into multiple (e.g., `TestCostTracker` + `TestCostTrackerSessionSummary`)
- Each test method has a docstring explaining intent
- `tmp_path` built-in fixture used for all filesystem tests — never write to real output dirs

## Mocking

**Framework:** `unittest.mock` (`patch`, `MagicMock`) — used directly, not via `pytest-mock`

**Primary mocking pattern — patch `load_json_file` at import time:**
```python
with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
    mock_load.return_value = {"openai": {"model": "gpt-4.1-mini", ...}}
    with patch("utils.cost_tracker.load_json_file", return_value={}):
        from review_aggregator.openai_aggregator import OpenAIAggregator
        agg = OpenAIAggregator()
```
Note: imports happen inside the `with patch(...)` block so the module sees mocked config at init.

**Mocking OpenAI client:**
```python
mock_client = MagicMock()
mock_response = MagicMock()
mock_response.choices = [MagicMock()]
mock_response.choices[0].message.content = "Generated summary"
mock_client.chat.completions.create.return_value = mock_response
```

**Patching instance methods directly:**
```python
with patch.object(
    aggregator.openai_aggregator.client.chat.completions,
    "create",
    return_value=mock_response,
):
```

**Patching filesystem calls:**
```python
with patch("os.listdir", return_value=["listing_summary_97067_123.json"]):
    with patch("review_aggregator.area_review_aggregator.load_json_file") as mock_load:
        mock_load.side_effect = [first_call_data, second_call_data, ...]
```

**`side_effect` for ordered returns:** Used when a function is called multiple times with different expected returns — pass a list to `side_effect`.

**What to Mock:**
- `load_json_file` wherever it reads `config.json` or prompt files
- `OpenAI` client / `chat.completions.create` for any OpenAI call
- `os.listdir` when testing filesystem-scanning logic
- `pgeocode.Nominatim` for geocoding calls (provided via `mock_pgeocode` shared fixture)
- `tiktoken.encoding_for_model` when testing fallback token estimation paths
- `time.time` / time-related calls via `freezegun` when testing TTL/mtime logic

**What NOT to Mock:**
- `tmp_path` filesystem (use real temp files for file I/O logic)
- Pydantic model initialization logic
- Pure computation methods (token calculation, rating averaging)

## Shared Fixtures (conftest.py)

All fixtures live in `tests/conftest.py` and are available to all test files.

**Key fixtures:**

| Fixture | Scope | Purpose |
|---|---|---|
| `sample_data` | function | Loads `tests/fixtures/sample_data.json` |
| `sample_reviews` | function | `sample_data["sample_reviews"]` |
| `sample_config` | function | `sample_data["sample_config"]` |
| `sample_listing_id` | function | `sample_data["sample_listing_id"]` |
| `sample_prompt` | function | `sample_data["sample_prompt"]` |
| `sample_openai_response` | function | `sample_data["sample_openai_response"]` |
| `tmp_logs_dir` | function | `tmp_path / "logs"` directory |
| `mock_config` | function | Creates `config.json` in tmp_path |
| `mock_openai_client` | function | Fully wired `MagicMock` OpenAI client |
| `mock_pgeocode` | function | Context-manager patch of pgeocode module |
| `review_strings` | function | List of `"rating text"` strings for aggregator |
| `empty_reviews` | function | `[]` for edge case testing |
| `single_review` | function | `[{"rating": 5, "review": "..."}]` |
| `isolate_tests` | function, **autouse=True** | Writes a minimal `config.json` to `tmp_path` to prevent production config bleed |
| `sample_property_summary` | function | Long markdown summary string for integration tests |
| `mock_summary_files_dir` | function | Creates temp dir with 3 summary JSON files |
| `mock_review_files_dir` | function | Creates temp dir with 3 review JSON files |
| `mocked_openai_aggregator` | function | Fully constructed `OpenAIAggregator` with mock client |

**`isolate_tests` autouse fixture** — critical for all tests:
```python
@pytest.fixture(autouse=True)
def isolate_tests(tmp_path, monkeypatch):
    """Isolate tests from production config files."""
    empty_config = {
        "openai": {"enable_caching": False, "enable_cost_tracking": False},
        "pipeline_cache_enabled": False,
        "pipeline_cache_ttl_days": 7,
    }
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(empty_config, f)
```
This runs automatically for every test. However, `load_json_file` still reads from cwd, so tests that construct classes with config loading still need to `patch("module.load_json_file")` explicitly.

## Fixtures and Factories

**Test data location:** `tests/fixtures/sample_data.json`

**In-test data creation:**
```python
# Create real files in tmp_path for filesystem tests
search_dir = tmp_path / "outputs" / "01_search_results"
search_dir.mkdir(parents=True)
search_results = [{"room_id": "111"}, {"room_id": "222"}]
with open(str(search_dir / "search_results_97067.json"), "w") as f:
    json.dump(search_results, f)
```

**Inline fixture data:**
```python
@pytest.fixture
def review_strings():
    return [
        "5 Amazing place! Very clean and great location.",
        "4 Good stay overall. Host was responsive.",
    ]
```

## Coverage

**Requirements:** 75% minimum enforced (`--cov-fail-under=75` in `pytest.ini`)

**Measured modules** (from `pytest.ini`):
- `utils.tiny_file_handler`
- `utils.cost_tracker`
- `utils.pipeline_cache_manager`
- `utils.local_file_handler`
- `scraper.location_calculator`
- `review_aggregator.openai_aggregator`
- `review_aggregator.property_review_aggregator`
- `review_aggregator.area_review_aggregator`

Note: `steps/` modules and `scraper/` scraping modules (Playwright-dependent) are NOT in coverage config.

**View Coverage:**
```bash
make coverage                       # Generates term-missing + HTML report
open coverage_html/index.html       # View HTML report in browser
```

## Test Types

**Unit Tests (`tests/unit/`):**
- Test a single class or function in isolation
- All external I/O (files, APIs, geocoding) is mocked
- No network calls, no disk writes outside `tmp_path`
- Test both happy path and edge cases (empty inputs, missing files, API failures)

**Integration Tests (`tests/integration/test_pipeline_integration.py`):**
- Test cross-component flows (aggregator → cost tracker, area aggregator → file output)
- External services still mocked (OpenAI, file loading)
- Real filesystem writes to `tmp_path` to verify output file creation and content

**E2E Tests:**
- Not present; scraper tests for Playwright-based scrapers (`test_airdna_scraper.py`, `test_reviews_scraper.py`) mock Playwright and HTTP calls

## Common Patterns

**Async Testing:**
- Not applicable; codebase is synchronous Python

**Error/Exception Testing:**
```python
with pytest.raises(json.JSONDecodeError):
    load_json_file(str(empty_file))
```

**Testing None return on failure:**
```python
result = aggregator.generate_summary([], "prompt", "listing123")
assert result is None
```

**Testing retry logic:**
```python
mock_client.chat.completions.create.side_effect = [
    Exception("API Error"),
    Exception("API Error"),
    MagicMock(choices=[MagicMock(message=MagicMock(content="Success"))]),
]
aggregator.retry_delay = 0.01  # Speed up test
result = aggregator.call_openai_with_retry("Test prompt", "listing123")
assert result == "Success"
assert mock_client.chat.completions.create.call_count == 3
```

**Testing filesystem side effects:**
```python
handler.clear_directory(str(target_dir))
assert target_dir.exists()
assert list(target_dir.iterdir()) == []
```

**Testing ordered mock calls with side_effect list:**
```python
mock_load.side_effect = [
    {"listing_a": "Summary A"},   # first call
    {"listing_b": "Summary B"},   # second call
    {"gpt4o_mini_generate_prompt_structured": "Prompt"},  # third call
    {"iso_code": "us"},           # fourth call
]
```

**TDD pattern** (observed in `tests/unit/test_description_analyzer.py`):
- Test file docstring notes "TDD: These tests are written BEFORE the implementation"
- Tests import from modules that may not yet exist; they should fail (red) until the module is created

---

*Testing analysis: 2026-03-08*
