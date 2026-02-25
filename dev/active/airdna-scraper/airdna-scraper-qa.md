# AirDNA Scraper — QA Runbook

Manual testing guide for the AirDNA comp set scraper. Use this to verify end-to-end functionality, diagnose failures, validate output, and maintain selectors when AirDNA changes their UI.

---

## Prerequisites Checklist

Before running any tests, confirm each item:

- [ ] **Chrome launched with remote debugging**
  1. **Quit Chrome completely first** (Cmd+Q). If Chrome is already running, the debug flag is silently ignored.
  2. Run:
     ```bash
     make chrome-debug
     ```
     This launches Chrome directly via its binary with `--remote-debugging-port=9222`. If `make chrome-debug` doesn't work, run the binary manually:
     ```bash
     /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 &
     ```
  3. **Verify debugging is active** — open `http://localhost:9222/json` in that Chrome. You should see a JSON array listing your open tabs. If the page doesn't load, Chrome was not launched correctly — quit and retry from step 1.

- [ ] **Logged into AirDNA** — in the same Chrome window, navigate to `https://app.airdna.co` and sign in

- [ ] **Comp set ID is valid** — visit `https://app.airdna.co/data/comp-sets/{id}` in Chrome and confirm the page loads with property rows

- [ ] **Config values are set** — edit `config.json`:
  ```json
  {
      "scrape_airdna": true,
      "airdna_comp_set_ids": ["348454"],
      "airdna_cdp_url": "http://localhost:9222",
      "airdna_inspect_mode": false
  }
  ```

- [ ] **Playwright is installed**
  ```bash
  pipenv run playwright install chromium
  ```

---

## Smoke Test

A quick end-to-end run to confirm the scraper works.

### Steps

1. Complete all prerequisites above
2. Run the scraper:
   ```bash
   make scrape-airdna
   ```
3. Watch terminal output for:
   - `Connecting to Chrome at http://localhost:9222`
   - `Navigating to comp set: https://app.airdna.co/data/comp-sets/348454`
   - `Scrolling... N properties loaded so far.`
   - `Scroll complete. Found N property elements.`
   - `Extracting data from N property rows.`
   - `Extracted N listings. Skipped M rows (no listing ID found).`
   - `Saved N listings to ./compset_348454.json`
   - `AirDNA scraping complete.`

4. Verify the output file exists:
   ```bash
   cat compset_348454.json | python -m json.tool | head -20
   ```

5. **Spot-check 2–3 listings** — pick listing IDs from the JSON, visit the comp set page in Chrome, and compare:

   | Field | JSON Value | AirDNA UI Value | Match? |
   |-------|-----------|-----------------|--------|
   | Revenue | | | |
   | ADR | | | |
   | Occupancy | | | |
   | Bedrooms | | | |
   | Bathrooms | | | |

### Expected Results

- `compset_{id}.json` file created in project root
- Contains at least 1 listing entry
- All listing IDs are numeric strings (no `abnb_` prefix)
- Metrics are non-zero for active properties

---

## Failure Scenarios & Troubleshooting

| Symptom | Error / Log Message | Cause | Fix |
|---------|-------------------|-------|-----|
| **Crash on startup** | `ConnectionError: Could not connect to Chrome at http://localhost:9222. Is Chrome running with --remote-debugging-port=9222?` | Chrome not running with debug port, or was already running when `make chrome-debug` was called (the `--args` flag is silently ignored if Chrome is already open) | Quit Chrome completely (Cmd+Q), then run `make chrome-debug`. Verify at `http://localhost:9222/json`. |
| **Crash after connect** | `RuntimeError: No browser contexts available in Chrome.` | Chrome launched but no windows open | Open at least one Chrome tab/window |
| **Empty JSON output, no error** | `No property rows found for comp set {id}. Run with inspect_mode=True to discover selectors.` (warning) | AirDNA login expired, or selectors are stale | Re-login to AirDNA in Chrome; if still empty, run with inspect mode (see Selector Maintenance below) |
| **Partial data — some rows skipped** | `Extracted N listings. Skipped M rows (no listing ID found).` | Rows don't contain `airbnb.com/rooms/{id}` links or a numeric `data-testid` | Use inspect mode to check how listing IDs are embedded in the DOM |
| **ADR/Occupancy/Revenue show as 0** | No explicit error — metrics silently default to 0 | Cell text format changed (e.g. no `$`, no `%`, no `K` suffix) | Use inspect mode; check `Row cells:` log lines for actual cell text |
| **Script hangs indefinitely** | No output after `Navigating to comp set...` | `wait_until="networkidle"` timeout on slow network | Check internet connection; the page may be loading very slowly |
| **Playwright unhandled error** | `playwright._impl._errors.TimeoutError` | Network timeout during page navigation | Retry; check AirDNA is reachable in Chrome first |
| **Inspect mode blocks forever** | `Inspect mode enabled. Use Playwright Inspector to find selectors.` | Expected behavior — `page.pause()` waits for user | Click "Resume" in the Playwright Inspector or close it to continue |

---

## Output Validation Checklist

After a successful run, verify the `compset_{id}.json` file:

- [ ] **File is valid JSON** — `python -m json.tool compset_348454.json`
- [ ] **All keys are numeric strings** — no `abnb_` prefix, no non-digit characters:
  ```bash
  pipenv run python -c "
  import json
  with open('compset_348454.json') as f:
      data = json.load(f)
  for k in data:
      assert k.isdigit(), f'Bad listing ID: {k}'
  print(f'All {len(data)} listing IDs are valid numeric strings')
  "
  ```
- [ ] **Each listing has all 5 metric keys** — `ADR`, `Occupancy`, `Revenue`, `Bedrooms`, `Bathrooms`:
  ```bash
  pipenv run python -c "
import json
with open('compset_348454.json') as f:
    data = json.load(f)
for lid, metrics in data.items():
    assert 'ADR' in metrics, f'{lid} missing ADR'
    assert 'Occupancy' in metrics, f'{lid} missing Occupancy'
    assert 'Revenue' in metrics, f'{lid} missing Revenue'
    assert 'Bedrooms' in metrics, f'{lid} missing Bedrooms'
    assert 'Bathrooms' in metrics, f'{lid} missing Bathrooms'
print(f'All {len(data)} listings have required keys')
  "
  ```
- [ ] **ADR values are positive floats** — `ADR > 0.0` for active properties
- [ ] **Occupancy values are 0–100 integers** — `0 <= Occupancy <= 100`
- [ ] **Revenue values are positive floats** — typically in thousands (e.g. 47800.0 for $47.8K)
- [ ] **Bedrooms values are non-negative integers**
- [ ] **Bathrooms values are non-negative floats** — may be decimals like 2.5
- [ ] **Listing count matches AirDNA UI** — compare `len(data)` with the visible row count on the comp set page
- [ ] **Spot-check 2–3 listings against AirDNA UI** — values should match within rounding tolerance

### Quick Validation Script

```bash
pipenv run python -c "
import json, sys

with open('compset_348454.json') as f:
    data = json.load(f)

errors = []
for lid, m in data.items():
    if not lid.isdigit():
        errors.append(f'{lid}: ID is not numeric')
    if not isinstance(m.get('ADR'), (int, float)) or m['ADR'] < 0:
        errors.append(f'{lid}: ADR={m.get(\"ADR\")} invalid')
    if not isinstance(m.get('Occupancy'), int) or not 0 <= m['Occupancy'] <= 100:
        errors.append(f'{lid}: Occupancy={m.get(\"Occupancy\")} invalid')
    if not isinstance(m.get('Revenue'), (int, float)) or m['Revenue'] < 0:
        errors.append(f'{lid}: Revenue={m.get(\"Revenue\")} invalid')
    if not isinstance(m.get('Bedrooms'), int) or m['Bedrooms'] < 0:
        errors.append(f'{lid}: Bedrooms={m.get(\"Bedrooms\")} invalid')
    if not isinstance(m.get('Bathrooms'), (int, float)) or m['Bathrooms'] < 0:
        errors.append(f'{lid}: Bathrooms={m.get(\"Bathrooms\")} invalid')

if errors:
    print(f'FAIL — {len(errors)} errors:')
    for e in errors:
        print(f'  {e}')
    sys.exit(1)
else:
    print(f'PASS — {len(data)} listings, all valid')
"
```

---

## Selector Maintenance (Inspect Mode)

When AirDNA changes their UI, the scraper's CSS selectors will break — typically producing empty output or all-zero metrics. Use inspect mode to discover the new selectors.

### When to Use

- Output JSON is empty (0 listings) despite the page loading correctly in Chrome
- All metrics are `0` / `0.0` despite the AirDNA UI showing real values
- `Row cells:` log lines show unexpected text formats
- After any known AirDNA UI redesign

### Steps

1. **Enable inspect mode** — set `"airdna_inspect_mode": true` in `config.json`

2. **Run the scraper**:
   ```bash
   make scrape-airdna
   ```

3. **Wait for Playwright Inspector to open** — a separate window appears after the comp set page loads

4. **Discover row selectors** — in the Inspector, hover over property rows and note the selector. The scraper currently uses these (in `scraper/airdna_scraper.py`):

   | What | Current Selector | Used In |
   |------|-----------------|---------|
   | Property rows (primary) | `tr[data-testid]` | `_scroll_to_bottom`, `scrape_comp_set` |
   | Property rows (fallback) | `table tbody tr` | `_scroll_to_bottom`, `scrape_comp_set` |
   | Listing ID links | `a[href]` containing `airbnb.com/rooms/{id}` | `_extract_listing_id` |
   | Listing ID fallback | `data-testid` attribute with 6+ digit number | `_extract_listing_id` |
   | Metric cells | `td` elements within each row | `_extract_property_data` |

5. **Check cell text format** — click into a row and inspect `<td>` elements:
   - Revenue cell should contain `$` + `K`/`M` suffix (e.g. `$47.8K`)
   - ADR cell should contain `$` without K/M (e.g. `$240.07`)
   - Occupancy cell should contain `%` (e.g. `70%`)
   - Bedrooms and Bathrooms are plain numbers (e.g. `3`, `2.5`)

6. **If selectors changed**, update the corresponding lines in `scraper/airdna_scraper.py` (see table above)

7. **Click "Resume"** in the Playwright Inspector to continue the scrape and verify the fix

8. **Disable inspect mode** — set `"airdna_inspect_mode": false` before production runs

---

## Downstream Integration Test

Verify the comp set output works with the rest of the pipeline.

### Steps

1. Complete a successful scrape (smoke test above)

2. Point the pipeline at the comp set file — edit `config.json`:
   ```json
   {
       "use_custom_listings_file": true,
       "custom_filepath": "compset_348454.json"
   }
   ```

3. Enable a downstream stage, e.g.:
   ```json
   {
       "scrape_reviews": true
   }
   ```

4. Run the pipeline:
   ```bash
   pipenv run python main.py
   ```

5. Verify:
   - [ ] Reviews are scraped for listing IDs from the compset file
   - [ ] No `KeyError` or format mismatches
   - [ ] Review files appear in `property_reviews_scraped/`

---

## Known Silent Failures

These behaviors produce no error — be aware of them during QA:

| Behavior | What Happens | How to Detect |
|----------|-------------|---------------|
| **Metric parse failure** | `ADR`, `Occupancy`, `Revenue`, `Bedrooms`, or `Bathrooms` defaults to `0` / `0.0` | Check output for suspicious zero values on properties you know are active |
| **Row without listing ID** | Row is silently skipped | Compare listing count in JSON vs row count in AirDNA UI; check `Skipped N rows` log message |
| **AirDNA auth expired** | Page loads login screen instead of data; scraper finds 0 rows | Output file has `{}` — re-login in Chrome and re-run |
| **Coverage gap** | `scraper.airdna_scraper` is not listed in `pytest.ini` `--cov` flags | Unit tests run but coverage is not tracked for this module |

---

## Unit Tests

The scraper has 23 unit tests in `tests/unit/test_airdna_scraper.py` that can be run without Chrome:

```bash
pipenv run pytest tests/unit/test_airdna_scraper.py -v
```

These cover: init, URL building, currency/percentage/days parsing, save results, and scroll detection logic. They do **not** cover any browser interaction — that requires the manual QA above.

---

## Quick Reference

| Action | Command |
|--------|---------|
| Launch Chrome debug | `make chrome-debug` |
| Run scraper standalone | `make scrape-airdna` |
| Run scraper via pipeline | `pipenv run python main.py` (with `scrape_airdna: true`) |
| Run unit tests | `pipenv run pytest tests/unit/test_airdna_scraper.py -v` |
| Validate output | See validation script above |
| Enable inspect mode | Set `"airdna_inspect_mode": true` in `config.json` |
