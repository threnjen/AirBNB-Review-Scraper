# AirDNA Per-Listing Refactor — Context

## Key Files

| File | Role |
|------|------|
| `scraper/airdna_scraper.py` | AirDNA scraper (being rewritten) |
| `scraper/airbnb_searcher.py` | AirBnB geo search by zipcode |
| `main.py` | Pipeline orchestrator |
| `utils/pipeline_cache_manager.py` | Stage ordering, TTL cache, cascade logic |
| `config.json` | Runtime configuration |
| `tests/unit/test_airdna_scraper.py` | Scraper tests |
| `tests/unit/test_compile_comp_sets.py` | Comp set compilation tests |
| `tests/unit/test_get_area_search_results.py` | Search results tests |

## Architecture Change

### Before
```
Manual comp set creation on AirDNA website
  → scrape_airdna (reads comp set pages by ID)
  → compile_comp_sets
  → airbnb_searcher (OR uses comp set IDs, bypassing search)
  → downstream stages
```

### After
```
zipcode
  → airbnb_searcher (geo search, saves to outputs/01_search_results)
  → scrape_airdna (per-listing rentalizer lookup, saves to outputs/02_comp_sets)
  → compile_comp_sets
  → downstream stages
```

## Rentalizer URL Pattern

`https://app.airdna.co/data/rentalizer?&listing_id=abnb_{airbnb_listing_id}`

## Page Structure (from screenshot)

**Header area** (icon+text pairs):
- Bedrooms: 4, Bathrooms: 3, Max Guests: 15
- Rating: 4.7, Review Count: 287

**KPI cards row** (value + label):
- Revenue Potential: $57.5K
- Days Available: 333
- Annual Revenue: $51.7K
- Occupancy: 32%
- Average Daily Rate: $487.5

## Field Mapping to Existing Schema

| Rentalizer Page | Comp Set Field |
|-----------------|---------------|
| Annual Revenue | `Revenue` |
| Average Daily Rate | `ADR` |
| Occupancy | `Occupancy` |
| Days Available | `Days_Available` |
| Bedrooms | `Bedrooms` |
| Bathrooms | `Bathrooms` |
| Max Guests | `Max_Guests` |
| Rating | `Rating` |
| Review Count | `Review_Count` |
| *(not available)* | `LY_Revenue` (default 0.0) |

## Directory Swap

| Stage | Old Dir | New Dir |
|-------|---------|---------|
| search | `outputs/02_search_results` | `outputs/01_search_results` |
| airdna | `outputs/01_comp_sets` | `outputs/02_comp_sets` |

## Filtering

- Skip listings with `Days_Available < min_days_available` (default 100)
- Applied at scrape time (don't save listing file)
- Configurable via `min_days_available` in config.json
