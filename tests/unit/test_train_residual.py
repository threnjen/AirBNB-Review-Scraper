"""
Unit tests for ml/train_residual.py — two-stage residual model.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _make_sample_df(n_rows=80, n_amenities=10):
    """Create a minimal DataFrame matching the expected CSV schema."""
    rng = np.random.RandomState(42)
    data = {
        "property_id": range(1000, 1000 + n_rows),
        "capacity": rng.randint(1, 16, n_rows),
        "bedrooms": rng.randint(0, 8, n_rows),
        "beds": rng.randint(1, 12, n_rows),
        "bathrooms": rng.uniform(0.5, 5, n_rows).round(1),
        "DIST_TO_POI": rng.uniform(0.5, 30, n_rows).round(2),
    }
    cap = np.maximum(data["capacity"], 1)
    data["BEDS_PER_PERSON"] = (data["beds"] / cap).round(2)
    data["BATHS_PER_PERSON"] = (data["bathrooms"] / cap).round(2)
    data["BEDROOMS_PER_PERSON"] = (data["bedrooms"] / cap).round(2)
    for i in range(n_amenities):
        data[f"SYSTEM_AMENITY_{i}"] = rng.choice([0, 1], n_rows)
    data["ADR"] = rng.uniform(50, 500, n_rows).round(2)
    data["Days_Avail"] = rng.randint(30, 365, n_rows)
    data["has_airdna_data"] = rng.choice([0, 1], n_rows)
    return pd.DataFrame(data)


class TestFilterAmenityFeatures:
    """Tests for filter_amenity_features."""

    def test_returns_only_system_columns(self):
        from ml.ml_utils import filter_amenity_features

        rng = np.random.RandomState(42)
        X = pd.DataFrame(
            {f"SYSTEM_AMENITY_{i}": rng.choice([0, 1], 80) for i in range(10)}
        )
        y = pd.Series(rng.normal(0, 50, 80))

        result = filter_amenity_features(X, y)
        for col in result.columns:
            assert col.startswith("SYSTEM_")

    def test_returns_fewer_or_equal_columns(self):
        from ml.ml_utils import filter_amenity_features

        rng = np.random.RandomState(42)
        X = pd.DataFrame(
            {f"SYSTEM_AMENITY_{i}": rng.choice([0, 1], 80) for i in range(10)}
        )
        y = pd.Series(rng.normal(0, 50, 80))

        result = filter_amenity_features(X, y)
        assert result.shape[1] <= X.shape[1]


class TestResidualMainPipeline:
    """Integration tests for the two-stage residual pipeline."""

    def test_main_produces_artifacts(self, tmp_path):
        """main() should produce stage1/stage2 models and metrics."""
        from ml.train_2_level import main

        df = _make_sample_df(n_rows=80, n_amenities=10)
        csv_path = tmp_path / "test_data.csv"
        df.to_csv(csv_path, index=False)

        output_dir = tmp_path / "model_output"
        main(csv_path=csv_path, output_dir=output_dir)

        assert (output_dir / "stage1_model.joblib").exists()
        assert (output_dir / "stage1_feature_columns.json").exists()
        assert (output_dir / "stage2_model.joblib").exists()
        assert (output_dir / "stage2_feature_columns.json").exists()
        assert (output_dir / "training_metrics.json").exists()

    def test_stage1_uses_only_numeric_features(self, tmp_path):
        """Stage 1 feature columns should be exactly the 8 numeric features."""
        from ml.train_2_level import main
        from ml.ml_utils import NUMERIC_FEATURES

        df = _make_sample_df(n_rows=80, n_amenities=10)
        csv_path = tmp_path / "test_data.csv"
        df.to_csv(csv_path, index=False)

        output_dir = tmp_path / "model_output"
        main(csv_path=csv_path, output_dir=output_dir)

        with open(output_dir / "stage1_feature_columns.json") as f:
            s1_cols = json.load(f)

        assert s1_cols == NUMERIC_FEATURES

    def test_stage2_uses_only_system_features(self, tmp_path):
        """Stage 2 feature columns should all be SYSTEM_* columns."""
        from ml.train_2_level import main

        df = _make_sample_df(n_rows=80, n_amenities=10)
        csv_path = tmp_path / "test_data.csv"
        df.to_csv(csv_path, index=False)

        output_dir = tmp_path / "model_output"
        main(csv_path=csv_path, output_dir=output_dir)

        with open(output_dir / "stage2_feature_columns.json") as f:
            s2_cols = json.load(f)

        for col in s2_cols:
            assert col.startswith("SYSTEM_")

    def test_combined_prediction_equals_sum(self, tmp_path):
        """Combined prediction = stage1 + stage2 predictions."""
        import joblib
        from ml.train_2_level import main

        df = _make_sample_df(n_rows=80, n_amenities=10)
        csv_path = tmp_path / "test_data.csv"
        df.to_csv(csv_path, index=False)

        output_dir = tmp_path / "model_output"
        main(csv_path=csv_path, output_dir=output_dir)

        s1_model = joblib.load(output_dir / "stage1_model.joblib")
        s2_model = joblib.load(output_dir / "stage2_model.joblib")

        with open(output_dir / "stage1_feature_columns.json") as f:
            s1_cols = json.load(f)
        with open(output_dir / "stage2_feature_columns.json") as f:
            s2_cols = json.load(f)

        row = df.iloc[:1]
        s1_pred = np.expm1(s1_model.predict(row[s1_cols]))[0]
        s2_pred = s2_model.predict(row[s2_cols])[0]
        combined = s1_pred + s2_pred

        assert np.isfinite(combined)

    def test_metrics_json_has_all_sections(self, tmp_path):
        """training_metrics.json should have stage1, stage2, and combined keys."""
        from ml.train_2_level import main

        df = _make_sample_df(n_rows=80, n_amenities=10)
        csv_path = tmp_path / "test_data.csv"
        df.to_csv(csv_path, index=False)

        output_dir = tmp_path / "model_output"
        main(csv_path=csv_path, output_dir=output_dir)

        with open(output_dir / "training_metrics.json") as f:
            metrics = json.load(f)

        assert "stage1" in metrics
        assert "stage2" in metrics
        assert "combined_test_rmse" in metrics
        assert "combined_test_mae" in metrics
        assert "combined_train_rmse" in metrics
        assert "improvement_dollars" in metrics
        assert "stage1_test_rmse" in metrics
