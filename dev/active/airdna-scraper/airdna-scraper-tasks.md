- [x] **Stage 1: Setup & Dependencies**
  - [x] Add `playwright` to `Pipfile` `[packages]`
  - [x] Run `pipenv install` and `pipenv run playwright install chromium`
  - [x] Add `chrome-debug` and `scrape-airdna` targets to `Makefile`
  - [x] Add `scrape_airdna`, `airdna_comp_set_ids`, `airdna_cdp_url`, `airdna_inspect_mode` to `config.json`
  - [x] Verify: config loads without errors

- [x] **Stage 2: Tests (Red)**
  - [x] Write `TestAirDNAScraperSaveResults` — JSON output format
  - [x] Write `TestAirDNAScraperConfig` — config key loading
  - [x] Write `TestAirDNAScraperParseMetrics` — metric parsing helpers
  - [x] Confirm tests fail (module not yet implemented)

- [x] **Stage 3: Core Scraper Module**
  - [x] Create `scraper/airdna_scraper.py` with `AirDNAScraper` class skeleton
  - [x] Implement `connect()` — CDP connection to Chrome
  - [x] Implement `scrape_comp_set()` — navigation + scroll + extraction
  - [x] Implement `_scroll_to_bottom()` — infinite scroll loop
  - [x] Implement `_extract_property_data()` — parse single property element
  - [x] Implement `save_results()` — JSON output
  - [x] Implement `run()` — orchestrate full flow
  - [x] Add inspect mode support (`page.pause()`)
  - [x] Verify: `pipenv run python -m py_compile scraper/airdna_scraper.py`

- [x] **Stage 4: Pipeline Integration**
  - [x] Update `load_configs()` in `main.py` for new config keys
  - [x] Add `scrape_airdna` block to `run_tasks_from_config()`
  - [x] Verify: `pipenv run python -m py_compile main.py`

- [x] **Stage 5: Tests (Green)**
  - [x] Run `pipenv run pytest tests/unit/test_airdna_scraper.py -v`
  - [x] All 23 tests pass

- [x] **Stage 6: Documentation**
  - [x] Add AirDNA scraper section to `README.md`
