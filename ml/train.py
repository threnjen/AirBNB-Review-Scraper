"""
XGBoost ADR (Average Daily Rate) prediction model training script.

Loads the property amenities matrix CSV, trains an XGBRegressor with
RandomizedSearchCV (10-fold CV), log-transformed target, and saves model
artifacts to ml/model/.
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
ZONE_NAME = config.get("search_zone_name", "00000")

DEFAULT_CSV_PATH = (
    Path(__file__).parent.parent
    / "outputs"
    / "07_details_results"
    / f"property_amenities_matrix_cleaned_{ZONE_NAME}.csv"
)
DEFAULT_MODEL_DIR = Path(__file__).parent / "model"


def select_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Select feature columns and target from the amenities matrix DataFrame.

    Uses an explicit whitelist: 4 numeric features + all SYSTEM_* columns.
    """
    system_cols = sorted([c for c in df.columns if c.startswith("SYSTEM_")])
    feature_cols = NUMERIC_FEATURES + system_cols
    X = df[feature_cols].copy()
    y = df["ADR"].copy()
    return X, y


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


def drop_correlated(X: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
    """Drop one column from each pair of SYSTEM_* features with |corr| > threshold.

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
            if corr.iloc[i, j] > threshold:
                # Drop the column with lower variance
                if X[system_cols[i]].var() >= X[system_cols[j]].var():
                    to_drop.add(system_cols[j])
                else:
                    to_drop.add(system_cols[i])

    if to_drop:
        logger.info(
            "Dropping %d correlated amenities (|r|>%.2f): %s",
            len(to_drop),
            threshold,
            sorted(to_drop),
        )
    return X.drop(columns=to_drop)


def prune_zero_importance(X: pd.DataFrame, y_log: pd.Series, params: dict) -> list[str]:
    """Train a quick model and return columns with non-zero feature importance."""
    model = XGBRegressor(**params, random_state=42)
    model.fit(X, y_log)
    importances = model.feature_importances_
    keep = [col for col, imp in zip(X.columns, importances) if imp > 0]
    n_dropped = X.shape[1] - len(keep)
    if n_dropped:
        logger.info(
            "Pruning %d zero-importance features (keeping %d)",
            n_dropped,
            len(keep),
        )
    return keep


def train_model(
    X: pd.DataFrame, y: pd.Series, n_search_iter: int = 50
) -> tuple[XGBRegressor, dict]:
    """Train an XGBRegressor via RandomizedSearchCV with 5-fold CV.

    The target is log-transformed during training. The returned model
    is fit on log(y) — callers must apply np.expm1() to predictions.
    Uses early stopping to determine optimal n_estimators, then refits
    on the full dataset.
    Returns the best fitted model and a metrics dict.
    """
    y_log = np.log1p(y)

    base_model = XGBRegressor(random_state=42)
    kfold = KFold(n_splits=5, shuffle=True, random_state=42)

    search = RandomizedSearchCV(
        base_model,
        param_distributions=PARAM_GRID,
        n_iter=n_search_iter,
        scoring="neg_mean_squared_error",
        cv=kfold,
        random_state=42,
        refit=True,
        n_jobs=-1,
    )
    search.fit(X, y_log)

    best_params = search.best_params_

    # Determine optimal n_estimators via early stopping on a held-out split
    X_fit, X_es, y_fit, y_es = train_test_split(
        X, y_log, test_size=0.20, random_state=42
    )
    es_model = XGBRegressor(
        **best_params,
        random_state=42,
        early_stopping_rounds=20,
        eval_metric="rmse",
    )
    es_model.fit(X_fit, y_fit, eval_set=[(X_es, y_es)], verbose=False)
    optimal_n = es_model.best_iteration + 1
    logger.info(
        "Early stopping: %d → %d estimators",
        best_params["n_estimators"],
        optimal_n,
    )

    # Refit on full data with the early-stopped n_estimators
    final_params = {**best_params, "n_estimators": optimal_n}
    model = XGBRegressor(**final_params, random_state=42)
    model.fit(X, y_log)

    # CV RMSE in log-space, then convert to dollar-space
    cv_log_rmse = np.sqrt(-search.best_score_)
    # Per-fold RMSE in dollar-space via cross_val_score on the best model
    cv_neg_mse = cross_val_score(
        model, X, y_log, cv=kfold, scoring="neg_mean_squared_error"
    )
    cv_log_rmse_per_fold = np.sqrt(-cv_neg_mse)

    cv_neg_mae = cross_val_score(
        model, X, y_log, cv=kfold, scoring="neg_mean_absolute_error"
    )
    cv_log_mae_per_fold = -cv_neg_mae

    # Convert log-space fold errors to approximate dollar-space
    # using median(y) as the representative scale factor
    median_y = float(np.median(y))
    cv_rmse_dollar = cv_log_rmse_per_fold * median_y
    cv_mae_dollar = cv_log_mae_per_fold * median_y

    # Train RMSE in dollar-space
    train_pred_log = model.predict(X)
    train_pred = np.expm1(train_pred_log)
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
) -> None:
    """Save trained model and feature column list to disk."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, output_dir / "adr_model.joblib")

    with open(output_dir / "feature_columns.json", "w") as f:
        json.dump(feature_columns, f, indent=2)

    logger.info("Saved model artifacts to %s", output_dir)


def main(csv_path: Path = DEFAULT_CSV_PATH, output_dir: Path = DEFAULT_MODEL_DIR):
    """Full training pipeline: load data, select features, train, save."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Loading data from %s", csv_path)
    df = pd.read_csv(csv_path)
    logger.info("Dataset: %d rows × %d columns", df.shape[0], df.shape[1])

    # Inspect ADR distribution
    adr_skew = df["ADR"].skew()
    logger.info(
        "ADR stats: mean=%.1f, median=%.1f, std=%.1f, skew=%.2f",
        df["ADR"].mean(),
        df["ADR"].median(),
        df["ADR"].std(),
        adr_skew,
    )

    X, y = select_features(df)
    logger.info("Features selected: %d columns", X.shape[1])

    # Drop near-zero-variance and near-ubiquitous amenities
    system_cols = [c for c in X.columns if c.startswith("SYSTEM_")]
    prevalence = X[system_cols].mean()
    low_variance = prevalence[prevalence < 0.05].index.tolist()
    if low_variance:
        logger.info(
            "Dropping %d low-variance amenities (<5%%): %s",
            len(low_variance),
            low_variance,
        )
        X = X.drop(columns=low_variance)
    high_prevalence = prevalence[prevalence > 0.95].index.tolist()
    if high_prevalence:
        logger.info(
            "Dropping %d near-ubiquitous amenities (>95%%): %s",
            len(high_prevalence),
            high_prevalence,
        )
        X = X.drop(columns=[c for c in high_prevalence if c in X.columns])

    # Drop highly correlated amenity pairs
    X = drop_correlated(X, threshold=0.8)
    logger.info("Features after filtering: %d columns", X.shape[1])

    # Prune zero-importance features via a preliminary model
    y_log = np.log1p(y)
    keep_cols = prune_zero_importance(
        X, y_log, {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.05}
    )
    X = X[keep_cols]
    logger.info("Features after importance pruning: %d columns", X.shape[1])

    # Hold out a test set for independent evaluation
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42
    )
    logger.info(
        "Train/test split: %d train, %d test", X_train.shape[0], X_test.shape[0]
    )

    model, metrics = train_model(X_train, y_train)

    # Evaluate on held-out test set
    test_pred_log = model.predict(X_test)
    test_pred = np.expm1(test_pred_log)
    test_rmse = float(np.sqrt(np.mean((y_test - test_pred) ** 2)))
    test_mae = float(np.mean(np.abs(y_test - test_pred)))
    metrics["test_rmse"] = test_rmse
    metrics["test_mae"] = test_mae

    # Report metrics
    logger.info("--- Training Metrics ---")
    logger.info("Train RMSE:  $%.2f", metrics["train_rmse"])
    logger.info(
        "CV RMSE:     $%.2f ± $%.2f", metrics["cv_rmse_mean"], metrics["cv_rmse_std"]
    )
    logger.info(
        "CV MAE:      $%.2f ± $%.2f", metrics["cv_mae_mean"], metrics["cv_mae_std"]
    )
    logger.info("Test RMSE:   $%.2f", test_rmse)
    logger.info("Test MAE:    $%.2f", test_mae)
    logger.info("Features:    %d", metrics["n_features"])
    logger.info(
        "Samples:     %d (train) / %d (test)", X_train.shape[0], X_test.shape[0]
    )
    logger.info("Search iters: %d", metrics["n_search_iter"])
    logger.info("Best params: %s", metrics["best_params"])

    # Overfitting check
    gap = (
        (metrics["cv_rmse_mean"] - metrics["train_rmse"]) / metrics["cv_rmse_mean"]
    ) * 100
    logger.info("Train/CV gap: %.1f%%", gap)
    if gap > 30:
        logger.warning(
            "Potential overfitting: train/CV RMSE gap is %.1f%% (>30%%)", gap
        )

    # Refit on full data for production model (features already selected)
    y_log_full = np.log1p(y)
    final_params = {
        **metrics["best_params"],
        "n_estimators": metrics.get(
            "optimal_n_estimators", metrics["best_params"]["n_estimators"]
        ),
    }
    production_model = XGBRegressor(**final_params, random_state=42)
    production_model.fit(X, y_log_full)

    save_artifacts(production_model, list(X.columns), output_dir=output_dir)

    # Save metrics alongside artifacts
    with open(Path(output_dir) / "training_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info("Training complete.")


if __name__ == "__main__":
    main()
