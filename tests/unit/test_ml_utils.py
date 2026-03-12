"""
Unit tests for ml/ml_utils.py — shared training utilities.
"""

import json

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


class TestTrainModelLogTransform:
    """Tests for train_model with log_transform=True (default)."""

    def test_returns_model_and_metrics(self):
        from ml.ml_utils import NUMERIC_FEATURES, train_model

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X = df[NUMERIC_FEATURES]
        y = df["ADR"]
        model, metrics = train_model(X, y, n_search_iter=3, log_transform=True)

        assert hasattr(model, "predict")
        assert metrics["log_transform"] is True
        assert metrics["cv_rmse_mean"] > 1.0

    def test_predictions_are_positive_after_expm1(self):
        from ml.ml_utils import NUMERIC_FEATURES, train_model

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X = df[NUMERIC_FEATURES]
        y = df["ADR"]
        model, _ = train_model(X, y, n_search_iter=3, log_transform=True)

        preds = np.expm1(model.predict(X))
        assert (preds > 0).all()


class TestTrainModelNoLogTransform:
    """Tests for train_model with log_transform=False (for residuals)."""

    def test_returns_model_and_metrics(self):
        from ml.ml_utils import train_model

        rng = np.random.RandomState(42)
        X = pd.DataFrame(
            {
                "SYSTEM_A": rng.choice([0, 1], 50),
                "SYSTEM_B": rng.choice([0, 1], 50),
            }
        )
        # Residuals can be negative
        y = pd.Series(rng.normal(0, 50, 50))
        model, metrics = train_model(X, y, n_search_iter=3, log_transform=False)

        assert hasattr(model, "predict")
        assert metrics["log_transform"] is False

    def test_predictions_in_original_space(self):
        from ml.ml_utils import train_model

        rng = np.random.RandomState(42)
        X = pd.DataFrame(
            {
                "SYSTEM_A": rng.choice([0, 1], 50),
                "SYSTEM_B": rng.choice([0, 1], 50),
            }
        )
        y = pd.Series(rng.normal(0, 50, 50))
        model, _ = train_model(X, y, n_search_iter=3, log_transform=False)

        preds = model.predict(X)
        assert np.isfinite(preds).all()


class TestSaveArtifacts:
    """Tests for save_artifacts with custom filenames."""

    def test_saves_with_default_filenames(self, tmp_path):
        from ml.ml_utils import NUMERIC_FEATURES, train_model, save_artifacts

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X = df[NUMERIC_FEATURES]
        y = df["ADR"]
        model, _ = train_model(X, y, n_search_iter=3)

        save_artifacts(model, list(X.columns), output_dir=tmp_path)

        assert (tmp_path / "adr_model.joblib").exists()
        assert (tmp_path / "feature_columns.json").exists()

    def test_saves_with_custom_filenames(self, tmp_path):
        from ml.ml_utils import NUMERIC_FEATURES, train_model, save_artifacts

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X = df[NUMERIC_FEATURES]
        y = df["ADR"]
        model, _ = train_model(X, y, n_search_iter=3)

        save_artifacts(
            model,
            list(X.columns),
            output_dir=tmp_path,
            model_filename="stage1_model.joblib",
            columns_filename="stage1_feature_columns.json",
        )

        assert (tmp_path / "stage1_model.joblib").exists()
        assert (tmp_path / "stage1_feature_columns.json").exists()

    def test_feature_columns_json_content_matches(self, tmp_path):
        from ml.ml_utils import NUMERIC_FEATURES, train_model, save_artifacts

        df = _make_sample_df(n_rows=50, n_amenities=5)
        X = df[NUMERIC_FEATURES]
        y = df["ADR"]
        model, _ = train_model(X, y, n_search_iter=3)

        cols = list(X.columns)
        save_artifacts(model, cols, output_dir=tmp_path)

        with open(tmp_path / "feature_columns.json") as f:
            loaded = json.load(f)
        assert loaded == cols


class TestDropCorrelated:
    """Tests for drop_correlated (now in ml_utils)."""

    def test_drops_perfectly_correlated_column(self):
        from ml.ml_utils import drop_correlated

        df = _make_sample_df(n_rows=50, n_amenities=3)
        df["SYSTEM_AMENITY_2"] = df["SYSTEM_AMENITY_0"]
        X = df[["capacity", "SYSTEM_AMENITY_0", "SYSTEM_AMENITY_1", "SYSTEM_AMENITY_2"]]

        result = drop_correlated(X, threshold=0.9)
        assert result.shape[1] < X.shape[1]
        assert "capacity" in result.columns

    def test_keeps_uncorrelated_columns(self):
        from ml.ml_utils import drop_correlated

        rng = np.random.RandomState(99)
        X = pd.DataFrame(
            {
                "SYSTEM_A": rng.choice([0, 1], 100),
                "SYSTEM_B": rng.choice([0, 1], 100),
            }
        )

        result = drop_correlated(X, threshold=0.9)
        assert result.shape[1] == 2


class TestPruneZeroImportance:
    """Tests for prune_zero_importance."""

    def test_returns_subset_of_columns(self):
        from ml.ml_utils import prune_zero_importance

        rng = np.random.RandomState(42)
        X = pd.DataFrame(
            {
                "useful": rng.uniform(0, 100, 50),
                "SYSTEM_NOISE": rng.choice([0, 1], 50),
            }
        )
        y = pd.Series(X["useful"] * 2 + rng.normal(0, 1, 50))

        keep = prune_zero_importance(
            X, y, {"n_estimators": 50, "max_depth": 2, "learning_rate": 0.1}
        )
        assert "useful" in keep
        assert isinstance(keep, list)
