# Project Research Summary

**Project:** ADR Prediction Tool (XGBoost + Flask UI)
**Domain:** ML model training + local web prediction interface
**Researched:** 2026-03-08
**Confidence:** MEDIUM — stack versions based on training data (cutoff Aug 2025); core patterns are well-established

## Executive Summary

This project adds an ADR (Average Daily Rate) prediction capability to an existing Airbnb data pipeline. The work splits cleanly into two subsystems: a one-time training script that produces a serialized XGBoost model from the existing amenities matrix CSV, and a local Flask web application that loads that model at startup and serves an HTML form for interactive prediction. The two subsystems communicate only through files on disk (`adr_model.joblib` + `feature_columns.json`), which is the correct pattern for a single-user local tool — no REST API, no database, no JavaScript framework required.

The recommended approach is to build the training script first, validate model quality (checking for overfitting and leakage) before writing any Flask code, then build the Flask app as a thin serving layer. The dominant complexity is the 142-checkbox amenity form — grouping those into HTML fieldsets by category (Bathroom, Kitchen, Safety, etc.) is essential for usability and is template-only work with no architectural implications. Everything else is standard Flask form handling.

The central risk is silent correctness failures rather than crashes: feature column order mismatches produce wrong predictions with no error, feature leakage produces good CV scores but poor real-world accuracy, and unchecked HTML checkboxes silently disappear from POST data. All three are mechanical problems with deterministic prevention strategies documented in the research. Model quality risk (overfitting on 479 rows with 146 features) is the one area that requires empirical validation during Phase 1.

## Key Findings

### Recommended Stack

The stack is intentionally minimal. XGBoost and scikit-learn handle training and cross-validation; joblib handles model serialization (preferred over pickle for numpy-backed objects). Flask with Jinja2 handles the web layer. Existing pandas and numpy installs cover data loading — no new data dependencies required.

**Core technologies:**
- `xgboost >= 2.1.0`: gradient-boosted tree regression — handles mixed numeric/binary tabular data well, sklearn-compatible API enables `cross_val_score` directly
- `scikit-learn >= 1.5.0`: cross-validation and metrics — `KFold(n_splits=5)` with `cross_val_score` is the standard pattern
- `joblib >= 1.4.0`: model persistence — ships with scikit-learn, handles numpy arrays efficiently; use `joblib.dump` / `joblib.load`
- `flask >= 3.1.0`: two-route HTTP server — `GET /` renders form, `POST /predict` returns prediction; Jinja2 bundled
- `pandas 3.0.1` / `numpy 2.4.2`: already installed; no new additions needed for data layer

### Expected Features

The 142-checkbox problem is the UX problem. All other features are commodity Flask form work.

**Must have (table stakes):**
- All 142 `SYSTEM_*` amenity checkboxes rendered in form — missing any means silently wrong predictions
- 4 numeric inputs (capacity, bedrooms, beds, bathrooms) — required model features
- Server-side validation — `model.predict()` crashes on None or empty string
- Feature vector assembled in exact training column order — wrong order produces silent garbage
- Prediction result displayed as `$XXX.XX` — raw float is unreadable
- Form state preserved after POST — user must see what they checked
- Model loaded once at startup, not per-request — per-request load is avoidable latency
- Error display on prediction failure — no 500 pages

**Should have (differentiators):**
- Amenity grouping in HTML `<fieldset>` sections by category — 142 flat checkboxes is unusable without grouping
- Input range hints near numeric fields — "typical range" guidance
- Feature importance display from `model.feature_importances_`
- "Toggle all off" button for fast baseline reset

**Defer (v2+):**
- Retraining via UI — adds auth, file upload, job queue complexity; out of scope
- User accounts / session persistence — single-user local tool
- Database for prediction logging — append-to-CSV if needed later
- REST API / JSON endpoints — no external consumers

### Architecture Approach

The architecture is a clean two-subsystem split: `ml/train.py` runs offline to produce model artifacts; `app/app.py` is a Flask server that loads those artifacts at startup and serves prediction requests. The contract between them is `feature_columns.json` — the ordered list of 146 feature column names that both subsystems must agree on. No changes to the existing pipeline (`steps/`, `scraper/`, `review_aggregator/`) are required; the training script reads the existing amenities matrix CSV as a static input.

**Major components:**
1. `ml/train.py` — loads CSV, whitelists features, trains XGBRegressor with 5-fold CV, saves `adr_model.joblib` and `feature_columns.json`
2. `ml/model/` — artifact directory; `adr_model.joblib` + `feature_columns.json` are the training/serving contract
3. `app/app.py` — Flask server; loads model at module scope, `GET /` renders form, `POST /predict` assembles feature vector and returns prediction
4. `app/templates/index.html` — Jinja2 template with 4 numeric inputs + 142 checkboxes grouped in `<fieldset>` blocks by category

### Critical Pitfalls

1. **Feature column order mismatch** — Save `feature_columns.json` during training; always build prediction array by iterating that saved list, never from `request.form` keys. This is the highest-risk silent failure.
2. **Feature leakage** — Explicitly whitelist features as `['capacity', 'bedrooms', 'beds', 'bathrooms'] + [SYSTEM_* columns]`. Drop `property_id`, `ADR`, `Days_Avail`, `has_airdna_data` before training. Do not assume `df.drop(['ADR'])` leaves a clean feature set.
3. **Unchecked checkboxes absent from POST data** — Always use `1 if request.form.get(col) else 0` for every binary column. `request.form[col]` raises `KeyError`; `request.form.get(col)` returns `None` which breaks numpy array construction.
4. **Model path relative to working directory** — Use `Path(__file__).parent / 'model' / 'adr_model.joblib'` — not a relative string. The existing codebase's `CONCERNS.md` documents this same bug in the main pipeline.
5. **Overfitting on 479 rows with 146 features** — Constrain `max_depth=3` or `4`, add regularization. Report both train RMSE and CV RMSE; a gap >30% signals overfitting. Drop amenities present in <5% of properties.

## Implications for Roadmap

Based on combined research, two phases are the natural split. The training script has no Flask dependency and must exist before Flask can start. Flask has no value without a trained model artifact. These are genuinely sequential phases.

### Phase 1: ML Training Script

**Rationale:** Training must run before Flask can load a model; this phase has no web dependencies and can be validated independently. All four critical model-quality pitfalls (leakage, overfitting, outliers, column order) must be resolved here before any UI work begins.

**Delivers:** `ml/train.py`, `ml/model/adr_model.joblib`, `ml/model/feature_columns.json`, logged CV RMSE/MAE metrics

**Addresses:** Feature engineering (whitelist), model training, cross-validation, model persistence, outlier analysis

**Avoids:**
- Feature leakage (explicit whitelist)
- Overfitting (constrained depth, regularization, drop near-zero-variance amenities)
- ADR outlier distortion (inspect distribution, consider log transform)
- Column order mismatch (save `feature_columns.json` in same run as model)
- Model/feature list version mismatch (assert `len(feature_columns) == model.n_features_in_` at startup)

### Phase 2: Flask Prediction Web UI

**Rationale:** Depends on Phase 1 artifacts. All complexity is mechanical Flask form work once the model artifact and feature column contract exist. Grouping 142 checkboxes into fieldsets is the highest-effort task in this phase.

**Delivers:** `app/app.py` (two-route Flask server), `app/templates/index.html` (grouped form + result display), runnable local prediction tool

**Uses:** Flask 3.1+, Jinja2, joblib, numpy

**Implements:** Flask app component + HTML template component from ARCHITECTURE.md

**Avoids:**
- Unchecked checkbox KeyError (always `request.form.get(col)`)
- String-typed numeric inputs (cast to float, wrap in try/except)
- Model path relative to cwd (use `Path(__file__).parent`)
- 142 flat checkbox wall (group into `<fieldset>` by category in template)
- No input range validation (add server-side range checks: capacity 1-50, bedrooms 0-20, etc.)

### Phase Ordering Rationale

- Training must precede serving — Flask raises an error at startup if the model file doesn't exist, making this a hard dependency, not a preference
- Model quality validation (Phase 1) must be confirmed before building UI around it — discovering overfitting after the Flask layer is built wastes Phase 2 effort
- The two-phase split maps directly to the two-subsystem architecture documented in ARCHITECTURE.md
- Both phases have standard, well-documented patterns; neither requires additional research

### Research Flags

Phases with standard patterns (skip research-phase):
- **Phase 1:** XGBoost + sklearn cross-validation is extensively documented; pitfalls are mechanical and deterministic
- **Phase 2:** Flask two-route app with HTML forms is a textbook pattern; the 142-checkbox grouping is template work only

Potential validation point (not a full research phase):
- **Phase 1, model quality:** Whether 479 rows / 146 features produces useful model accuracy cannot be determined from research alone — requires running the actual training and inspecting CV RMSE vs. a naive baseline (mean ADR). If CV R² < 0.3, the project premise needs revisiting before building the UI.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | User-specified technologies (XGBoost, Flask); version bounds from training data (cutoff Aug 2025). Pin exact versions after `pipenv install`. |
| Features | HIGH | Feature set is tightly constrained by the project spec; the 142-checkbox count and 4 numeric inputs come directly from the existing CSV schema |
| Architecture | HIGH | Two-subsystem split is the standard pattern for offline-trained / online-serving ML tools; no architectural ambiguity |
| Pitfalls | HIGH (mechanical) / MEDIUM (data-dependent) | Pitfalls 1, 5, 6 are provably correct mechanical issues. Pitfalls 3, 4 depend on actual data distribution not yet fully characterized. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Actual model accuracy:** CV RMSE and R² cannot be predicted from research. Validate in Phase 1 before investing in Phase 2. Define a minimum acceptable R² threshold before starting.
- **ADR distribution shape:** Whether log-transforming the target is warranted depends on the actual ADR histogram. Inspect during Phase 1 training.
- **Near-zero-variance amenities:** The list of `SYSTEM_*` columns with <2-5% prevalence is unknown until data is loaded. Drop decision affects final feature count.
- **Exact package versions:** Pin `xgboost`, `scikit-learn`, and `flask` to exact installed versions in `Pipfile.lock` after installation.

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md` — project specification, technology constraints, scope boundaries
- `.planning/codebase/CONCERNS.md` — existing known issues (relative path bug documented there)
- `.planning/codebase/STRUCTURE.md` — existing directory layout, installed packages

### Secondary (MEDIUM confidence)
- XGBoost and scikit-learn documentation patterns (training knowledge, cutoff Aug 2025) — cross-validation, `XGBRegressor` sklearn API, `joblib` persistence
- Flask documentation patterns (training knowledge) — form handling, Jinja2 templating, model-at-startup pattern

### Tertiary (LOW confidence)
- Version numbers for `xgboost >= 2.1.0`, `scikit-learn >= 1.5.0`, `flask >= 3.1.0` — inferred from training data; validate against current PyPI versions at install time

---
*Research completed: 2026-03-08*
*Ready for roadmap: yes*
