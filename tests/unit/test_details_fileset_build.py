"""Tests for DetailsFilesetBuilder reading from a comp_set file path."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest


class TestDetailsFilesetBuilderCompSetPath:
    """DetailsFilesetBuilder should accept and use a comp_set_filepath parameter."""

    def test_init_stores_comp_set_filepath(self):
        """The constructor stores the comp_set_filepath."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="outputs/01_comp_sets/comp_set_97067.json",
        )
        assert builder.comp_set_filepath == "outputs/01_comp_sets/comp_set_97067.json"

    def test_build_fileset_reads_comp_set_file(self, tmp_path):
        """build_fileset reads properties from the comp_set_filepath."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        # Create a comp_set file with one property
        comp_set_data = {
            "12345": {
                "ADR": 150.0,
                "Occupancy": 60,
                "Days_Available": 300,
                "Revenue": 50000.0,
                "Bedrooms": 3,
                "Bathrooms": 2.0,
                "Max_Guests": 8,
                "LY_Revenue": 45000.0,
                "Rating": 4.5,
                "Review_Count": 20,
            }
        }
        comp_set_file = tmp_path / "comp_set_97067.json"
        comp_set_file.write_text(json.dumps(comp_set_data))

        # Create a minimal property details file in the expected location
        details_dir = tmp_path / "details_scraped"
        details_dir.mkdir()
        property_details = {
            "room_type": "Entire home",
            "person_capacity": 8,
            "bedrooms": 3,
            "beds": 4,
            "bathrooms": 2.0,
            "rating": 4.5,
            "review_count": 20,
            "amenities": [],
            "house_rules": {},
            "highlights": [],
        }
        (details_dir / "property_details_12345.json").write_text(
            json.dumps(property_details)
        )

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath=str(comp_set_file),
        )

        # Patch the details directory to point at our tmp_path
        with patch(
            "scraper.details_fileset_build.DETAILS_SCRAPED_DIR",
            str(details_dir),
            create=True,
        ):
            with patch("os.makedirs"):
                with patch("pandas.DataFrame.to_csv"):
                    builder.build_fileset()

        assert "12345" in builder.property_details
        assert builder.property_details["12345"]["ADR"] == 150.0

    def test_build_fileset_logs_missing_comp_set(self, tmp_path):
        """build_fileset logs when no detail files exist and comp_set is missing."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath=str(tmp_path / "nonexistent.json"),
        )

        empty_details_dir = str(tmp_path / "empty_details")
        os.makedirs(empty_details_dir, exist_ok=True)

        with patch("scraper.details_fileset_build.logger") as mock_logger:
            with patch(
                "scraper.details_fileset_build.DETAILS_SCRAPED_DIR",
                empty_details_dir,
                create=True,
            ):
                builder.build_fileset()

        mock_logger.info.assert_any_call(
            "No property detail files found in the directory."
        )
