"""
Unit tests for ml/train.py
"""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


def _make_sample_df(n_rows=50, n_amenities=10):
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


class TestSelectFeatures:
    """Tests for feature selection logic."""

    def test_excludes_leaked_columns(self):
        """Feature whitelist must exclude property_id, ADR, Days_Avail, has_airdna_data."""
        from ml.train import select_features

        df = _make_sample_df()
        X, y = select_features(df)

        assert "property_id" not in X.columns
        assert "ADR" not in X.columns
        assert "Days_Avail" not in X.columns
        assert "has_airdna_data" not in X.columns

    def test_includes_numeric_features(self):
        """Feature whitelist must include capacity, bedrooms, beds, bathrooms, ratios."""
        from ml.train import select_features

        df = _make_sample_df()
        X, y = select_features(df)

        for col in [
            "capacity",
            "bedrooms",
            "beds",
            "bathrooms",
            "BEDS_PER_PERSON",
            "BATHS_PER_PERSON",
            "BEDROOMS_PER_PERSON",
        ]:
            assert col in X.columns

    def test_includes_all_system_columns(self):
        """Feature whitelist must include all SYSTEM_ columns from the DataFrame."""
        from ml.train import select_features

        df = _make_sample_df(n_amenities=15)
        X, y = select_features(df)

        system_cols = [c for c in df.columns if c.startswith("SYSTEM_")]
        for col in system_cols:
            assert col in X.columns

    def test_target_is_adr(self):
        """Target variable y must be the ADR column."""
        from ml.train import select_features

        df = _make_sample_df()
        X, y = select_features(df)

        pd.testing.assert_series_equal(y, df["ADR"], check_names=False)

    def test_feature_count_matches(self):
        """Feature count should be 8 numeric + N system columns."""
        from ml.train import select_features

        df = _make_sample_df(n_amenities=10)
        X, y = select_features(df)

        assert X.shape[1] == 8 + 10  # 8 numeric + 10 amenities


class TestTrainModel:
    """Tests for model training."""

    def test_returns_model_and_metrics(self):
        """train_model returns a fitted model and a metrics dict."""
        from ml.train import select_features, train_model

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X, y = select_features(df)
        model, metrics = train_model(X, y, n_search_iter=3)

        assert hasattr(model, "predict")
        assert "cv_rmse_mean" in metrics
        assert "cv_mae_mean" in metrics
        assert "train_rmse" in metrics
        assert "best_params" in metrics
        assert "n_search_iter" in metrics

    def test_model_feature_count_matches_input(self):
        """Trained model must expect the same number of features as X."""
        from ml.train import select_features, train_model

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X, y = select_features(df)
        model, _ = train_model(X, y, n_search_iter=3)

        assert model.n_features_in_ == X.shape[1]

    def test_prediction_returns_float(self):
        """Model.predict on a single row should return a numeric value."""
        from ml.train import select_features, train_model

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X, y = select_features(df)
        model, _ = train_model(X, y, n_search_iter=3)

        pred = model.predict(X.iloc[:1].values)
        assert len(pred) == 1
        assert np.isfinite(pred[0])


class TestSaveArtifacts:
    """Tests for model persistence."""

    def test_saves_model_and_columns(self, tmp_path):
        """save_artifacts writes adr_model.joblib and feature_columns.json."""
        from ml.train import select_features, train_model, save_artifacts

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X, y = select_features(df)
        model, _ = train_model(X, y, n_search_iter=3)

        save_artifacts(model, list(X.columns), output_dir=tmp_path)

        assert (tmp_path / "adr_model.joblib").exists()
        assert (tmp_path / "feature_columns.json").exists()

    def test_feature_columns_json_matches_model(self, tmp_path):
        """Saved feature_columns.json length must equal model.n_features_in_."""
        from ml.train import select_features, train_model, save_artifacts

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X, y = select_features(df)
        model, _ = train_model(X, y, n_search_iter=3)

        save_artifacts(model, list(X.columns), output_dir=tmp_path)

        with open(tmp_path / "feature_columns.json") as f:
            columns = json.load(f)

        assert len(columns) == model.n_features_in_

    def test_feature_columns_order_preserved(self, tmp_path):
        """Saved feature_columns.json must preserve the exact training column order."""
        from ml.train import select_features, train_model, save_artifacts

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X, y = select_features(df)
        model, _ = train_model(X, y, n_search_iter=3)

        original_columns = list(X.columns)
        save_artifacts(model, original_columns, output_dir=tmp_path)

        with open(tmp_path / "feature_columns.json") as f:
            loaded_columns = json.load(f)

        assert loaded_columns == original_columns

    def test_saved_model_loads_and_predicts(self, tmp_path):
        """Saved model should load and produce valid predictions."""
        import joblib

        from ml.train import select_features, train_model, save_artifacts

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X, y = select_features(df)
        model, _ = train_model(X, y, n_search_iter=3)

        save_artifacts(model, list(X.columns), output_dir=tmp_path)

        loaded_model = joblib.load(tmp_path / "adr_model.joblib")
        pred = loaded_model.predict(X.iloc[:1].values)
        assert np.isfinite(pred[0])


class TestDropCorrelated:
    """Tests for correlated feature dropping."""

    def test_drops_perfectly_correlated_column(self):
        """A duplicated SYSTEM_ column should be dropped."""
        from ml.train import drop_correlated

        df = _make_sample_df(n_rows=50, n_amenities=3)
        # Make SYSTEM_AMENITY_2 identical to SYSTEM_AMENITY_0
        df["SYSTEM_AMENITY_2"] = df["SYSTEM_AMENITY_0"]
        X = df[["capacity", "SYSTEM_AMENITY_0", "SYSTEM_AMENITY_1", "SYSTEM_AMENITY_2"]]

        result = drop_correlated(X, threshold=0.9)
        assert result.shape[1] < X.shape[1]
        assert "capacity" in result.columns  # numeric columns always kept

    def test_keeps_uncorrelated_columns(self):
        """Independent columns should all be retained."""
        from ml.train import drop_correlated

        rng = np.random.RandomState(99)
        data = {
            "SYSTEM_A": rng.choice([0, 1], 100),
            "SYSTEM_B": rng.choice([0, 1], 100),
        }
        X = pd.DataFrame(data)

        result = drop_correlated(X, threshold=0.9)
        assert result.shape[1] == 2

    def test_returns_unchanged_with_no_system_cols(self):
        """Non-SYSTEM columns should pass through untouched."""
        from ml.train import drop_correlated

        X = pd.DataFrame({"capacity": [1, 2, 3], "bedrooms": [1, 1, 2]})
        result = drop_correlated(X, threshold=0.9)
        pd.testing.assert_frame_equal(result, X)


class TestLogTransform:
    """Tests for log-transformed target in training."""

    def test_predictions_are_positive(self):
        """Inverse log-transform of model output should give positive dollar values."""
        from ml.train import select_features, train_model

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X, y = select_features(df)
        model, _ = train_model(X, y, n_search_iter=3)

        preds = np.expm1(model.predict(X))
        assert (preds > 0).all()

    def test_metrics_in_dollar_space(self):
        """CV RMSE should be in plausible dollar range, not log-space."""
        from ml.train import select_features, train_model

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X, y = select_features(df)
        _, metrics = train_model(X, y, n_search_iter=3)

        # Log-space RMSE would be ~0.1-1.0; dollar-space should be >1
        assert metrics["cv_rmse_mean"] > 1.0
        assert metrics["cv_mae_mean"] > 1.0
