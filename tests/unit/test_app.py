"""
Unit tests for app/app.py
"""

from unittest.mock import MagicMock

import numpy as np
import pytest


@pytest.fixture
def feature_columns():
    """Minimal feature columns list for testing."""
    return [
        "capacity",
        "bedrooms",
        "beds",
        "bathrooms",
        "SYSTEM_BATHTUB",
        "SYSTEM_POOL",
        "SYSTEM_WI_FI",
    ]


@pytest.fixture
def mock_model():
    """Mock XGBoost model that returns a fixed prediction."""
    model = MagicMock()
    model.predict.return_value = np.array([250.0])
    model.n_features_in_ = 7
    return model


@pytest.fixture
def app_client(feature_columns, mock_model):
    """Create a Flask test client with mocked model artifacts."""
    import app.app as app_module

    # Save originals and override module globals with test doubles
    original = (app_module.model, app_module.feature_columns, app_module.category_map)
    app_module.model = mock_model
    app_module.feature_columns = feature_columns
    app_module.category_map = app_module._build_category_map(feature_columns)

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client

    # Restore originals
    app_module.model, app_module.feature_columns, app_module.category_map = original


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
        for field in ["capacity", "bedrooms", "beds", "bathrooms"]:
            assert field in html

    def test_contains_amenity_checkboxes(self, app_client):
        """GET / should have checkboxes for SYSTEM_ features."""
        response = app_client.get("/")
        html = response.data.decode()
        assert "SYSTEM_BATHTUB" in html
        assert "SYSTEM_POOL" in html
        assert "SYSTEM_WI_FI" in html


class TestPostPredict:
    """Tests for POST /predict route."""

    def test_returns_200_with_prediction(self, app_client):
        """POST /predict with valid data should return 200 with a dollar amount."""
        response = app_client.post(
            "/predict",
            data={"capacity": "6", "bedrooms": "3", "beds": "4", "bathrooms": "2"},
        )
        assert response.status_code == 200
        assert b"$250.00" in response.data

    def test_missing_numeric_defaults_to_zero(self, app_client, mock_model):
        """POST /predict with missing numeric fields should not crash."""
        response = app_client.post("/predict", data={})
        assert response.status_code == 200

    def test_checked_amenity_becomes_one(self, app_client, mock_model):
        """Checked checkbox should produce value 1 in feature vector."""
        app_client.post(
            "/predict",
            data={
                "capacity": "4",
                "bedrooms": "2",
                "beds": "3",
                "bathrooms": "1",
                "SYSTEM_POOL": "on",
            },
        )
        # Inspect the array passed to model.predict
        call_args = mock_model.predict.call_args[0][0]
        # SYSTEM_POOL is at index 5 in feature_columns
        assert call_args[0][5] == 1.0

    def test_unchecked_amenity_becomes_zero(self, app_client, mock_model):
        """Unchecked checkbox should produce value 0 in feature vector."""
        app_client.post(
            "/predict",
            data={"capacity": "4", "bedrooms": "2", "beds": "3", "bathrooms": "1"},
        )
        call_args = mock_model.predict.call_args[0][0]
        # SYSTEM_POOL (index 5) not in form data → should be 0
        assert call_args[0][5] == 0.0

    def test_feature_vector_order_matches_columns(self, app_client, mock_model):
        """Feature vector must be assembled in feature_columns.json order."""
        app_client.post(
            "/predict",
            data={
                "capacity": "6",
                "bedrooms": "3",
                "beds": "4",
                "bathrooms": "2",
                "SYSTEM_BATHTUB": "on",
                "SYSTEM_WI_FI": "on",
            },
        )
        call_args = mock_model.predict.call_args[0][0]
        row = call_args[0]
        # Order: capacity=6, bedrooms=3, beds=4, bathrooms=2,
        #        SYSTEM_BATHTUB=1, SYSTEM_POOL=0, SYSTEM_WI_FI=1
        assert row[0] == 6.0  # capacity
        assert row[1] == 3.0  # bedrooms
        assert row[2] == 4.0  # beds
        assert row[3] == 2.0  # bathrooms
        assert row[4] == 1.0  # SYSTEM_BATHTUB (checked)
        assert row[5] == 0.0  # SYSTEM_POOL (unchecked)
        assert row[6] == 1.0  # SYSTEM_WI_FI (checked)

    def test_preserves_form_state_after_predict(self, app_client):
        """After POST, the form should show the values the user submitted."""
        response = app_client.post(
            "/predict",
            data={
                "capacity": "6",
                "bedrooms": "3",
                "beds": "4",
                "bathrooms": "2",
                "SYSTEM_POOL": "on",
            },
        )
        html = response.data.decode()
        # Numeric values preserved
        assert 'value="6"' in html
        assert 'value="3"' in html
        # Checked checkbox preserved
        assert "SYSTEM_POOL" in html

    def test_invalid_numeric_shows_error(self, app_client):
        """Non-numeric capacity should render a validation error, not crash."""
        response = app_client.post(
            "/predict",
            data={"capacity": "abc", "bedrooms": "2", "beds": "3", "bathrooms": "1"},
        )
        assert response.status_code == 200
        assert b"error" in response.data.lower() or b"invalid" in response.data.lower()
