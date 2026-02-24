# Phase 2: AreaRagAggregator Rewrite

**Status:** Complete  
**Dependencies:** Phase 1 (Bug Fixes)  
**Deliverables:** Working area-level summary generation from property summaries

---

## Overview

Rewrite `AreaRagAggregator` to generate area-level insights by consuming existing property summaries. The current implementation is broken due to:
1. Wrong file paths (`results/` doesn't exist)
2. Expects combined reviews file that doesn't exist
3. Processes raw reviews instead of using existing property summaries

### Design Decision

`AreaRagAggregator` should consume **property summaries** (output of `PropertyRagAggregator`), not re-process raw reviews. This:
- Avoids duplicate OpenAI calls
- Generates higher-level area trends from already-analyzed property data
- Uses `prompts/zipcode_prompt.json` for area-level analysis

---

## Task 1: Update File Paths

### File to Edit

`review_aggregator/area_review_aggregator.py`

### Changes Required

Replace all occurrences of:
- `results/reviews_{zipcode}.json` → Read from `property_generated_summaries/` directory
- `results/generated_summaries_{zipcode}.json` → `generated_summaries_{zipcode}.json` (root directory)
- `prompt.json` → `prompts/zipcode_prompt.json`

### Specific Line Changes

**Line 143** - Change prompt file path:
```python
# FROM:
generated_prompt = load_json_file("prompt.json")["prompt"]

# TO:
generated_prompt = load_json_file("prompts/zipcode_prompt.json")["gpt4o_mini_generate_prompt_structured"]
```

**Lines 220, 233, 262, 284** - Update output path:
```python
# FROM:
filename=f"results/generated_summaries_{self.zipcode}.json"

# TO:
filename=f"generated_summaries_{self.zipcode}.json"
```

---

## Task 2: Rewrite `rag_description_generation_chain` Method

### Problem

The current method (lines 224-288) expects a combined `results/reviews_{zipcode}.json` file that doesn't exist. It needs complete rewrite to:
1. Load property summaries from `property_generated_summaries/`
2. Combine summaries as input text
3. Call OpenAI with area-level prompt
4. Save area-level output

### File to Edit

`review_aggregator/area_review_aggregator.py`

### Replace Method (lines 224-288)

Delete the existing `rag_description_generation_chain` method and replace with:

```python
def rag_description_generation_chain(self):
    """Generate area-level summary from existing property summaries."""
    
    # Load all property summaries from the output directory
    summary_files = [
        x for x in os.listdir("property_generated_summaries/")
        if x.startswith(f"generated_summaries_{self.zipcode}_")
    ]
    
    if not summary_files:
        logger.info(f"No property summaries found for zipcode {self.zipcode}; exiting.")
        return
    
    logger.info(f"Found {len(summary_files)} property summaries for zipcode {self.zipcode}")
    
    # Collect all summaries
    all_summaries = []
    for file in summary_files[:self.num_listings]:
        file_path = f"property_generated_summaries/{file}"
        summary_data = load_json_file(filename=file_path)
        # Each file is {listing_id: summary_text}
        for listing_id, summary_text in summary_data.items():
            if summary_text:
                all_summaries.append(f"Listing {listing_id}:\n{summary_text}")
    
    if not all_summaries:
        logger.info("No valid summaries to aggregate; exiting.")
        return
    
    logger.info(f"Aggregating {len(all_summaries)} property summaries into area summary")
    
    # Load area-level prompt template
    prompt_data = load_json_file("prompts/zipcode_prompt.json")
    prompt_template = prompt_data.get("gpt4o_mini_generate_prompt_structured", "")
    
    # Replace placeholders in prompt
    updated_prompt = prompt_template.replace("{ZIP_CODE_HERE}", self.zipcode)
    updated_prompt = updated_prompt.replace(
        "{ISO_CODE_HERE}", 
        load_json_file("config.json").get("iso_code", "us")
    )
    updated_prompt = updated_prompt.replace("{OVERALL_MEAN}", str(self.overall_mean))
    
    # Generate area summary using OpenAI
    area_summary = self.openai_aggregator.generate_summary(
        reviews=all_summaries,  # Pass summaries as "reviews" input
        prompt=updated_prompt,
        listing_id=f"area_{self.zipcode}"
    )
    
    # Save area-level summary
    output_data = {
        "zipcode": self.zipcode,
        "num_properties_analyzed": len(all_summaries),
        "area_summary": area_summary
    }
    
    save_json_file(
        filename=f"generated_summaries_{self.zipcode}.json",
        data=output_data
    )
    
    logger.info(f"Area summary saved to generated_summaries_{self.zipcode}.json")
    
    # Log cost and cache statistics
    self.openai_aggregator.cost_tracker.print_session_summary()
    self.openai_aggregator.cost_tracker.log_session()
    
    cache_stats = self.openai_aggregator.cache_manager.get_cache_stats()
    if cache_stats.get("enabled"):
        logger.info(
            f"\nCache Statistics: {cache_stats['valid_cache']} valid, {cache_stats['expired_cache']} expired"
        )
```

### Required Import

Add `os` import at top of file if not present:

```python
import os
```

---

## Task 3: Remove Unused Methods

### Methods to Delete or Comment Out

The following methods in `area_review_aggregator.py` are no longer needed after the rewrite:

1. `get_listing_ratings_and_reviews` (lines 66-68) - Was for raw review processing
2. `get_listing_id_mean_rating` (lines 70-82) - Was for raw review processing  
3. `clean_single_item_reviews` (lines 114-122) - Was for raw review processing (already broken)
4. `process_single_listing` (lines 124-177) - Was for raw review processing
5. `filter_out_processed_reviews` (lines 179-194) - No longer needed
6. `get_unfinished_aggregated_reviews` (lines 196-203) - Moves to simpler check
7. `get_empty_aggregated_reviews` (lines 205-210) - No longer needed
8. `remove_empty_reviews` (lines 212-222) - No longer needed

### Recommended Approach

Comment out these methods rather than delete them, with a note:
```python
# DEPRECATED: These methods were for raw review processing.
# Keeping commented for reference. Can be deleted after Phase 3 testing.
```

---

## Task 4: Uncomment AreaRagAggregator in main.py

### File to Edit

`main.py`

### Change 1: Uncomment Import (line 10)

```python
# FROM:
# from review_aggregator.area_review_aggregator import AreaRagAggregator

# TO:
from review_aggregator.area_review_aggregator import AreaRagAggregator
```

### Change 2: Uncomment Usage Block (lines 128-137)

```python
# FROM (commented block):
# if self.aggregate_summaries:
#     rag_area = AreaRagAggregator(...)
#     ...

# TO (uncommented):
if self.aggregate_summaries:
    rag_area = AreaRagAggregator(
        num_listings=self.num_summary_to_process,
        review_thresh_to_include_prop=self.review_thresh_to_include_prop,
        zipcode=self.zipcode,
    )
    rag_area.rag_description_generation_chain()
    logger.info(
        f"Aggregating area summary for zipcode {self.zipcode} completed."
    )
```

**Note:** Remove `collection_name="Summaries"` parameter since it was for Weaviate.

---

## Task 5: Update config.json Documentation

### File to Edit

`config.json`

Ensure these keys exist and document their usage:
- `aggregate_summaries`: Enable area-level summary generation (bool)
- `num_summary_to_process`: Max property summaries to include in area analysis (int)

---

## Success Criteria

1. [ ] All file paths updated from `results/` to correct directories
2. [ ] `rag_description_generation_chain` rewritten to consume property summaries
3. [ ] Import uncommented in `main.py`
4. [ ] Usage block uncommented in `main.py`
5. [ ] No syntax errors: `python -m py_compile review_aggregator/area_review_aggregator.py main.py`
6. [ ] Manual test: Run with existing property summaries generates area output

---

## Manual Verification Steps

1. Ensure `property_generated_summaries/` has at least 3 files for your zipcode
2. Set `config.json`:
   ```json
   {
     "aggregate_summaries": true,
     "num_summary_to_process": 5,
     "zipcode": "97067"
   }
   ```
3. Run: `python main.py`
4. Verify `generated_summaries_97067.json` is created with structure:
   ```json
   {
     "zipcode": "97067",
     "num_properties_analyzed": 5,
     "area_summary": "..."
   }
   ```

---

## Commit Message

```
feat: rewrite AreaRagAggregator to consume property summaries

- Update file paths from results/ to actual directory structure
- Rewrite rag_description_generation_chain to read property summaries
- Use zipcode_prompt.json for area-level analysis
- Uncomment AreaRagAggregator usage in main.py
- Remove Weaviate-specific parameters
```
