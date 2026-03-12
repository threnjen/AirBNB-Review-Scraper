"""
Shared constants and utilities for ML training scripts.

Used by both train.py (single-model) and train_residual.py (two-stage residual).
"""

import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import (
    KFold,
    RandomizedSearchCV,
    cross_val_score,
    train_test_split,
)
from xgboost import XGBRegressor
from utils.tiny_file_handler import load_config

logger = logging.getLogger(__name__)

NUMERIC_FEATURES = [
    "capacity",
    "bedrooms",
    "beds",
    "bathrooms",
    "DIST_TO_POI",
    "BEDS_PER_PERSON",
    "BATHS_PER_PERSON",
    "BEDROOMS_PER_PERSON",
]
EXCLUDED_COLUMNS = {
    "property_id",
    "ADR",
    "Days_Avail",
    "has_airdna_data",
}

config = load_config()
ml_config = load_config(path=".ml_config.json")
ZONE_NAME = config.get("search_zone_name", "00000")

DEFAULT_CSV_PATH = (
    Path(__file__).parent.parent
    / "outputs"
    / "07_details_results"
    / f"property_amenities_matrix_cleaned_{ZONE_NAME}.csv"
)
DEFAULT_MODEL_DIR = Path(__file__).parent / "model"

PARAM_GRID = {
    "n_estimators": [100, 200, 300, 500],
    "max_depth": [2, 3, 4],
    "learning_rate": [0.01, 0.02, 0.03, 0.05],
    "reg_alpha": [1.0, 3.0, 5.0, 10.0],
    "reg_lambda": [5.0, 10.0, 20.0, 50.0],
    "min_child_weight": [10, 20, 30, 50],
    "subsample": [0.6, 0.7, 0.8, 1.0],
    "colsample_bytree": [0.3, 0.4, 0.5, 0.6],
}

THRESHOLD = ml_config.get("correlation_threshold", 0.9)
RANDOM_SEED = ml_config.get("random_seed", 42)
HIGH_PREV_THRESH = ml_config.get("high_prevalence_threshold", 0.95)
LOW_VAR_THRESH = ml_config.get("low_variance_threshold", 0.03)


def drop_correlated(X: pd.DataFrame) -> pd.DataFrame:
    """Drop one column from each pair of SYSTEM_* features with |corr| > THRESHOLD.

    Keeps the column with higher variance in each correlated pair.
    Non-SYSTEM columns are always kept.
    """
    system_cols = [c for c in X.columns if c.startswith("SYSTEM_")]
    if len(system_cols) < 2:
        return X

    corr = X[system_cols].corr().abs()
    to_drop: set[str] = set()
    for i in range(len(system_cols)):
        if system_cols[i] in to_drop:
            continue
        for j in range(i + 1, len(system_cols)):
            if system_cols[j] in to_drop:
                continue
            if corr.iloc[i, j] > THRESHOLD:
                if X[system_cols[i]].var() >= X[system_cols[j]].var():
                    to_drop.add(system_cols[j])
                else:
                    to_drop.add(system_cols[i])

    if to_drop:
        logger.info(
            f"Dropping {len(to_drop)} correlated amenities (|r|>{THRESHOLD}): {sorted(to_drop)}"
        )
    return X.drop(columns=to_drop)


def prune_zero_importance(
    X: pd.DataFrame, y_target: pd.Series, params: dict
) -> list[str]:
    """Train a quick model and return columns with non-zero feature importance."""
    model = XGBRegressor(**params, random_state=RANDOM_SEED)
    model.fit(X, y_target)
    importances = model.feature_importances_
    no_keep = [col for col, imp in zip(X.columns, importances) if imp == 0]
    keep = [col for col, imp in zip(X.columns, importances) if imp > 0]
    n_dropped = X.shape[1] - len(keep)
    if n_dropped:
        logger.info(
            f"Pruning {str(n_dropped)} zero-importance features (keeping {len(keep)})\nDropped {str(n_dropped)}: {sorted(no_keep)}\nKeeping {len(keep)}",
        )
    return keep


def train_model(
    X: pd.DataFrame,
    y: pd.Series,
    n_search_iter: int = 50,
    log_transform: bool = True,
) -> tuple[XGBRegressor, dict]:
    """Train an XGBRegressor via RandomizedSearchCV with 5-fold CV.

    When log_transform=True (default), the target is log1p-transformed
    during training. The returned model is fit on log(y) — callers must
    apply np.expm1() to predictions.

    When log_transform=False, the target is used as-is (e.g. for residuals
    that can be negative). Predictions are returned in the same space.

    Returns the best fitted model and a metrics dict.
    """
    if log_transform:
        y_fit = np.log1p(y)
    else:
        y_fit = y.copy()

    base_model = XGBRegressor(random_state=RANDOM_SEED)
    kfold = KFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)

    search = RandomizedSearchCV(
        base_model,
        param_distributions=PARAM_GRID,
        n_iter=n_search_iter,
        scoring="neg_mean_squared_error",
        cv=kfold,
        random_state=RANDOM_SEED,
        refit=True,
        n_jobs=-1,
    )
    search.fit(X, y_fit)

    best_params = search.best_params_

    # Determine optimal n_estimators via early stopping on a held-out split
    X_es_fit, X_es_val, y_es_fit, y_es_val = train_test_split(
        X, y_fit, test_size=0.20, random_state=RANDOM_SEED
    )
    es_model = XGBRegressor(
        **best_params,
        random_state=RANDOM_SEED,
        early_stopping_rounds=20,
        eval_metric="rmse",
    )
    es_model.fit(X_es_fit, y_es_fit, eval_set=[(X_es_val, y_es_val)], verbose=False)
    optimal_n = es_model.best_iteration + 1
    logger.info(
        "Early stopping: %d → %d estimators",
        best_params["n_estimators"],
        optimal_n,
    )

    # Refit on full data with the early-stopped n_estimators
    final_params = {**best_params, "n_estimators": optimal_n}
    model = XGBRegressor(**final_params, random_state=RANDOM_SEED)
    model.fit(X, y_fit)

    # CV metrics
    cv_neg_mse = cross_val_score(
        model, X, y_fit, cv=kfold, scoring="neg_mean_squared_error"
    )
    cv_neg_mae = cross_val_score(
        model, X, y_fit, cv=kfold, scoring="neg_mean_absolute_error"
    )

    if log_transform:
        cv_log_rmse_per_fold = np.sqrt(-cv_neg_mse)
        cv_log_mae_per_fold = -cv_neg_mae
        median_y = float(np.median(y))
        cv_rmse_dollar = cv_log_rmse_per_fold * median_y
        cv_mae_dollar = cv_log_mae_per_fold * median_y

        train_pred_log = model.predict(X)
        train_pred = np.expm1(train_pred_log)
        train_rmse = float(np.sqrt(np.mean((y - train_pred) ** 2)))
    else:
        cv_rmse_dollar = np.sqrt(-cv_neg_mse)
        cv_mae_dollar = -cv_neg_mae

        train_pred = model.predict(X)
        train_rmse = float(np.sqrt(np.mean((y - train_pred) ** 2)))

    metrics = {
        "cv_rmse_mean": float(cv_rmse_dollar.mean()),
        "cv_rmse_std": float(cv_rmse_dollar.std()),
        "cv_mae_mean": float(cv_mae_dollar.mean()),
        "cv_mae_std": float(cv_mae_dollar.std()),
        "train_rmse": train_rmse,
        "n_features": X.shape[1],
        "n_samples": X.shape[0],
        "best_params": {k: _jsonable(v) for k, v in best_params.items()},
        "n_search_iter": n_search_iter,
        "optimal_n_estimators": optimal_n,
        "log_transform": log_transform,
    }
    return model, metrics


def _jsonable(v):
    """Convert numpy scalars to native Python types for JSON serialization."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


def save_artifacts(
    model: XGBRegressor,
    feature_columns: list[str],
    output_dir: Path = DEFAULT_MODEL_DIR,
    model_filename: str = "adr_model.joblib",
    columns_filename: str = "feature_columns.json",
) -> None:
    """Save trained model and feature column list to disk."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, output_dir / model_filename)

    with open(output_dir / columns_filename, "w") as f:
        json.dump(feature_columns, f, indent=2)

    logger.info("Saved model artifacts to %s", output_dir)


def filter_amenity_features(
    X_amenity: pd.DataFrame, y_target: pd.Series
) -> pd.DataFrame:
    """Apply standard amenity feature filtering: low-variance, high-prevalence,
    correlation, and zero-importance pruning."""
    system_cols = [c for c in X_amenity.columns if c.startswith("SYSTEM_")]
    prevalence = X_amenity[system_cols].mean()

    # low_variance = prevalence[prevalence < LOW_VAR_THRESH].index.tolist()
    # if low_variance:
    #     logger.info(
    #         "Dropping %d low-variance amenities (<5%%): %s",
    #         len(low_variance),
    #         low_variance,
    #     )
    #     X_amenity = X_amenity.drop(columns=low_variance)

    high_prevalence = prevalence[prevalence > HIGH_PREV_THRESH].index.tolist()
    if high_prevalence:
        logger.info(
            "Dropping %d near-ubiquitous amenities (>95%%): %s",
            len(high_prevalence),
            high_prevalence,
        )
        X_amenity = X_amenity.drop(
            columns=[c for c in high_prevalence if c in X_amenity.columns]
        )

    X_amenity = drop_correlated(X_amenity)
    logger.info("Amenity features after filtering: %d columns", X_amenity.shape[1])

    keep_cols = prune_zero_importance(
        X_amenity,
        y_target,
        {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.05},
    )
    X_amenity = X_amenity[keep_cols]
    logger.info(
        "Amenity features after importance pruning: %d columns", X_amenity.shape[1]
    )

    return X_amenity


def log_stage_metrics(stage_name: str, metrics: dict) -> None:
    """Print a standard metrics report for a training stage."""
    logger.info(f"--- {stage_name} Metrics ---")
    logger.info(f"Train RMSE:  ${metrics['train_rmse']}")
    logger.info(f"CV RMSE:     ${metrics['cv_rmse_mean']} ± ${metrics['cv_rmse_std']}")
    logger.info(f"CV MAE:      ${metrics['cv_mae_mean']} ± ${metrics['cv_mae_std']}")
    if "test_rmse" in metrics:
        logger.info(f"Test RMSE:   ${metrics['test_rmse']}")
        logger.info(f"Test MAE:    ${metrics['test_mae']}")
    logger.info(f"Features:    {metrics['n_features']}")
    logger.info(f"Samples:     {metrics['n_samples']}")
    if "n_search_iter" in metrics:
        logger.info(f"Search iters: {metrics['n_search_iter']}")
    logger.info(f"Best params: {metrics['best_params']}")

    gap = (
        (metrics["cv_rmse_mean"] - metrics["train_rmse"]) / metrics["cv_rmse_mean"]
    ) * 100
    logger.info(f"Train/CV gap: {gap:.1f}%")
    if gap > 30:
        logger.warning(f"Potential overfitting: train/CV RMSE gap is {gap:.1f}% (>30%)")


def refit_production_model(
    X: pd.DataFrame,
    y: pd.Series,
    metrics: dict,
    log_transform: bool = True,
) -> XGBRegressor:
    """Refit a production model on full data using best params from search."""
    final_params = {
        **metrics["best_params"],
        "n_estimators": metrics.get(
            "optimal_n_estimators", metrics["best_params"]["n_estimators"]
        ),
    }
    model = XGBRegressor(**final_params, random_state=RANDOM_SEED)
    y_fit = np.log1p(y) if log_transform else y
    model.fit(X, y_fit)
    return model
