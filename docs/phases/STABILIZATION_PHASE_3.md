# Phase 3: Data Extraction & Aggregation

**Status:** Complete  
**Completed:** February 2026  
**Dependencies:** Phase 2 (AreaRagAggregator Rewrite)  
**Deliverables:** Structured JSON with area pros/cons weighted by actual review counts

---

## Overview

Extract numeric data from property summaries (the "X of Y Reviews" mentions), cluster similar topics into categories using LLM, and aggregate totals across all properties weighted by actual review counts.

### Pipeline Position

```
Property Reviews → PropertyRagAggregator → Property Summaries
                                              ↓
                                      DataExtractor (NEW)
                                              ↓
                                      Aggregated Area Data (JSON)
```

### Output Structure

```json
{
  "zipcode": "97067",
  "total_properties_analyzed": 15,
  "total_reviews_in_area": 450,
  "positive_categories": {
    "Location": {
      "total_mentions": 156,
      "total_reviews": 200,
      "percentage": 78.0,
      "properties": [
        {"id": "25923", "mentions": 15, "reviews": 20, "description": "Beautiful and secluded environment"},
        {"id": "45678", "mentions": 40, "reviews": 50, "description": "Great proximity to trails"}
      ]
    },
    "Host Communication": { ... },
    "Amenities": { ... }
  },
  "negative_categories": {
    "Cleanliness Issues": { ... },
    "Noise": { ... }
  }
}
```

---

## Seed Categories

### Positive Categories

| Category | Maps From (examples) |
|----------|---------------------|
| Location | "Location", "Beautiful Setting", "Proximity to attractions", "Views" |
| Host Communication | "Host", "Communication", "Check-in", "Responsive" |
| Cleanliness | "Cleanliness", "Tidy", "Fresh linens", "Clean" |
| Amenities | "Hot Tub", "Kitchen", "WiFi", "Parking", "Fireplace", "Amenities" |
| Value | "Value", "Price", "Worth it", "Exceeded expectations" |
| Comfort | "Comfort", "Bed quality", "Space", "Cozy", "Temperature" |
| Character/Ambiance | "Character", "Decor", "Uniqueness", "Rustic charm", "Cabin Character" |
| Accuracy | "Accuracy", "As described", "Matched photos" |

### Negative Categories

| Category | Maps From (examples) |
|----------|---------------------|
| Cleanliness Issues | "Cleanliness", "Dust", "Deep clean needed" |
| Noise | "Noise", "Noisy", "Traffic", "Neighbors" |
| Privacy Concerns | "Privacy", "Visibility", "Not private" |
| Accessibility | "Accessibility", "Stairs", "Tight spaces", "Parking difficulty" |
| Missing Amenities | "WiFi issues", "Missing supplies", "Broken items" |
| Communication Issues | "Slow response", "Unclear instructions" |
| Inaccuracy | "Photos didn't match", "Misleading" |
| Maintenance | "Repairs needed", "Outdated", "Needs work" |

---

## Task 1: Create DataExtractor Class

### File to Create

`review_aggregator/data_extractor.py`

### Class Structure

```python
"""
DataExtractor: Extracts and aggregates numeric review data from property summaries.
Uses LLM to parse semi-structured text and cluster topics into categories.
"""

import os
import logging
import sys
from typing import Any

from pydantic import BaseModel, Field, ConfigDict
from review_aggregator.openai_aggregator import OpenAIAggregator
from utils.tiny_file_handler import load_json_file, save_json_file

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


# Seed categories for clustering
POSITIVE_CATEGORIES = [
    "Location",
    "Host Communication", 
    "Cleanliness",
    "Amenities",
    "Value",
    "Comfort",
    "Character/Ambiance",
    "Accuracy"
]

NEGATIVE_CATEGORIES = [
    "Cleanliness Issues",
    "Noise",
    "Privacy Concerns",
    "Accessibility",
    "Missing Amenities",
    "Communication Issues",
    "Inaccuracy",
    "Maintenance"
]


class DataExtractor(BaseModel):
    """Extracts and aggregates review data from property summaries."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    zipcode: str = "00000"
    openai_aggregator: OpenAIAggregator = Field(default_factory=OpenAIAggregator)
    
    def load_property_summaries(self) -> dict[str, str]:
        """Load all property summaries for this zipcode."""
        summaries = {}
        summary_dir = "property_generated_summaries"
        
        if not os.path.exists(summary_dir):
            logger.warning(f"Summary directory {summary_dir} does not exist")
            return summaries
            
        for filename in os.listdir(summary_dir):
            if filename.startswith(f"generated_summaries_{self.zipcode}_"):
                file_path = f"{summary_dir}/{filename}"
                data = load_json_file(filename=file_path)
                summaries.update(data)
                
        logger.info(f"Loaded {len(summaries)} property summaries for zipcode {self.zipcode}")
        return summaries
    
    def extract_data_from_summary(self, listing_id: str, summary_text: str) -> dict:
        """Use LLM to extract structured data from a property summary."""
        
        extraction_prompt = f"""Extract the numeric review data from this property summary.

For each item mentioned in the Positives and Criticisms sections, extract:
- topic: The name of the topic (e.g., "Location", "Hot Tub")  
- sentiment: "positive" or "negative"
- mentions: The number before "of" (e.g., 15 from "15 of 20 Reviews")
- total_reviews: The number after "of" (e.g., 20 from "15 of 20 Reviews")
- description: Brief description from the summary

Categorize each topic into one of these categories:

Positive categories: {POSITIVE_CATEGORIES}
Negative categories: {NEGATIVE_CATEGORIES}

If a topic doesn't fit existing categories, assign it to the closest match or create a specific new category name.

Return a JSON object with this structure:
{{
  "listing_id": "{listing_id}",
  "total_reviews": <total reviews for this property>,
  "items": [
    {{
      "category": "<category name>",
      "original_topic": "<topic from summary>",
      "sentiment": "<positive or negative>",
      "mentions": <number>,
      "total_reviews": <number>,
      "description": "<brief description>"
    }}
  ]
}}

Property Summary:
{summary_text}
"""
        
        response = self.openai_aggregator.generate_summary(
            reviews=[extraction_prompt],
            prompt="Extract the data as requested and return only valid JSON.",
            listing_id=f"extract_{listing_id}"
        )
        
        # Parse JSON response
        try:
            import json
            # Clean response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction for {listing_id}: {e}")
            return {"listing_id": listing_id, "total_reviews": 0, "items": []}
    
    def aggregate_extractions(self, extractions: list[dict]) -> dict:
        """Aggregate extracted data across all properties."""
        
        positive_categories = {}
        negative_categories = {}
        total_reviews = 0
        
        for extraction in extractions:
            listing_id = extraction.get("listing_id", "unknown")
            listing_reviews = extraction.get("total_reviews", 0)
            total_reviews += listing_reviews
            
            for item in extraction.get("items", []):
                category = item.get("category", "Other")
                sentiment = item.get("sentiment", "positive")
                mentions = item.get("mentions", 0)
                item_reviews = item.get("total_reviews", listing_reviews)
                description = item.get("description", "")
                original_topic = item.get("original_topic", category)
                
                # Choose target dict based on sentiment
                target = positive_categories if sentiment == "positive" else negative_categories
                
                if category not in target:
                    target[category] = {
                        "total_mentions": 0,
                        "total_reviews": 0,
                        "properties": []
                    }
                
                target[category]["total_mentions"] += mentions
                target[category]["total_reviews"] += item_reviews
                target[category]["properties"].append({
                    "id": listing_id,
                    "mentions": mentions,
                    "reviews": item_reviews,
                    "original_topic": original_topic,
                    "description": description
                })
        
        # Calculate percentages
        for category_dict in [positive_categories, negative_categories]:
            for category, data in category_dict.items():
                if data["total_reviews"] > 0:
                    data["percentage"] = round(
                        (data["total_mentions"] / data["total_reviews"]) * 100, 1
                    )
                else:
                    data["percentage"] = 0.0
        
        # Sort by total mentions descending
        positive_categories = dict(
            sorted(positive_categories.items(), 
                   key=lambda x: x[1]["total_mentions"], 
                   reverse=True)
        )
        negative_categories = dict(
            sorted(negative_categories.items(), 
                   key=lambda x: x[1]["total_mentions"], 
                   reverse=True)
        )
        
        return {
            "zipcode": self.zipcode,
            "total_properties_analyzed": len(extractions),
            "total_reviews_in_area": total_reviews,
            "positive_categories": positive_categories,
            "negative_categories": negative_categories
        }
    
    def run_extraction(self):
        """Main entry point: extract, aggregate, and save."""
        
        summaries = self.load_property_summaries()
        
        if not summaries:
            logger.info(f"No property summaries found for zipcode {self.zipcode}; exiting.")
            return
        
        logger.info(f"Extracting data from {len(summaries)} property summaries")
        
        extractions = []
        for listing_id, summary_text in summaries.items():
            if summary_text:
                extraction = self.extract_data_from_summary(listing_id, summary_text)
                extractions.append(extraction)
        
        logger.info(f"Extracted data from {len(extractions)} properties")
        
        # Aggregate across all properties
        aggregated = self.aggregate_extractions(extractions)
        
        # Save output
        output_path = f"area_data_{self.zipcode}.json"
        save_json_file(filename=output_path, data=aggregated)
        
        logger.info(f"Area data saved to {output_path}")
        logger.info(f"Positive categories: {len(aggregated['positive_categories'])}")
        logger.info(f"Negative categories: {len(aggregated['negative_categories'])}")
        
        # Log costs
        self.openai_aggregator.cost_tracker.print_session_summary()
        self.openai_aggregator.cost_tracker.log_session()
        
        return aggregated
```

---

## Task 2: Add to main.py

### File to Edit

`main.py`

### Change 1: Add Import (after other review_aggregator imports, around line 10)

```python
from review_aggregator.data_extractor import DataExtractor
```

### Change 2: Add Config Variable (in `__init__`, around line 33)

```python
self.extract_data = False
```

### Change 3: Load Config (in `load_configs`, add after `aggregate_summaries`)

```python
self.extract_data = self.config.get("extract_data", False)
```

### Change 4: Add Pipeline Step (in `run_tasks_from_config`, after `aggregate_summaries` block)

```python
if self.extract_data:
    extractor = DataExtractor(zipcode=self.zipcode)
    extractor.run_extraction()
    logger.info(
        f"Data extraction for zipcode {self.zipcode} completed."
    )
```

---

## Task 3: Update config.json

### File to Edit

`config.json`

### Add Key

```json
{
  "extract_data": false
}
```

---

## Success Criteria

1. [x] `review_aggregator/data_extractor.py` created with full class
2. [x] Import added to `main.py`
3. [x] Config loading added for `extract_data`
4. [x] Pipeline step added in `run_tasks_from_config`
5. [x] No syntax errors: `python -m py_compile review_aggregator/data_extractor.py main.py`
6. [ ] Manual test produces `area_data_{zipcode}.json` with expected structure

---

## Manual Verification Steps

1. Ensure at least 3 property summaries exist in `property_generated_summaries/`
2. Set `config.json`:
   ```json
   {
     "extract_data": true,
     "zipcode": "97067"
   }
   ```
3. Run: `python main.py`
4. Verify `area_data_97067.json` created with structure matching Output Structure above
5. Check that categories are clustered correctly
6. Verify per-property breakdown is preserved

---

## Commit Message

```
feat: add DataExtractor for numeric review aggregation

- Create DataExtractor class with LLM-based parsing and clustering
- Extract "X of Y Reviews" data from property summaries
- Cluster topics into predefined categories using LLM
- Aggregate totals weighted by actual review counts
- Preserve per-property breakdown in output JSON
- Add extract_data config flag and pipeline step
```

