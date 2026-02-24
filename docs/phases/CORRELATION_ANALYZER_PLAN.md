````markdown
# Feature Plan: Rating Correlation Analyzer

**Status:** Planned  
**Dependencies:** Phase 3 (Data Extraction & Aggregation) — requires `property_amenities_matrix.csv` to exist  
**Deliverables:** LLM-powered analysis identifying trends between property attributes and ratings

---

## Overview

Add a feature to identify what differentiates high-rated properties from low-rated ones. The analyzer segments properties into top 25% vs bottom 25% by `guest_satisfaction`, computes statistical differences in amenities/capacity/descriptions, and uses GPT to synthesize human-readable insights.

### Pipeline Position

```
property_details_scraped/*.json
         ↓
DetailsFilesetBuilder.build_fileset()
         ↓
property_amenities_matrix.csv + property_descriptions.json
         ↓
CorrelationAnalyzer (NEW)
         ↓
property_correlation_results/
├── correlation_stats_{zipcode}.json    (statistical data)
└── correlation_insights_{zipcode}.md   (GPT-generated report)
```

### Output Structure

**Statistical JSON** (`correlation_stats_{zipcode}.json`):
```json
{
  "zipcode": "97067",
  "high_tier_threshold": 4.95,
  "low_tier_threshold": 4.58,
  "high_tier_count": 13,
  "low_tier_count": 13,
  "top_percentile": 25,
  "bottom_percentile": 25,
  "amenity_comparison": {
    "PETS": {"high_tier_pct": 75.0, "low_tier_pct": 40.0, "difference": 35.0},
    "JACUZZI": {"high_tier_pct": 92.0, "low_tier_pct": 85.0, "difference": 7.0}
  },
  "numeric_comparison": {
    "capacity": {"high_tier_avg": 9.2, "low_tier_avg": 10.1, "difference": -0.9},
    "bedrooms": {"high_tier_avg": 3.5, "low_tier_avg": 3.8, "difference": -0.3}
  }
}
```

**Insights Markdown** (`correlation_insights_{zipcode}.md`):
Human-readable report with sections for key differentiators, amenity patterns, capacity analysis, pet policy insights, description language patterns, and recommendations for hosts.

---

## Task 1: Add Config Flags

### File to Edit

`config.json`

### Changes Required

Add three new configuration parameters:

```json
{
    "analyze_correlations": false,
    "correlation_top_percentile": 25,
    "correlation_bottom_percentile": 25
}
```

| Key | Type | Description |
|-----|------|-------------|
| `analyze_correlations` | bool | Enable correlation analysis step |
| `correlation_top_percentile` | int | Percentile threshold for "high" tier (default: 25 = top 25%) |
| `correlation_bottom_percentile` | int | Percentile threshold for "low" tier (default: 25 = bottom 25%) |

---

## Task 2: Create Correlation Prompt Template

### File to Create

`prompts/correlation_prompt.json`

### Structure

```json
{
    "prompt": "You are analyzing AirBNB property data from zipcode '{ZIPCODE}'..."
}
```

### Placeholders

| Placeholder | Description |
|-------------|-------------|
| `{ZIPCODE}` | Target zipcode being analyzed |
| `{HIGH_THRESHOLD}` | Rating cutoff for high tier (e.g., 4.95) |
| `{LOW_THRESHOLD}` | Rating cutoff for low tier (e.g., 4.58) |
| `{FEATURE_COMPARISON}` | Pre-computed amenity prevalence stats |
| `{HIGH_TIER_DESCRIPTIONS}` | Sample descriptions from top-rated properties |
| `{LOW_TIER_DESCRIPTIONS}` | Sample descriptions from bottom-rated properties |

### Prompt Sections to Request from LLM

1. Key Differentiators (top 5-7 features with % differences)
2. Amenity Patterns (what correlates with ratings)
3. Capacity and Size Analysis
4. Pet Policy Insights
5. Description Language Patterns
6. Recommendations for Hosts

---

## Task 3: Create CorrelationAnalyzer Class

### File to Create

`review_aggregator/correlation_analyzer.py`

### Class Structure

Follow the Pydantic `BaseModel` pattern matching `PropertyRagAggregator`:

```python
class CorrelationAnalyzer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    zipcode: str = "00000"
    top_percentile: int = 25
    bottom_percentile: int = 25
    openai_aggregator: OpenAIAggregator = Field(default_factory=OpenAIAggregator)
```

### Methods

| Method | Responsibility |
|--------|---------------|
| `load_property_data()` | Read `property_amenities_matrix.csv`, filter properties with valid ratings |
| `load_descriptions()` | Read `property_descriptions.json` |
| `segment_by_rating()` | Split into high/low tiers using percentile thresholds |
| `compute_amenity_prevalence()` | Calculate % of properties with each amenity per tier |
| `compute_numeric_stats()` | Calculate avg capacity, bedrooms, bathrooms per tier |
| `get_sample_descriptions()` | Extract description samples for LLM context |
| `build_feature_comparison_text()` | Format statistics as human-readable text for prompt |
| `generate_insights()` | Call `OpenAIAggregator.generate_summary()` with correlation prompt |
| `save_results()` | Write JSON stats and Markdown insights to output directory |
| `run_analysis()` | Main orchestrator |

### Amenity Columns to Analyze

```python
AMENITY_COLUMNS = [
    "SYSTEM_PETS",
    "SYSTEM_JACUZZI", 
    "SYSTEM_POOL",
    "SYSTEM_FIREPLACE",
    "SYSTEM_WI_FI",
    "SYSTEM_WORKSPACE",
    "SYSTEM_GRILL",
    "SYSTEM_FIREPIT",
    "SYSTEM_WASHER",
    "SYSTEM_DRYER",
    "SYSTEM_DISHWASHER",
    "SYSTEM_TV",
    "SYSTEM_SNOWFLAKE",  # AC
    "SYSTEM_SUPERHOST",
    "SYSTEM_POOL_TABLE",
    "SYSTEM_VIDEO_GAME",
    "SYSTEM_SAUNA",
    "SYSTEM_EV_CHARGER",
    "SYSTEM_VIEW_MOUNTAIN",
]
```

### Output Directory

Create `property_correlation_results/` if it doesn't exist.

---

## Task 4: Integrate into main.py

### File to Edit

`main.py`

### Change 1: Add Import

```python
from review_aggregator.correlation_analyzer import CorrelationAnalyzer
```

### Change 2: Add Config Loading

In `AirBnbReviewAggregator.__init__()`:
```python
self.analyze_correlations = False
self.correlation_top_percentile = 25
self.correlation_bottom_percentile = 25
```

In `load_configs()`:
```python
self.analyze_correlations = self.config.get("analyze_correlations", False)
self.correlation_top_percentile = self.config.get("correlation_top_percentile", 25)
self.correlation_bottom_percentile = self.config.get("correlation_bottom_percentile", 25)
```

### Change 3: Add Execution Block

In `run_tasks_from_config()`, after the `build_details` block:

```python
if self.analyze_correlations:
    analyzer = CorrelationAnalyzer(
        zipcode=self.zipcode,
        top_percentile=self.correlation_top_percentile,
        bottom_percentile=self.correlation_bottom_percentile,
    )
    analyzer.run_analysis()
    logger.info(
        f"Correlation analysis for zipcode {self.zipcode} completed."
    )
```

---

## Success Criteria

1. [ ] Config flags added to `config.json`
2. [ ] Prompt template created at `prompts/correlation_prompt.json`
3. [ ] `CorrelationAnalyzer` class created following Pydantic pattern
4. [ ] Import and execution block added to `main.py`
5. [ ] No syntax errors: `python -m py_compile review_aggregator/correlation_analyzer.py main.py`
6. [ ] Manual test: Running with `analyze_correlations: true` generates both output files

---

## Manual Verification Steps

1. Ensure `property_amenities_matrix.csv` exists (run with `build_details: true` first)
2. Set `config.json`:
   ```json
   {
     "analyze_correlations": true,
     "correlation_top_percentile": 25,
     "correlation_bottom_percentile": 25,
     "zipcode": "97067"
   }
   ```
3. Run: `python main.py`
4. Verify `property_correlation_results/correlation_stats_97067.json` exists with expected structure
5. Verify `property_correlation_results/correlation_insights_97067.md` exists with readable insights

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Use `property_amenities_matrix.csv` as input | Avoids re-parsing raw JSON; data already normalized |
| Quartile segmentation (25%) | Clearer signal from extremes than median split |
| LLM synthesizes insights (not statistics) | GPT better at narrative; Python better at math |
| Separate JSON + Markdown outputs | JSON for programmatic use; Markdown for human reading |
| Follow existing Pydantic pattern | Consistency with `PropertyRagAggregator` |

---

## Commit Message

```
feat: add CorrelationAnalyzer for rating trend analysis

- Add analyze_correlations config flag with percentile thresholds
- Create correlation_prompt.json for LLM insights generation
- Add CorrelationAnalyzer class comparing top/bottom quartiles
- Integrate into main.py pipeline
- Output statistical JSON and human-readable Markdown report
```

````
