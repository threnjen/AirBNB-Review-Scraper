# Zipcode-Scoped Cache Clearing

## Problem

Two bugs in the current pipeline cache behavior:

1. **Unnecessary wipes on resume**: When a stage is not "fresh" (e.g. interrupted before `record_stage_complete`), `main.py` unconditionally calls `clear_stage()` — wiping all partial progress. This destroys work from interrupted runs even when no `force_refresh` flag is set.

2. **Full-directory wipes destroy other zipcodes**: `clear_stage()` calls `LocalFileHandler.clear_directory()` which removes ALL files in the output directory, not just files for the active zipcode.

## Solution

Introduce a three-way stage action (`skip` / `resume` / `clear_and_run`) and make all clearing zipcode-scoped.

## Stage 1: Cache Manager Core Changes
**Goal**: `should_run_stage`, `clear_stage_for_zipcode`, zipcode-scoped completion
**Success Criteria**: Unit tests pass for three-way check, scoped clearing, scoped completion
**Status**: Not Started

- Add `clear_files_matching(directory, substring)` to `LocalFileHandler`
- Add `_get_listing_ids_for_zipcode(zipcode)` helper to `PipelineCacheManager`
- Add `clear_stage_for_zipcode(stage_name, zipcode)` — only removes matching files/metadata
- Update `record_stage_complete(stage_name, zipcode)` — writes `_completed:{zipcode}` key
- Update `is_stage_fresh(stage_name, zipcode)` — checks `_completed:{zipcode}`, validates only matching output files
- Add `should_run_stage(stage_name, zipcode)` — returns `"skip"`, `"resume"`, or `"clear_and_run"`

## Stage 2: Wire Up main.py
**Goal**: All stage blocks use three-way check + zipcode-scoped methods
**Success Criteria**: No stage calls `clear_stage()`; interrupted runs resume without data loss
**Status**: Not Started

- Replace binary if/else with `should_run_stage` three-way check
- `cascade_force_refresh` only on `clear_and_run` path
- All `record_stage_complete` calls pass zipcode

## Stage 3: Update Tests
**Goal**: Full test coverage for new behavior + updated existing tests
**Success Criteria**: `pipenv run pytest tests/ -x -q` passes
**Status**: Not Started
