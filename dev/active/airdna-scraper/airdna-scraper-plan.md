## Stage 1: Setup & Dependencies

**Goal**: Add Playwright to the project and create the Chrome-debug launch infrastructure

**Success Criteria**: `pipenv run playwright install chromium` succeeds; `make chrome-debug` launches Chrome with remote debugging; new config keys parse without errors

**Status**: Complete

**Changes**:
- `Pipfile`: Add `playwright` to `[packages]`
- `Makefile`: Add `chrome-debug` target and `scrape-airdna` convenience target
- `config.json`: Add `scrape_airdna` (bool), `airdna_comp_set_ids` (list[str]), `airdna_cdp_url` (str), `airdna_inspect_mode` (bool)

---

## Stage 2: Tests (Red)

**Goal**: Write unit tests for AirDNAScraper before implementation

**Success Criteria**: Tests exist and fail because the module doesn't exist yet

**Status**: Complete

**Changes**:
- Create `tests/unit/test_airdna_scraper.py` with test classes for save_results, config loading, and data extraction parsing

---

## Stage 3: Core Scraper Module

**Goal**: Create `AirDNAScraper` class that connects to Chrome via CDP, navigates to comp set URLs, handles infinite scroll, and extracts property data

**Success Criteria**: Module compiles; unit tests pass; running against a live AirDNA comp set page produces a JSON file with correct listing IDs, ADR, Occupancy, and Days_Available values

**Status**: Complete

**Changes**:
- Create `scraper/airdna_scraper.py` with `AirDNAScraper` class:
  - `__init__(self, cdp_url: str, comp_set_ids: list[str], inspect_mode: bool)`
  - `connect(self)` — CDP connection to Chrome
  - `scrape_comp_set(self, browser, comp_set_id: str) -> dict`
  - `_scroll_to_bottom(self, page)` — infinite scroll handling
  - `_extract_property_data(self, element) -> tuple[str, dict]`
  - `save_results(self, comp_set_id: str, data: dict)`
  - `run(self)` — orchestrate full flow

---

## Stage 4: Pipeline Integration

**Goal**: Wire `AirDNAScraper` into the `main.py` pipeline via config flag

**Success Criteria**: Setting `scrape_airdna: true` in config and running `pipenv run python main.py` triggers the AirDNA scraper before other pipeline stages

**Status**: Complete

**Changes**:
- `main.py`: Load new config keys in `load_configs()`; add `scrape_airdna` block at top of `run_tasks_from_config()`

---

## Stage 5: Documentation

**Goal**: Update README with AirDNA scraper usage instructions

**Success Criteria**: A user can follow the README to successfully scrape their first comp set

**Status**: Complete

**Changes**:
- `README.md`: Add "AirDNA Comp Set Scraper" section
