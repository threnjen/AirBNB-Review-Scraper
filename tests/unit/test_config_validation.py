"""Unit tests for validate_config() in utils/tiny_file_handler.py."""

import pytest

from utils.tiny_file_handler import validate_config

VALID_CONFIG = {
    "search_zone_name": "mt_hood_corridor",
    "start_lat": 45.33,
    "start_long": -121.87,
    "search_radius_miles": 25.0,
}


class TestValidateConfig:
    """validate_config raises ValueError on invalid input, passes on valid."""

    def test_valid_config_passes(self):
        validate_config(VALID_CONFIG)  # should not raise

    def test_zone_name_missing_raises(self):
        cfg = {k: v for k, v in VALID_CONFIG.items() if k != "search_zone_name"}
        with pytest.raises(ValueError, match="search_zone_name"):
            validate_config(cfg)

    def test_zone_name_empty_raises(self):
        cfg = {**VALID_CONFIG, "search_zone_name": ""}
        with pytest.raises(ValueError, match="search_zone_name"):
            validate_config(cfg)

    def test_zone_name_with_slash_raises(self):
        """Path separator is not allowed in filesystem-safe name."""
        cfg = {**VALID_CONFIG, "search_zone_name": "mt_hood/corridor"}
        with pytest.raises(ValueError, match="search_zone_name"):
            validate_config(cfg)

    def test_zone_name_with_space_raises(self):
        cfg = {**VALID_CONFIG, "search_zone_name": "mt hood"}
        with pytest.raises(ValueError, match="search_zone_name"):
            validate_config(cfg)

    def test_zone_name_alphanumeric_underscore_hyphen_passes(self):
        cfg = {**VALID_CONFIG, "search_zone_name": "zone-123_abc"}
        validate_config(cfg)  # should not raise

    def test_start_lat_missing_raises(self):
        cfg = {k: v for k, v in VALID_CONFIG.items() if k != "start_lat"}
        with pytest.raises(ValueError, match="start_lat"):
            validate_config(cfg)

    def test_start_long_missing_raises(self):
        cfg = {k: v for k, v in VALID_CONFIG.items() if k != "start_long"}
        with pytest.raises(ValueError, match="start_long"):
            validate_config(cfg)

    def test_start_lat_not_float_raises(self):
        cfg = {**VALID_CONFIG, "start_lat": "not_a_float"}
        with pytest.raises(ValueError, match="start_lat"):
            validate_config(cfg)

    def test_start_long_not_float_raises(self):
        cfg = {**VALID_CONFIG, "start_long": "bad"}
        with pytest.raises(ValueError, match="start_long"):
            validate_config(cfg)

    def test_search_radius_missing_raises(self):
        cfg = {k: v for k, v in VALID_CONFIG.items() if k != "search_radius_miles"}
        with pytest.raises(ValueError, match="search_radius_miles"):
            validate_config(cfg)

    def test_search_radius_zero_raises(self):
        cfg = {**VALID_CONFIG, "search_radius_miles": 0}
        with pytest.raises(ValueError, match="search_radius_miles"):
            validate_config(cfg)

    def test_search_radius_negative_raises(self):
        cfg = {**VALID_CONFIG, "search_radius_miles": -5}
        with pytest.raises(ValueError, match="search_radius_miles"):
            validate_config(cfg)

    def test_search_radius_string_float_passes(self):
        """Numeric strings should be accepted (JSON may parse as string)."""
        cfg = {**VALID_CONFIG, "search_radius_miles": "25.0"}
        validate_config(cfg)  # should not raise
