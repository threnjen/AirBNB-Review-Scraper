## Key Files

| File | Role |
|------|------|
| `scraper/details_fileset_build.py` | Reference pattern — class-based scraper, newest style |
| `scraper/reviews_scraper.py` | Reference pattern — rate limiting, error handling, JSON output |
| `main.py` | Pipeline orchestrator — `load_configs()` + `run_tasks_from_config()` |
| `config.json` | Boolean flags + parameters for pipeline stages |
| `custom_listing_ids.json` | Target output format — listing ID → `{ADR, Occupancy, Days_Available}` |
| `Pipfile` | Dependencies — currently no browser automation library |
| `Makefile` | Dev commands — all prefixed with `pipenv run` |
| `docs/STYLE_GUIDE.md` | OOP preferred, logging only, type annotations, ≤40-line functions |
| `tests/conftest.py` | Shared fixtures — `isolate_tests`, `mock_config`, `tmp_path` |

## Decisions

| Decision | Chose | Over | Reason |
|----------|-------|------|--------|
| Browser automation library | Playwright | Selenium | Better CDP support, modern async API, better SPA handling |
| Browser connection | Connect to open Chrome via CDP | Persistent Chromium profile | User preference; simplifies Google OAuth |
| Output format | Per-comp-set file (`compset_{id}.json`) | Overwrite `custom_listing_ids.json` | Keeps data separated; user can point `custom_filepath` in config |
| API style | `sync_api` | `async_api` | Matches project's synchronous patterns |
| Selector discovery | Built-in inspect mode (`page.pause()`) | Hardcoded selectors | AirDNA DOM is unknown and may change |

## AirDNA URL Pattern

Base: `https://app.airdna.co/data/comp-sets/{comp_set_id}`

With listing context: `https://app.airdna.co/data/comp-sets/{comp_set_id}?listing_id=abnb_{airbnb_id}`

The `listing_id` param highlights a specific listing within the comp set but is not required to load the full set.

## Output Format

Matches `custom_listing_ids.json`: keys are Airbnb listing ID strings, values have `ADR` (float), `Occupancy` (int), `Days_Available` (int).

## Technical Risks

- AirDNA DOM structure is unknown — selectors must be discovered via inspect mode on first run
- Infinite scroll timing may need tuning depending on network speed
- Airbnb listing ID may not be directly visible — might require clicking into property detail
- AirDNA may change their UI, breaking selectors — inspect mode serves as maintenance escape hatch
