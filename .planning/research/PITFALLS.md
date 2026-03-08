# Pitfalls

**Domain:** XGBoost ADR prediction + Flask web UI
**Researched:** 2026-03-08

---

## Critical Pitfalls

### 1. Feature Column Order Mismatch at Prediction Time

**What goes wrong:** XGBoost model expects features in the exact column order used during training. If the Flask form assembles the feature vector in a different order (e.g., form field order, alphabetical, or iteration order), predictions are silently wrong — no error, just garbage output.

**Prevention:** Save the ordered column list as `model/feature_columns.json` during `train.py`. In Flask, always build the prediction array by iterating that saved list — never from `request.form` keys directly.

**Phase:** Training script (Phase 1)

---

### 2. Feature Leakage

**What goes wrong:** Including columns in training that would be unavailable for a new property (e.g., `Days_Avail`, `has_airdna_data`, or any AirDNA-derived column) causes the model to learn from data that doesn't exist at prediction time. Model appears accurate in CV but performs poorly in practice.

**Prevention:** Explicitly whitelist features: `['capacity', 'bedrooms', 'beds', 'bathrooms'] + [all SYSTEM_ columns]`. Drop `property_id`, `ADR`, `Days_Avail`, `has_airdna_data` before training. Never use `df.drop(['ADR', 'property_id'])` and assume the rest is safe — be explicit.

**Phase:** Training script (Phase 1)

---

### 3. Overfitting on 479 Rows with 146 Features

**What goes wrong:** With more features than ~3x the row count, XGBoost can memorize training data. 5-fold CV RMSE looks good but test-set performance degrades.

**Prevention:** Constrain tree depth (`max_depth=3` or `4`), add regularization (`reg_alpha`, `reg_lambda`). Report both train RMSE and CV RMSE — a large gap (>30%) signals overfitting. Consider feature selection: drop amenities present in <5% of properties.

**Phase:** Training script (Phase 1)

---

### 4. ADR Outliers Distorting RMSE

**What goes wrong:** A few ultra-luxury properties with ADR of $2,000+ will dominate RMSE minimization, causing the model to optimize for the rare high end at the expense of typical properties.

**Prevention:** Inspect ADR distribution before training. Consider log-transforming the target (`np.log1p(adr)`) and back-transforming predictions (`np.expm1(pred)`). Report both RMSE and MAE — MAE is more robust to outliers.

**Phase:** Training script (Phase 1)

---

### 5. Flask Unchecked Checkboxes Send No Key

**What goes wrong:** In HTML, unchecked checkboxes are not included in the POST form data at all. Using `request.form['SYSTEM_BATHTUB']` raises a `KeyError` for any unchecked amenity. Using `request.form.get('SYSTEM_BATHTUB')` returns `None`, which then causes a type error when building the numpy array.

**Prevention:** Always use `1 if request.form.get(col) else 0` for every binary feature column. Never use `request.form[col]` for checkboxes.

**Phase:** Flask app (Phase 2)

---

### 6. Model Path Relative to Working Directory

**What goes wrong:** `joblib.load('model/adr_model.joblib')` resolves relative to `os.getcwd()`. If Flask is started from a different working directory than expected, the model file is not found at startup, crashing the server.

**Prevention:** Always use `Path(__file__).parent / 'model' / 'adr_model.joblib'` — resolves relative to the script file, not the working directory. The existing codebase's `CONCERNS.md` documents this same relative-path bug in the main pipeline; do not repeat it.

**Phase:** Flask app (Phase 2)

---

### 7. Model and Feature List Version Mismatch

**What goes wrong:** After retraining with a different feature set, the old `feature_columns.json` and new `adr_model.joblib` get out of sync. The model expects N features but the column list has M entries.

**Prevention:** Always write both files in the same `train.py` run. At Flask startup, assert `len(feature_columns) == model.n_features_in_`. Raise a clear error if they don't match rather than silently proceeding.

**Phase:** Both (Phase 1 + 2)

---

## Moderate Pitfalls

### 8. Numeric Inputs as Strings from Form

Flask's `request.form` returns all values as strings. Passing `'6'` (string) instead of `6` (int/float) to a numpy array will either cause a type error or silently create an object-dtype array that XGBoost may handle inconsistently.

**Prevention:** Always cast: `float(request.form.get('capacity', 0))`. Wrap in try/except to catch non-numeric user input.

---

### 9. Near-Zero-Variance Binary Features

Some amenities (e.g., `SYSTEM_BASEBALL`, `SYSTEM_CLIMBING_ROPE`) may appear in <1% of properties. These features contribute near-zero information but add noise and can cause issues with some CV splits where a fold has zero positive examples.

**Prevention:** After loading data, check `df[system_cols].mean()` and consider dropping columns with <2% prevalence. Document the dropped columns.

---

### 10. 5-Fold CV with Outliers

With 479 rows and potential outliers, a single CV fold may have an outlier-heavy test set, producing an anomalously high fold RMSE that inflates the reported CV error.

**Prevention:** Report mean ± std of 5 fold scores. If std > 20% of mean, investigate outliers. Consider `KFold(shuffle=True, random_state=42)` for reproducibility.

---

## Minor Pitfalls

### 11. 142 Flat Checkboxes as a Wall

A flat alphabetical list of 142 SYSTEM_ checkboxes is technically functional but practically unusable for scenario testing. Users cannot quickly find or toggle related amenities.

**Prevention:** Group into HTML `<fieldset>` sections by category (Bathroom, Kitchen, Safety, etc.). Strip `SYSTEM_` prefix and title-case the label. This is template work only — no JS required.

---

### 12. No Input Range Validation

Capacity of `999` or bedrooms of `0.5` won't crash the model but will produce nonsense predictions. The model has no concept of physical impossibility.

**Prevention:** Add server-side range validation: capacity 1–50, bedrooms 0–20, beds 0–50, bathrooms 0–20. Return a user-readable validation error rather than a garbage prediction.

---

## Sources

- `.planning/PROJECT.md` and `.planning/codebase/CONCERNS.md` (existing codebase known issues)
- XGBoost + sklearn cross-validation patterns (training knowledge, cutoff Aug 2025)
- Flask form handling conventions (training knowledge)
- Confidence: HIGH for pitfalls 1, 5, 6 (mechanical, provably correct); MEDIUM for 3, 4, 7 (depend on data characteristics not yet fully inspected)
