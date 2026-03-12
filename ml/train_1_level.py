"""
XGBoost ADR (Average Daily Rate) prediction model training script.

Loads the property amenities matrix CSV, trains an XGBRegressor with
RandomizedSearchCV (5-fold CV), log-transformed target, and saves model
artifacts to ml/model/.
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from ml.ml_utils import (
    DEFAULT_CSV_PATH,
    DEFAULT_MODEL_DIR,
    NUMERIC_FEATURES,
    filter_amenity_features,
    log_stage_metrics,
    refit_production_model,
    save_artifacts,
    train_model,
)

logger = logging.getLogger(__name__)


def select_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Select feature columns and target from the amenities matrix DataFrame.

    Uses an explicit whitelist: 8 numeric features + all SYSTEM_* columns.
    """
    system_cols = sorted([c for c in df.columns if c.startswith("SYSTEM_")])
    feature_cols = NUMERIC_FEATURES + system_cols
    X = df[feature_cols].copy()
    y = df["ADR"].copy()
    return X, y


def main(csv_path: Path = DEFAULT_CSV_PATH, output_dir: Path = DEFAULT_MODEL_DIR):
    """Full training pipeline: load data, select features, train, save."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Loading data from %s", csv_path)
    df = pd.read_csv(csv_path)
    logger.info("Dataset: %d rows × %d columns", df.shape[0], df.shape[1])

    # Inspect ADR distribution
    adr_skew = df["ADR"].skew()
    logger.info(
        f"ADR stats: mean={df['ADR'].mean():.1f}, median={df['ADR'].median():.1f}, std={df['ADR'].std():.1f}, skew={adr_skew:.2f}"
    )

    X, y = select_features(df)
    logger.info("Features selected: %d columns", X.shape[1])

    y_log = np.log1p(y)
    X = filter_amenity_features(X, y_log)

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

    log_stage_metrics("Training", metrics)

    # Refit on full data for production model (features already selected)
    production_model = refit_production_model(X, y, metrics)

    save_artifacts(production_model, list(X.columns), output_dir=output_dir)

    # Save metrics alongside artifacts
    with open(Path(output_dir) / "training_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info("Training complete.")


if __name__ == "__main__":
    main()
