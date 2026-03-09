# ADR Prediction Tool

## What This Is

A machine learning model and web interface that predicts Average Daily Rate (ADR) for Airbnb properties based on their amenities and basic property characteristics. Built on top of the existing AirBNB Review Scraper pipeline's output data, it adds a predictive layer so users can estimate nightly pricing for any property configuration.

## Core Value

Given a property's amenities and size, instantly predict what ADR it should command — so hosts can optimize their listing setup.

## Requirements

### Validated

- ✓ Airbnb property data scraped and processed into amenities matrix — existing pipeline
- ✓ ADR values captured per property in `outputs/06_details_results/property_amenities_matrix_cleaned_97067.csv` — existing

### Active

- [ ] XGBoost model trained on amenities matrix with ADR as target using 5-fold cross-validation
- [ ] Trained model saved to disk (pickle or joblib)
- [ ] Flask web app with form UI for property configuration and ADR prediction
- [ ] Numeric inputs (free entry): capacity, bedrooms, beds, bathrooms
- [ ] Binary toggles for all 142 SYSTEM_ amenity columns
- [ ] Prediction result displayed in the UI after form submission

### Out of Scope

- Days_Avail and has_airdna_data as model features — excluded per user preference
- Retraining via the UI — model is pre-trained and loaded at server start
- Authentication or multi-user support — local tool only
- Deployment beyond localhost — local development use

## Context

- **Data source:** `outputs/06_details_results/property_amenities_matrix_cleaned_97067.csv`
- **Dataset:** 479 properties, 146 feature columns (4 numeric + 142 binary amenities), ADR as target
- **Feature columns:** capacity, bedrooms, beds, bathrooms + 142 `SYSTEM_` binary amenity columns
- **Excluded from features:** property_id (identifier), Days_Avail, has_airdna_data
- **Existing codebase:** Sequential ETL pipeline (steps 01–09); this project adds a standalone ML + web layer

## Constraints

- **Stack:** Python (XGBoost, scikit-learn, Flask) — consistent with existing Python codebase
- **Data:** Fixed dataset (97067 market), no live data refresh needed for model training
- **Local only:** Flask dev server, no production deployment requirements

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| XGBoost with 5-fold CV | User specified — robust evaluation on 479-row dataset | — Pending |
| Flask + HTML frontend | User specified — simple, no JS framework | — Pending |
| Exclude Days_Avail/has_airdna_data | Not available at prediction time for new properties | — Pending |
| Numeric entry for capacity/beds/etc | Free-form makes sense; these vary continuously | — Pending |
| Binary toggles for amenities | All SYSTEM_ columns are 0/1 | — Pending |

---
*Last updated: 2026-03-08 after initialization*
