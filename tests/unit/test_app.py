"""
Unit tests for app/app.py — two-stage residual model.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture
def stage1_feature_columns():
    """Stage 1 numeric feature columns (matches ml_utils.NUMERIC_FEATURES)."""
    return [
        "capacity",
        "bedrooms",
        "beds",
        "bathrooms",
        "DIST_TO_POI",
        "BEDS_PER_PERSON",
        "BATHS_PER_PERSON",
        "BEDROOMS_PER_PERSON",
    ]


@pytest.fixture
def stage2_feature_columns():
    """Stage 2 amenity feature columns."""
    return ["SYSTEM_BATHTUB", "SYSTEM_POOL", "SYSTEM_WI_FI"]


@pytest.fixture
def mock_stage1_model():
    """Mock Stage 1 model (log-transformed output: expm1 applied by app)."""
    model = MagicMock()
    # Return log1p(200) so that expm1 gives ~200
    model.predict.return_value = np.log1p(np.array([200.0]))
    model.n_features_in_ = 8
    return model


@pytest.fixture
def mock_stage2_model():
    """Mock Stage 2 model (residuals in dollar space)."""
    model = MagicMock()
    model.predict.return_value = np.array([50.0])
    model.n_features_in_ = 3
    return model


@pytest.fixture
def app_client(
    stage1_feature_columns,
    stage2_feature_columns,
    mock_stage1_model,
    mock_stage2_model,
):
    """Create a Flask test client with mocked two-stage model artifacts."""
    import app.app as app_module

    original = (
        app_module.stage1_model,
        app_module.stage1_feature_columns,
        app_module.stage2_model,
        app_module.stage2_feature_columns,
        app_module.category_map,
        app_module.MAE_DOLLARS,
    )
    app_module.stage1_model = mock_stage1_model
    app_module.stage1_feature_columns = stage1_feature_columns
    app_module.stage2_model = mock_stage2_model
    app_module.stage2_feature_columns = stage2_feature_columns
    app_module.category_map = app_module._build_category_map(stage2_feature_columns)
    app_module.MAE_DOLLARS = 30.0

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client

    (
        app_module.stage1_model,
        app_module.stage1_feature_columns,
        app_module.stage2_model,
        app_module.stage2_feature_columns,
        app_module.category_map,
        app_module.MAE_DOLLARS,
    ) = original


class TestGetIndex:
    """Tests for GET / route."""

    def test_returns_200(self, app_client):
        """GET / should return 200 OK."""
        response = app_client.get("/")
        assert response.status_code == 200

    def test_contains_form(self, app_client):
        """GET / should render an HTML form."""
        response = app_client.get("/")
        assert b"<form" in response.data

    def test_contains_numeric_inputs(self, app_client):
        """GET / should have inputs for numeric features."""
        response = app_client.get("/")
        html = response.data.decode()
        for field in [
            "capacity",
            "bedrooms",
            "beds",
            "bathrooms",
            "latitude",
            "longitude",
        ]:
            assert field in html

    def test_contains_amenity_checkboxes(self, app_client):
        """GET / should have checkboxes for SYSTEM_ features."""
        response = app_client.get("/")
        html = response.data.decode()
        assert "SYSTEM_BATHTUB" in html
        assert "SYSTEM_POOL" in html
        assert "SYSTEM_WI_FI" in html

    def test_all_checkboxes_checked_by_default(self, app_client):
        """GET / should render all amenity checkboxes pre-checked."""
        response = app_client.get("/")
        html = response.data.decode()
        # All three amenities in our fixture should appear checked
        assert html.count("checked") == 3


class TestPostPredict:
    """Tests for POST /predict route."""

    def test_returns_200_with_prediction(self, app_client):
        """POST /predict with valid data should return 200 with combined prediction and MAE."""
        response = app_client.post(
            "/predict",
            data={
                "capacity": "6",
                "bedrooms": "3",
                "beds": "4",
                "bathrooms": "2",
                "latitude": "45.3",
                "longitude": "-121.8",
            },
        )
        assert response.status_code == 200
        # Combined prediction: expm1(log1p(200)) + 50 = 200 + 50 = 250
        assert b"$250.00" in response.data
        # MAE range should also appear
        assert b"$30.00" in response.data

    def test_missing_numeric_defaults_to_zero(self, app_client, mock_stage1_model):
        """POST /predict with missing numeric fields should not crash."""
        response = app_client.post("/predict", data={})
        assert response.status_code == 200

    def test_checked_amenity_becomes_one(self, app_client, mock_stage2_model):
        """Checked checkbox should produce value 1 in stage 2 feature vector."""
        app_client.post(
            "/predict",
            data={
                "capacity": "4",
                "bedrooms": "2",
                "beds": "3",
                "bathrooms": "1",
                "latitude": "45.3",
                "longitude": "-121.8",
                "SYSTEM_POOL": "on",
            },
        )
        call_args = mock_stage2_model.predict.call_args[0][0]
        # SYSTEM_POOL is at index 1 in stage2_feature_columns
        assert call_args[0][1] == 1.0

    def test_unchecked_amenity_becomes_zero(self, app_client, mock_stage2_model):
        """Unchecked checkbox should produce value 0 in stage 2 feature vector."""
        app_client.post(
            "/predict",
            data={
                "capacity": "4",
                "bedrooms": "2",
                "beds": "3",
                "bathrooms": "1",
                "latitude": "45.3",
                "longitude": "-121.8",
            },
        )
        call_args = mock_stage2_model.predict.call_args[0][0]
        # SYSTEM_POOL (index 1) not in form data → should be 0
        assert call_args[0][1] == 0.0

    def test_stage1_feature_vector_order(self, app_client, mock_stage1_model):
        """Stage 1 feature vector must contain numeric + derived features in order."""
        app_client.post(
            "/predict",
            data={
                "capacity": "6",
                "bedrooms": "3",
                "beds": "4",
                "bathrooms": "2",
                "latitude": "45.3",
                "longitude": "-121.8",
            },
        )
        call_args = mock_stage1_model.predict.call_args[0][0]
        row = call_args[0]
        assert row[0] == 6.0  # capacity
        assert row[1] == 3.0  # bedrooms
        assert row[2] == 4.0  # beds
        assert row[3] == 2.0  # bathrooms
        assert row[4] > 0  # DIST_TO_POI (computed from lat/long)
        assert row[5] == pytest.approx(4.0 / 6.0)  # BEDS_PER_PERSON
        assert row[6] == pytest.approx(2.0 / 6.0)  # BATHS_PER_PERSON
        assert row[7] == pytest.approx(3.0 / 6.0)  # BEDROOMS_PER_PERSON

    def test_stage2_feature_vector_order(self, app_client, mock_stage2_model):
        """Stage 2 feature vector must match amenity column order."""
        app_client.post(
            "/predict",
            data={
                "capacity": "6",
                "bedrooms": "3",
                "beds": "4",
                "bathrooms": "2",
                "latitude": "45.3",
                "longitude": "-121.8",
                "SYSTEM_BATHTUB": "on",
                "SYSTEM_WI_FI": "on",
            },
        )
        call_args = mock_stage2_model.predict.call_args[0][0]
        row = call_args[0]
        assert row[0] == 1.0  # SYSTEM_BATHTUB (checked)
        assert row[1] == 0.0  # SYSTEM_POOL (unchecked)
        assert row[2] == 1.0  # SYSTEM_WI_FI (checked)

    def test_preserves_form_state_after_predict(self, app_client):
        """After POST, checked boxes stay checked and unchecked boxes stay unchecked."""
        response = app_client.post(
            "/predict",
            data={
                "capacity": "6",
                "bedrooms": "3",
                "beds": "4",
                "bathrooms": "2",
                "latitude": "45.3",
                "longitude": "-121.8",
                "SYSTEM_POOL": "on",
                # SYSTEM_BATHTUB and SYSTEM_WI_FI intentionally omitted (unchecked)
            },
        )
        html = response.data.decode()
        assert 'value="6"' in html
        assert 'value="3"' in html
        # Only SYSTEM_POOL was checked — exactly 1 checkbox should be checked
        assert html.count("checked") == 1

    def test_invalid_numeric_shows_error(self, app_client):
        """Non-numeric capacity should render a validation error, not crash."""
        response = app_client.post(
            "/predict",
            data={"capacity": "abc", "bedrooms": "2", "beds": "3", "bathrooms": "1"},
        )
        assert response.status_code == 200
        assert b"error" in response.data.lower() or b"invalid" in response.data.lower()
