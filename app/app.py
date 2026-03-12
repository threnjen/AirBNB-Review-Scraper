"""
Flask web application for ADR (Average Daily Rate) prediction.

Loads a pre-trained two-stage residual XGBoost model at startup and serves
an HTML form for interactive prediction based on property amenities and
characteristics.

Stage 1: Numeric features (capacity, bedrooms, beds, bathrooms, distance,
         per-person ratios) → ADR (log-transformed).
Stage 2: SYSTEM_* amenity features → Stage 1 residuals.
Combined prediction = Stage 1 + Stage 2.
"""

import json
import logging
from pathlib import Path

import joblib
import numpy as np
from flask import Flask, render_template, request

from app.system_labels import SYSTEM_LABEL_MAP
from utils.geo_utils import manhattan_surface_distance
from utils.tiny_file_handler import load_config

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent / "ml" / "model" / "residual"

# User-facing input fields (shown in the form).
NUMERIC_FEATURES = [
    "capacity",
    "bedrooms",
    "beds",
    "bathrooms",
    "latitude",
    "longitude",
]

NUMERIC_RANGES = {
    "capacity": (1, 50, "1–50 guests"),
    "bedrooms": (0, 20, "0–20"),
    "beds": (0, 50, "0–50"),
    "bathrooms": (0, 20, "0–20"),
    "latitude": (-90, 90, "-90 to 90"),
    "longitude": (-180, 180, "-180 to 180"),
}

# Load POI coordinates from config for DIST_TO_POI calculation.
_config = load_config()
POI_LAT = _config["poi_lat"]
POI_LONG = _config["poi_long"]
ZONE_NAME = _config["search_zone_name"].replace("_", " ").title()

# Amenity categories for grouping checkboxes in the UI.
# Keys are display names; values are lists of SYSTEM_ column names.
# Order matches SYSTEM_LABEL_MAP categories in system_labels.py.
AMENITY_CATEGORIES = {
    "Bathroom": [
        "SYSTEM_BATHTUB",
        "SYSTEM_HAIRDRYER",
        "SYSTEM_SHAMPOO",
        "SYSTEM_SOAP",
        "SYSTEM_HOT_WATER",
        "SYSTEM_TOILETRIES",
        "SYSTEM_SHOWER",
        "SYSTEM_TOILET_BIDET",
    ],
    "Bedroom & Sleep": [
        "SYSTEM_BLANKETS",
        "SYSTEM_PILLOW",
        "SYSTEM_BLACKOUT_SHADES",
        "SYSTEM_WARDROBE",
    ],
    "Kitchen & Dining": [
        "SYSTEM_MINI_BAR",
        "SYSTEM_MICROWAVE",
        "SYSTEM_DISHWASHER",
        "SYSTEM_STOVE",
        "SYSTEM_OVEN",
        "SYSTEM_TOASTER",
        "SYSTEM_BLENDER",
        "SYSTEM_RICE_COOKER",
        "SYSTEM_BAKING_SHEET",
        "SYSTEM_WATER_KETTLE",
        "SYSTEM_DISHES_AND_SILVERWARE",
        "SYSTEM_DINING_TABLE",
        "SYSTEM_CHILD_UTENSILS",
    ],
    "Laundry & Cleaning": [
        "SYSTEM_IRON",
        "SYSTEM_HANGERS",
        "SYSTEM_WASHER",
        "SYSTEM_DRYER",
        "SYSTEM_LAUNDRY_SERVICE",
        "SYSTEM_CLEANING_SUPPLIES",
        "SYSTEM_CLEAN",
    ],
    "Climate & Comfort": [
        "SYSTEM_THERMOMETER",
        "SYSTEM_SNOWFLAKE",
        "SYSTEM_FAN_CEILING",
        "SYSTEM_FAN_PORTABLE",
    ],
    "Safety & Security": [
        "SYSTEM_DETECTOR_CO",
        "SYSTEM_FIRE_EXTINGUISHER",
        "SYSTEM_FIRST_AID_KIT",
        "SYSTEM_SURVEILLANCE",
        "SYSTEM_SAFE",
        "SYSTEM_FIREPLACE_GUARD",
        "SYSTEM_AV_VOLUME",
    ],
    "Tech & Work": [
        "SYSTEM_WORKSPACE",
        "SYSTEM_TV",
        "SYSTEM_CABLE",
        "SYSTEM_SPEAKERS",
    ],
    "Entertainment": [
        "SYSTEM_PING_PONG",
        "SYSTEM_ARCADE_MACHINE",
        "SYSTEM_CHESS",
        "SYSTEM_PIANO",
        "SYSTEM_POOL_TABLE",
        "SYSTEM_BOARD_GAMES",
        "SYSTEM_BOOK",
        "SYSTEM_RECORD_PLAYER",
        "SYSTEM_VIDEO_GAME",
        "SYSTEM_ANIME",
    ],
    "Children & Family": [
        "SYSTEM_CRIB",
        "SYSTEM_PACK_N_PLAY",
        "SYSTEM_OUTLET_COVER",
        "SYSTEM_BABY_GATE",
        "SYSTEM_HIGH_CHAIR",
        "SYSTEM_TOYS",
        "SYSTEM_PLAY_SLIDE",
    ],
    "Outdoor & Recreation": [
        "SYSTEM_PATIO_BALCONY",
        "SYSTEM_GRILL",
        "SYSTEM_FIREPIT",
        "SYSTEM_FIREPLACE",
        "SYSTEM_HAMMOCK",
        "SYSTEM_POOL",
        "SYSTEM_JACUZZI",
        "SYSTEM_GYM",
        "SYSTEM_BEACH",
        "SYSTEM_BIKE",
        "SYSTEM_SAUNA",
        "SYSTEM_SUN_DECK",
        "SYSTEM_ROOFTOP_DECK",
    ],
    "Views & Scenery": [
        "SYSTEM_VIEW_MOUNTAIN",
        "SYSTEM_VIEW_OCEAN",
        "SYSTEM_LAKE",
        "SYSTEM_GOLF",
        "SYSTEM_FLOWER",
    ],
    "Access & Check-in": [
        "SYSTEM_CHECK_IN",
        "SYSTEM_LOCK_ON_DOOR",
        "SYSTEM_BUZZER",
        "SYSTEM_DOOR",
        "SYSTEM_LUGGAGE_DROP",
        "SYSTEM_NO_PRIVATE_ENTRANCE",
        "SYSTEM_NO_STAIRS",
        "SYSTEM_EV_CHARGER",
    ],
    "House Rules": [
        "SYSTEM_NO_EVENTS",
        "SYSTEM_SMOKING_ALLOWED",
        "SYSTEM_PETS",
        "SYSTEM_CAMERA",
    ],
    "Checkout Instructions": [
        "SYSTEM_TOWEL",
        "SYSTEM_POWER_SWITCH",
        "SYSTEM_LOCK",
        "SYSTEM_HOST_OWNERS",
        "SYSTEM_TRASH",
    ],
}


def _load_artifacts(model_dir: Path):
    """Load both stage models and their feature columns from disk.

    Returns (stage1_model, stage1_columns, stage2_model, stage2_columns).
    """
    model_dir = Path(model_dir)

    s1_model = joblib.load(model_dir / "stage1_model.joblib")
    with open(model_dir / "stage1_feature_columns.json") as f:
        s1_cols = json.load(f)

    s2_model = joblib.load(model_dir / "stage2_model.joblib")
    with open(model_dir / "stage2_feature_columns.json") as f:
        s2_cols = json.load(f)

    if len(s1_cols) != s1_model.n_features_in_:
        raise ValueError(
            f"Stage 1 column count ({len(s1_cols)}) does not match "
            f"model expectation ({s1_model.n_features_in_}). "
            "Retrain the model to sync artifacts."
        )
    if len(s2_cols) != s2_model.n_features_in_:
        raise ValueError(
            f"Stage 2 column count ({len(s2_cols)}) does not match "
            f"model expectation ({s2_model.n_features_in_}). "
            "Retrain the model to sync artifacts."
        )

    return s1_model, s1_cols, s2_model, s2_cols


def _load_mae(model_dir: Path) -> float:
    """Load the combined test MAE from training_metrics.json."""
    with open(Path(model_dir) / "training_metrics.json") as f:
        metrics = json.load(f)
    return metrics["combined_test_mae"]


def _format_label(system_col: str) -> str:
    """Convert a SYSTEM_ icon key to a human-readable display label.

    Uses SYSTEM_LABEL_MAP for specific mappings sourced from Airbnb property data.
    Falls back to naive title-casing for any unknown keys.
    """
    return SYSTEM_LABEL_MAP.get(
        system_col,
        system_col.replace("SYSTEM_", "").replace("_", " ").title(),
    )


def _build_category_map(feature_columns: list[str]) -> dict[str, list[dict]]:
    """Build an ordered mapping of category → list of {col, label} for the template.

    Any SYSTEM_ column not in a predefined category goes into 'Other'.
    Columns not in feature_columns (dropped during training) are excluded.
    """
    feature_set = set(feature_columns)
    categorized = set()
    result = {}

    for category, cols in AMENITY_CATEGORIES.items():
        items = []
        for col in cols:
            if col in feature_set:
                items.append({"col": col, "label": _format_label(col)})
                categorized.add(col)
        if items:
            result[category] = items

    # Catch any SYSTEM_ columns not in any predefined category
    uncategorized = [
        {"col": c, "label": _format_label(c)}
        for c in feature_columns
        if c.startswith("SYSTEM_") and c not in categorized
    ]
    if uncategorized:
        result["Other"] = result.get("Other", []) + uncategorized

    return result


# Load both stage models at module scope (once at startup).
stage1_model, stage1_feature_columns, stage2_model, stage2_feature_columns = (
    _load_artifacts(MODEL_DIR)
)
category_map = _build_category_map(stage2_feature_columns)
MAE_DOLLARS = _load_mae(MODEL_DIR)

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    """Render the prediction form."""
    return render_template(
        "index.html",
        categories=category_map,
        numeric_features=NUMERIC_FEATURES,
        numeric_ranges=NUMERIC_RANGES,
        form_values={},
        form_submitted=False,
        prediction=None,
        mae_dollars=None,
        error=None,
        zone_name=ZONE_NAME,
    )


@app.route("/predict", methods=["POST"])
def predict():
    """Assemble feature vectors and return combined two-stage ADR prediction."""
    form_values = {}
    error = None
    prediction = None

    def _render_error(msg):
        return render_template(
            "index.html",
            categories=category_map,
            numeric_features=NUMERIC_FEATURES,
            numeric_ranges=NUMERIC_RANGES,
            form_values=form_values,
            form_submitted=True,
            prediction=None,
            mae_dollars=None,
            error=msg,
            zone_name=ZONE_NAME,
        )

    # Parse user-facing numeric inputs with validation
    numeric_vals = {}
    for col in NUMERIC_FEATURES:
        raw = request.form.get(col, "").strip()
        form_values[col] = raw
        if not raw:
            numeric_vals[col] = 0.0
            continue
        try:
            val = float(raw)
        except ValueError:
            return _render_error(
                f"Invalid value for {col}: '{raw}'. Please enter a number."
            )
        min_val, max_val, _ = NUMERIC_RANGES[col]
        if not (min_val <= val <= max_val):
            return _render_error(
                f"{col.title()} must be between {min_val} and {max_val}."
            )
        numeric_vals[col] = val

    # Compute derived features for Stage 1
    capacity = max(numeric_vals["capacity"], 1)
    derived = {
        "DIST_TO_POI": manhattan_surface_distance(
            numeric_vals["latitude"], numeric_vals["longitude"], POI_LAT, POI_LONG
        ),
        "BEDS_PER_PERSON": numeric_vals["beds"] / capacity,
        "BATHS_PER_PERSON": numeric_vals["bathrooms"] / capacity,
        "BEDROOMS_PER_PERSON": numeric_vals["bedrooms"] / capacity,
    }

    # Build Stage 1 feature vector (numeric features in training order)
    s1_features = []
    for col in stage1_feature_columns:
        if col in numeric_vals:
            s1_features.append(numeric_vals[col])
        elif col in derived:
            s1_features.append(derived[col])
    s1_array = np.array([s1_features], dtype=np.float64)

    # Record which checkboxes are checked (for form state preservation)
    for col in stage2_feature_columns:
        if request.form.get(col):
            form_values[col] = "on"

    # Build Stage 2 feature vector (amenity features in training order)
    s2_features = [
        1.0 if request.form.get(col) else 0.0 for col in stage2_feature_columns
    ]
    s2_array = np.array([s2_features], dtype=np.float64)

    try:
        # Stage 1 is log-transformed: apply expm1 to get dollar predictions
        s1_pred = np.expm1(stage1_model.predict(s1_array))[0]
        # Stage 2 predicts residuals in dollar space
        s2_pred = stage2_model.predict(s2_array)[0]
        combined = s1_pred + s2_pred
        prediction = f"${combined:,.2f}"
    except Exception as e:
        logger.exception("Prediction failed")
        error = f"Prediction error: {e}"

    return render_template(
        "index.html",
        categories=category_map,
        numeric_features=NUMERIC_FEATURES,
        numeric_ranges=NUMERIC_RANGES,
        form_values=form_values,
        form_submitted=True,
        prediction=prediction,
        mae_dollars=f"${MAE_DOLLARS:,.2f}" if prediction else None,
        error=error,
        zone_name=ZONE_NAME,
    )


if __name__ == "__main__":
    app.run(debug=True)
