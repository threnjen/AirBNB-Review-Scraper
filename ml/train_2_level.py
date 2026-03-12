"""
Two-stage residual XGBoost ADR prediction model.

Stage 1: Predicts ADR from numeric property features only (capacity,
bedrooms, beds, bathrooms, distance, per-person ratios).

Stage 2: Predicts Stage 1 residuals from SYSTEM_* amenity features.

Combined prediction = Stage 1 + Stage 2.
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

DEFAULT_RESIDUAL_MODEL_DIR = Path(__file__).parent / "model" / "residual"


def main(
    csv_path: Path = DEFAULT_CSV_PATH,
    output_dir: Path = DEFAULT_RESIDUAL_MODEL_DIR,
):
    """Two-stage residual training pipeline."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Loading data from %s", csv_path)
    df = pd.read_csv(csv_path)
    logger.info("Dataset: %d rows × %d columns", df.shape[0], df.shape[1])

    y = df["ADR"].copy()
    logger.info(
        f"ADR stats: mean={y.mean():.1f}, median={y.median():.1f}, std={y.std():.1f}, skew={y.skew():.2f}"
    )
    # y = np.log(y)

    # Extract feature sets
    X_numeric = df[NUMERIC_FEATURES].copy()
    system_cols = sorted([c for c in df.columns if c.startswith("SYSTEM_")])
    X_amenity_all = df[system_cols].copy()

    # Single train/test split — same rows for both stages
    indices = np.arange(len(df))
    idx_train, idx_test = train_test_split(indices, test_size=0.10, random_state=42)
    X_num_train, X_num_test = X_numeric.iloc[idx_train], X_numeric.iloc[idx_test]
    y_train, y_test = y.iloc[idx_train], y.iloc[idx_test]

    logger.info("Train/test split: %d train, %d test", len(idx_train), len(idx_test))

    # ── Stage 1: Numeric features → ADR ──────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 1: Numeric features → ADR")
    logger.info("=" * 60)

    stage1_model, stage1_metrics = train_model(
        X_num_train, y_train, n_search_iter=50, log_transform=True
    )

    # Evaluate Stage 1 on test set
    s1_test_pred = np.expm1(stage1_model.predict(X_num_test))
    stage1_metrics["test_rmse"] = float(np.sqrt(np.mean((y_test - s1_test_pred) ** 2)))
    stage1_metrics["test_mae"] = float(np.mean(np.abs(y_test - s1_test_pred)))

    log_stage_metrics("Stage 1 (Numeric)", stage1_metrics)

    # ── Compute residuals ─────────────────────────────────────────────
    s1_train_pred = np.expm1(stage1_model.predict(X_num_train))
    residuals_train = y_train - s1_train_pred

    logger.info(
        f"Residual stats: mean={residuals_train.mean():.1f}, median={residuals_train.median():.1f}, std={residuals_train.std():.1f}"
    )

    # ── Stage 2: Amenity features → residuals ────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 2: Amenity features → Stage 1 residuals")
    logger.info("=" * 60)

    # Filter amenity features using training residuals as target
    X_amen_full = X_amenity_all.iloc[idx_train].copy()
    X_amen_full = filter_amenity_features(
        X_amen_full,
        residuals_train,
        prune_low_variance=False,
        prune_zero_importance_params=False,
    )
    amenity_keep_cols = list(X_amen_full.columns)

    X_amen_train = X_amenity_all.iloc[idx_train][amenity_keep_cols]
    X_amen_test = X_amenity_all.iloc[idx_test][amenity_keep_cols]

    stage2_model, stage2_metrics = train_model(
        X_amen_train, residuals_train, n_search_iter=50, log_transform=False
    )

    # Evaluate Stage 2 on test residuals
    residuals_test = y_test - s1_test_pred
    s2_test_pred = stage2_model.predict(X_amen_test)
    stage2_metrics["test_rmse"] = float(
        np.sqrt(np.mean((residuals_test - s2_test_pred) ** 2))
    )
    stage2_metrics["test_mae"] = float(np.mean(np.abs(residuals_test - s2_test_pred)))

    log_stage_metrics("Stage 2 (Amenities → Residuals)", stage2_metrics)

    # ── Combined evaluation ───────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("COMBINED: Stage 1 + Stage 2 → ADR")
    logger.info("=" * 60)

    combined_test_pred = s1_test_pred + s2_test_pred
    combined_test_rmse = float(np.sqrt(np.mean((y_test - combined_test_pred) ** 2)))
    combined_test_mae = float(np.mean(np.abs(y_test - combined_test_pred)))

    combined_train_pred = s1_train_pred + stage2_model.predict(X_amen_train)
    combined_train_rmse = float(np.sqrt(np.mean((y_train - combined_train_pred) ** 2)))

    logger.info(f"Combined Train RMSE: ${combined_train_rmse:.2f}")
    logger.info(f"Combined Test RMSE:  ${combined_test_rmse:.2f}")
    logger.info(f"Combined Test MAE:   ${combined_test_mae:.2f}")
    logger.info(
        f"Stage 1-only Test RMSE: ${stage1_metrics['test_rmse']:.2f} → Combined Test RMSE: ${combined_test_rmse:.2f} (improvement: ${stage1_metrics['test_rmse'] - combined_test_rmse:.2f})"
    )

    # ── Refit production models on full data ──────────────────────────
    logger.info("Refitting production models on full data...")

    # Stage 1 production: refit on all rows
    prod_stage1 = refit_production_model(
        X_numeric, y, stage1_metrics, log_transform=True
    )

    # Compute full-data residuals for Stage 2 refit
    full_s1_pred = np.expm1(prod_stage1.predict(X_numeric))
    full_residuals = y - full_s1_pred

    # Re-filter amenities on full data
    X_amen_full_refit = filter_amenity_features(
        X_amenity_all.copy(),
        full_residuals,
        prune_low_variance=False,
        prune_zero_importance_params=False,
    )
    amenity_prod_cols = list(X_amen_full_refit.columns)

    prod_stage2 = refit_production_model(
        X_amenity_all[amenity_prod_cols],
        full_residuals,
        stage2_metrics,
        log_transform=False,
    )

    # ── Save artifacts ────────────────────────────────────────────────
    save_artifacts(
        prod_stage1,
        list(X_numeric.columns),
        output_dir=output_dir,
        model_filename="stage1_model.joblib",
        columns_filename="stage1_feature_columns.json",
    )
    save_artifacts(
        prod_stage2,
        amenity_prod_cols,
        output_dir=output_dir,
        model_filename="stage2_model.joblib",
        columns_filename="stage2_feature_columns.json",
    )

    combined_metrics = {
        "stage1": stage1_metrics,
        "stage2": stage2_metrics,
        "combined_train_rmse": combined_train_rmse,
        "combined_test_rmse": combined_test_rmse,
        "combined_test_mae": combined_test_mae,
        "stage1_test_rmse": stage1_metrics["test_rmse"],
        "improvement_dollars": stage1_metrics["test_rmse"] - combined_test_rmse,
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "training_metrics.json", "w") as f:
        json.dump(combined_metrics, f, indent=2)

    logger.info("Training complete. Artifacts saved to %s", output_dir)


if __name__ == "__main__":
    main()
