# Technology Stack

**Analysis Date:** 2026-03-08

## Languages

**Primary:**
- Python 3.13 - All application code, scraping, data processing, and AI aggregation

**Secondary:**
- JSON - Configuration (`config.json`), all pipeline data interchange and outputs
- Markdown - Generated reports (`reports/*.md`)

## Runtime

**Environment:**
- CPython 3.13

**Package Manager:**
- pipenv
- Lockfile: `Pipfile.lock` (present, fully pinned)

## Frameworks

**Core:**
- pydantic 2.12.5 - Data validation and settings; used as base class for nearly all domain objects (`OpenAIAggregator`, `CostTracker`, `PipelineCacheManager`)

**Testing:**
- pytest 9.0.2 - Test runner (via pipenv dev deps)
- pytest-cov - Coverage reporting (minimum 75% enforced via `pytest.ini`)
- pytest-mock - Mocking support
- freezegun - Time-freezing for cache TTL tests

**Build/Dev:**
- black - Code formatter (enforced in CI via `.github/workflows/black-check.yml`)
- ruff 0.15.2 - Linter (cache at `.ruff_cache/`)
- ipykernel - Jupyter notebook support for `eda_property_details.ipynb` and `model_notebook.ipynb`

## Key Dependencies

**Critical:**
- openai 2.24.0 - GPT-4.1-mini API client; used by `review_aggregator/openai_aggregator.py` for review summarization and area report generation
- pyairbnb 2.2.1 - Unofficial Airbnb client; used in `scraper/airbnb_searcher.py` (search), `scraper/details_scraper.py` (property details), `scraper/reviews_scraper.py` (reviews)
- playwright 1.58.0 - Browser automation for AirDNA scraping; used in `scraper/airdna_scraper.py` via CDP remote debugging
- tiktoken 0.12.0 - Token counting for OpenAI requests; used by `review_aggregator/openai_aggregator.py` and `utils/cost_tracker.py`

**Infrastructure:**
- pandas 3.0.1 - Data processing in `steps/06_details_results.py` and analysis steps
- numpy 2.4.2 - Numerical operations
- pgeocode 0.5.0 - Postal code to lat/lon lookup; used in `scraper/location_calculator.py` to compute bounding boxes for Airbnb search
- pydantic 2.12.5 - Validation/modeling for `CostTracker`, `OpenAIAggregator`, `PipelineCacheManager`
- beautifulsoup4 4.14.3 - HTML parsing (transitive dep via pyairbnb)
- curl-cffi 0.14.0 - HTTP client with TLS fingerprinting (transitive dep via pyairbnb for anti-scraping bypass)

## Configuration

**Environment:**
- Single `.env` file at project root containing `OPENAI_API_KEY`
- `.env.example` shows required key: `OPENAI_API_KEY=`
- OpenAI client (`OpenAI()`) reads `OPENAI_API_KEY` from environment automatically

**Build:**
- `config.json` - Runtime pipeline configuration (pipeline step toggles, OpenAI settings, zipcode, cache TTL)
- `pytest.ini` - Test runner config (coverage targets, test paths, filter warnings)
- `Makefile` - Developer workflow (`make setup`, `make test`, `make test-fast`, `make coverage`, `make chrome-debug`, `make scrape-airdna`)

## Platform Requirements

**Development:**
- macOS assumed for `make chrome-debug` target (uses `/Applications/Google Chrome.app`)
- Chrome/Chromium browser must be installed and launchable for AirDNA scraping (Playwright Chromium installed via `make setup`)
- pipenv for dependency management

**Production:**
- No deployment infrastructure detected — runs as local CLI tool
- Entry point: `python main.py` or `pipenv run python main.py`
- Pipeline outputs written to local `outputs/` directory; reports written to `reports/`

---

*Stack analysis: 2026-03-08*
