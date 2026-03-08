# Technology Stack

**Project:** ADR Prediction Tool (XGBoost + Flask UI)
**Researched:** 2026-03-08
**Confidence:** MEDIUM — versions based on training data (cutoff Aug 2025). Pin exact versions after install.

---

## Recommended Stack

### ML Core

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| xgboost | `>=2.1.0` | Gradient boosted tree regression model | User-specified. Handles tabular data with mixed numeric/binary features well; robust to feature scale differences. Native `XGBRegressor` API integrates cleanly with sklearn. |
| scikit-learn | `>=1.5.0` | Cross-validation, metrics | User-specified. `cross_val_score` with `KFold(n_splits=5)` is standard. XGBoost's sklearn API wrapper satisfies the sklearn estimator interface. |
| joblib | `>=1.4.0` | Model persistence (save/load) | Ships with scikit-learn. Preferred over `pickle` for sklearn-family objects — handles numpy arrays efficiently, consistent across Python versions. |

### Web UI

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| flask | `>=3.1.0` | HTTP server + HTML form handling | User-specified. Two routes: `GET /` (render form) and `POST /predict` (return prediction). |
| Jinja2 | (ships with Flask) | HTML templating | Bundled with Flask; `render_template()` for HTML responses. |

### Data Layer (existing — no new installs)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pandas | 3.0.1 (installed) | Load amenities matrix CSV for training | Already in Pipfile. |
| numpy | 2.4.2 (installed) | Array operations during training | Already in Pipfile. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Model persistence | joblib | pickle (stdlib) | pickle has incompatibilities between Python minor versions and is slower for numpy-backed objects. |
| Model persistence | joblib | ONNX export | Over-engineered for a local tool; no benefit when training and serving share the same Python environment. |
| Web framework | Flask | FastAPI | FastAPI is designed for JSON REST APIs; Flask + Jinja2 is a single coherent unit for HTML form rendering. |
| Web framework | Flask | Django | Full-stack framework with ORM, migrations — none needed for a local 2-route prediction UI. |
| Frontend | plain Jinja2 | React / HTMX | User specified no JS framework. Plain HTML form + POST is sufficient. |

---

## Installation

Add to `Pipfile` under `[packages]`:

```toml
xgboost = "*"
scikit-learn = "*"
flask = "*"
```

Then: `pipenv install xgboost scikit-learn flask`

`joblib` does not need an explicit entry — scikit-learn pulls it in.

---

## Key Implementation Notes

**Model file location:** Save to `model/adr_model.joblib`. Flask loads it once at server startup.

**Feature column ordering:** Persist the feature column list alongside the model as `model/feature_columns.json`. Flask form-to-array conversion must reconstruct the exact input matrix column order.

**Binary feature representation:** Unchecked HTML checkboxes send no value in a POST form — the Flask view must explicitly default missing keys to `0`.

**XGBRegressor sklearn wrapper:** Use `xgboost.XGBRegressor` (not the native `xgb.train` API) so `cross_val_score` works directly.

**Flask dev server:** `app.run(debug=True)` is acceptable for local-only use.
