# AirDNA Per-Listing Refactor Plan

## Overview

Refactor the pipeline so AirDNA scraping uses per-listing rentalizer lookups
instead of manually-created comp sets. New flow:
zipcode → AirBnB search → per-listing AirDNA rentalizer → compiled comp set.

## Stage 1: AGENTS.md Update

**Goal**: Add guideline about switching to Agent mode after planning.
**Success Criteria**: New bullet added under Plan Mode Rules.
**Status**: Not Started

## Stage 2: Directory Swap + Pipeline Reorder

**Goal**: Swap `outputs/01_comp_sets` ↔ `outputs/02_search_results` and reorder
`STAGE_ORDER` so `search` comes before `airdna`.
**Success Criteria**: All path references updated (19 total), `STAGE_ORDER` lists
`search` before `airdna`, `run_tasks_from_config` runs search before airdna,
tests pass.
**Status**: Not Started

Files to change:
- `utils/pipeline_cache_manager.py` — swap in `STAGE_ORDER` and `STAGE_OUTPUT_DIRS`
- `main.py` — 4 refs to `01_comp_sets`, 1 ref to `02_search_results`, reorder `run_tasks_from_config`
- `scraper/airbnb_searcher.py` — 2 refs to `02_search_results`
- `scraper/airdna_scraper.py` — 1 ref to `01_comp_sets`
- `README.md` — 3 refs to `01_comp_sets`, 2 refs to `02_search_results`
- `tests/unit/test_compile_comp_sets.py` — 2 refs
- `tests/unit/test_details_fileset_build.py` — 2 refs

## Stage 3: Rewrite AirDNA Scraper

**Goal**: Replace comp-set-based scraping with rentalizer per-listing scraping.
**Success Criteria**: `AirDNAScraper` accepts `listing_ids`, navigates to
`https://app.airdna.co/data/rentalizer?&listing_id=abnb_{id}`, extracts metrics
(Bedrooms, Bathrooms, Max Guests, Rating, Review Count, Revenue, Days Available,
ADR, Occupancy), saves per-listing JSON files, filters out listings with
`Days_Available < min_days_available`.
**Status**: Not Started

Key changes in `scraper/airdna_scraper.py`:
- `__init__` takes `listing_ids` instead of `comp_set_ids`, plus `min_days_available`
- New `_build_rentalizer_url(listing_id)` replaces `_build_comp_set_url`
- New `scrape_listing(page, listing_id)` replaces `scrape_comp_set`
- `save_results` writes `listing_{id}.json` instead of `compset_{id}.json`
- Remove scrolling/comp-set logic: `_scroll_to_bottom`, `_should_continue_scrolling`,
  `_extract_listing_id`, `_extract_property_data`
- Keep parsing helpers: `_parse_currency`, `_parse_percentage`, `_parse_revenue`, etc.
- Filter: skip saving if `Days_Available < min_days_available`, log a message

## Stage 4: Update main.py Integration

**Goal**: Wire new scraper into pipeline, remove comp set ID dependency.
**Success Criteria**: `run_tasks_from_config` passes search result listing IDs to
`AirDNAScraper`, `compile_comp_sets` globs `listing_*.json`, `get_area_search_results`
no longer short-circuits on comp set file.
**Status**: Not Started

Key changes:
- Remove `self.airdna_comp_set_ids` from `__init__`/`load_configs`
- Add `self.min_days_available` from config (default 100)
- `scrape_airdna` block calls `get_area_search_results()` first
- `compile_comp_sets` glob pattern → `listing_*.json`
- Remove comp-set-file-bypass in `get_area_search_results`

## Stage 5: Update Config

**Goal**: Remove `airdna_comp_set_ids`, add `min_days_available`.
**Success Criteria**: `config.json` updated, pipeline still runs.
**Status**: Not Started

## Stage 6: Update Tests

**Goal**: All tests reflect new architecture.
**Success Criteria**: `pipenv run pytest` passes, tests cover new `scrape_listing`,
`listing_*.json` glob, removed comp-set-bypass, min_days_available filter.
**Status**: Not Started

Tests to update:
- `tests/unit/test_airdna_scraper.py` — rewrite for per-listing API
- `tests/unit/test_compile_comp_sets.py` — `listing_*.json` pattern
- `tests/unit/test_get_area_search_results.py` — remove comp-set-exists test

## Decisions

- "Annual Revenue" → `Revenue`, "Average Daily Rate" → `ADR`
- `LY_Revenue` not on rentalizer page — default to `0.0`
- Per-listing files: `listing_{id}.json` for resumable scraping
- Filter at scrape time: skip listings with `Days_Available < min_days_available`
- `min_days_available` configurable in config.json (default 100)
