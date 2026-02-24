````markdown
# Feature Plan: Revenue Correlation Analyzer

**Status:** Planned  
**Dependencies:** Phase 3 (Data Extraction & Aggregation) — requires `property_amenities_matrix.csv` to exist  
**Deliverables:** LLM-powered analysis identifying what drives high ADR (pricing power) and high occupancy (booking frequency)

---

## Overview

Add a feature to identify what differentiates high-performing properties from low-performing ones based on **revenue metrics**. The analyzer generates two independent analyses:

1. **ADR Analysis** — What amenities, capacity, and descriptions allow properties to command higher nightly rates?
2. **Occupancy Analysis** — What features attract more bookings and higher occupancy?

Each analysis segments properties into top 25% vs bottom 25% by the respective metric, computes statistical differences, and uses GPT to synthesize actionable insights for hosts.

### Data Source

The `property_amenities_matrix.csv` contains these revenue fields (sourced from `custom_listing_ids.json`):

| Column | Description |
|--------|-------------|
| `ADR` | Average Daily Rate in USD |
| `Occ_Rate_Based_on_Avail` | Occupancy % relative to available days |
| `Abs_Occ_Rate` | Absolute occupancy (% of 365 days) |
| `Days_Avail` | Days property is listed as available |

### Pipeline Position

```
property_details_scraped/*.json + custom_listing_ids.json
         ↓
DetailsFilesetBuilder.build_fileset()
         ↓
property_amenities_matrix.csv + property_descriptions.json
         ↓
CorrelationAnalyzer (NEW) — runs once per metric
         ↓
property_correlation_results/
├── correlation_stats_adr_{zipcode}.json
├── correlation_stats_occupancy_{zipcode}.json
├── correlation_insights_adr_{zipcode}.md
└── correlation_insights_occupancy_{zipcode}.md
```

### Output Structure

**Statistical JSON** (`correlation_stats_adr_{zipcode}.json`):
```json
{
  "zipcode": "97067",
  "metric": "adr",
  "metric_column": "ADR",
  "high_tier_threshold": 598.10,
  "low_tier_threshold": 285.50,
  "high_tier_count": 13,
  "low_tier_count": 13,
  "top_percentile": 25,
  "bottom_percentile": 25,
  "amenity_comparison": {
    "SYSTEM_JACUZZI": {"high_tier_pct": 100.0, "low_tier_pct": 54.0, "difference": 46.0},
    "SYSTEM_POOL_TABLE": {"high_tier_pct": 38.0, "low_tier_pct": 8.0, "difference": 30.0}
  },
  "numeric_comparison": {
    "capacity": {"high_tier_avg": 12.5, "low_tier_avg": 6.2, "difference": 6.3},
    "bedrooms": {"high_tier_avg": 5.1, "low_tier_avg": 2.4, "difference": 2.7}
  }
}
```

**Insights Markdown** (`correlation_insights_adr_{zipcode}.md`):
Human-readable report with sections for:
- Key Differentiators (what drives premium pricing)
- Amenity Patterns (luxury features vs basics)
- Capacity & Size Analysis (larger = higher ADR?)
- Pet Policy Impact
- Description Language Patterns
- Recommendations for Hosts seeking higher rates

**Occupancy Insights** focus instead on:
- What drives booking frequency
- Accessibility features
- Pet-friendliness impact
- Availability patterns
- Recommendations for Hosts seeking more bookings

---

## Task 1: Add Config Flags

### File to Edit

`config.json`

### Changes Required

Add four new configuration parameters:

```json
{
    "analyze_correlations": false,
    "correlation_metrics": ["adr", "occupancy"],
    "correlation_top_percentile": 25,
    "correlation_bottom_percentile": 25
}
```

| Key | Type | Description |
|-----|------|-------------|
| `analyze_correlations` | bool | Enable correlation analysis step |
| `correlation_metrics` | array | Which metrics to analyze: `"adr"`, `"occupancy"`, or both |
| `correlation_top_percentile` | int | Percentile threshold for "high" tier (default: 25 = top 25%) |
| `correlation_bottom_percentile` | int | Percentile threshold for "low" tier (default: 25 = bottom 25%) |

### Metric Mapping

| Config Value | CSV Column | Description |
|--------------|------------|-------------|
| `"adr"` | `ADR` | Average Daily Rate |
| `"occupancy"` | `Occ_Rate_Based_on_Avail` | Occupancy rate based on available days |

---

## Task 2: Create Correlation Prompt Template

### File to Create

`prompts/correlation_prompt.json`

### Structure

```json
{
    "adr_prompt": "You are analyzing AirBNB property data from zipcode '{ZIPCODE}' to understand what drives higher nightly rates (ADR)...",
    "occupancy_prompt": "You are analyzing AirBNB property data from zipcode '{ZIPCODE}' to understand what drives higher booking frequency (occupancy)..."
}
```

### Placeholders

| Placeholder | Description |
|-------------|-------------|
| `{ZIPCODE}` | Target zipcode being analyzed |
| `{METRIC_NAME}` | Human-readable metric name ("Average Daily Rate" or "Occupancy Rate") |
| `{HIGH_THRESHOLD}` | Metric cutoff for high tier (e.g., $598.10 or 75%) |
| `{LOW_THRESHOLD}` | Metric cutoff for low tier (e.g., $285.50 or 25%) |
| `{FEATURE_COMPARISON}` | Pre-computed amenity prevalence stats |
| `{HIGH_TIER_DESCRIPTIONS}` | Sample descriptions from high-performing properties |
| `{LOW_TIER_DESCRIPTIONS}` | Sample descriptions from low-performing properties |

### Prompt Sections by Metric

**ADR Analysis:**
1. Key Differentiators driving premium pricing
2. Luxury Amenity Patterns (hot tub, pool, game room)
3. Capacity & Size Premium (larger homes → higher ADR?)
4. Description Language (how do premium listings describe themselves?)
5. Recommendations for hosts seeking higher rates

**Occupancy Analysis:**
1. Key Differentiators driving booking frequency
2. Accessibility & Convenience Features
3. Pet-Friendliness Impact
4. Capacity Sweet Spot (is there an optimal size?)
5. Recommendations for hosts seeking more bookings

---

## Task 3: Create CorrelationAnalyzer Class

### File to Create

`review_aggregator/correlation_analyzer.py`

### Class Structure

Follow the Pydantic `BaseModel` pattern matching `PropertyRagAggregator`:

```python
# Metric configuration
METRIC_CONFIG = {
    "adr": {
        "column": "ADR",
        "display_name": "Average Daily Rate",
        "unit": "$",
        "higher_is_better": True,
    },
    "occupancy": {
        "column": "Occ_Rate_Based_on_Avail",
        "display_name": "Occupancy Rate",
        "unit": "%",
        "higher_is_better": True,
    },
}

class CorrelationAnalyzer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    zipcode: str = "00000"
    metrics: list[str] = ["adr", "occupancy"]
    top_percentile: int = 25
    bottom_percentile: int = 25
    openai_aggregator: OpenAIAggregator = Field(default_factory=OpenAIAggregator)
```

### Methods

| Method | Responsibility |
|--------|---------------|
| `load_property_data()` | Read `property_amenities_matrix.csv`, filter properties with valid metric values |
| `load_descriptions()` | Read `property_descriptions.json` |
| `segment_by_metric(metric: str)` | Split into high/low tiers using percentile thresholds on specified metric column |
| `compute_amenity_prevalence()` | Calculate % of properties with each amenity per tier |
| `compute_numeric_stats()` | Calculate avg capacity, bedrooms, bathrooms per tier |
| `get_sample_descriptions()` | Extract description samples for LLM context |
| `build_feature_comparison_text()` | Format statistics as human-readable text for prompt |
| `generate_insights(metric: str)` | Call `OpenAIAggregator.generate_summary()` with metric-specific prompt |
| `save_results(metric: str)` | Write JSON stats and Markdown insights per metric |
| `run_analysis()` | Main orchestrator — loops over configured metrics |

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
self.correlation_metrics = ["adr", "occupancy"]
self.correlation_top_percentile = 25
self.correlation_bottom_percentile = 25
```

In `load_configs()`:
```python
self.analyze_correlations = self.config.get("analyze_correlations", False)
self.correlation_metrics = self.config.get("correlation_metrics", ["adr", "occupancy"])
self.correlation_top_percentile = self.config.get("correlation_top_percentile", 25)
self.correlation_bottom_percentile = self.config.get("correlation_bottom_percentile", 25)
```

### Change 3: Add Execution Block

In `run_tasks_from_config()`, after the `extract_data` block:

```python
if self.analyze_correlations:
    analyzer = CorrelationAnalyzer(
        zipcode=self.zipcode,
        metrics=self.correlation_metrics,
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

1. [ ] Config flags added to `config.json` (including `correlation_metrics` array)
2. [ ] Prompt templates created at `prompts/correlation_prompt.json` (separate prompts for ADR/occupancy)
3. [ ] `CorrelationAnalyzer` class created with `segment_by_metric()` supporting both metrics
4. [ ] Import and execution block added to `main.py`
5. [ ] No syntax errors: `pipenv run python -m py_compile review_aggregator/correlation_analyzer.py main.py`
6. [ ] Manual test: Running with `analyze_correlations: true` generates 4 output files (2 per metric)

---

## Manual Verification Steps

1. Ensure `property_amenities_matrix.csv` exists (run with `build_details: true` first)
2. Set `config.json`:
   ```json
   {
     "analyze_correlations": true,
     "correlation_metrics": ["adr", "occupancy"],
     "correlation_top_percentile": 25,
     "correlation_bottom_percentile": 25,
     "zipcode": "97067"
   }
   ```
3. Run: `pipenv run python main.py`
4. Verify these files exist in `property_correlation_results/`:
   - `correlation_stats_adr_97067.json`
   - `correlation_stats_occupancy_97067.json`
   - `correlation_insights_adr_97067.md`
   - `correlation_insights_occupancy_97067.md`
5. Verify ADR insights discuss pricing power and premium amenities
6. Verify occupancy insights discuss booking frequency and accessibility

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Use `property_amenities_matrix.csv` as input | Avoids re-parsing raw JSON; data already normalized with ADR/occupancy |
| Dual-metric approach (ADR + Occupancy) | Price-drivers and volume-drivers may differ — separate analyses avoid conflation |
| Use `Occ_Rate_Based_on_Avail` not `Abs_Occ_Rate` | Accounts for intentional availability limits (seasonal rentals) |
| Quartile segmentation (25%) | Clearer signal from extremes than median split |
| LLM synthesizes insights (not statistics) | GPT better at narrative; Python better at math |
| Separate JSON + Markdown outputs per metric | JSON for programmatic use; Markdown for human reading |
| Follow existing Pydantic pattern | Consistency with `PropertyRagAggregator` |

---

## Commit Message

```
feat: add CorrelationAnalyzer for ADR and occupancy trend analysis

- Add analyze_correlations config flag with metrics array and percentile thresholds
- Create correlation_prompt.json with separate prompts for ADR/occupancy insights
- Add CorrelationAnalyzer class comparing top/bottom quartiles by revenue metrics
- Integrate into main.py pipeline
- Output statistical JSON and human-readable Markdown per metric
```

````
