"""Tests for DetailsFilesetBuilder reading from a comp_set file path."""

import json
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


class TestDetailsFilesetBuilderCompSetPath:
    """DetailsFilesetBuilder should accept and use a comp_set_filepath parameter."""

    def test_init_stores_comp_set_filepath(self):
        """The constructor stores the comp_set_filepath."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="outputs/02_comp_sets/comp_set_97067.json",
        )
        assert builder.comp_set_filepath == "outputs/02_comp_sets/comp_set_97067.json"

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


class TestCleanAmenitiesDfFiltering:
    """Tests for min_days_available row filtering in clean_amenities_df."""

    def test_filters_rows_below_min_days_available(self):
        """Rows with Days_Avail < min_days_available are dropped."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
            min_days_available=100,
        )
        df = pd.DataFrame(
            {
                "ADR": [150.0, 200.0, 180.0],
                "Days_Avail": [50, 100, 300],
                "capacity": [4, 6, 8],
            },
            index=["p1", "p2", "p3"],
        )
        result = builder.clean_amenities_df(df)
        assert "p1" not in result.index
        assert "p2" in result.index
        assert "p3" in result.index

    def test_keeps_rows_at_or_above_threshold(self):
        """Rows with Days_Avail >= min_days_available are kept."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
            min_days_available=100,
        )
        df = pd.DataFrame(
            {
                "ADR": [150.0, 200.0],
                "Days_Avail": [100, 365],
                "capacity": [4, 6],
            },
            index=["p1", "p2"],
        )
        result = builder.clean_amenities_df(df)
        assert len(result) == 2

    def test_zero_threshold_keeps_all_rows(self):
        """A threshold of 0 retains everything."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
            min_days_available=0,
        )
        df = pd.DataFrame(
            {
                "ADR": [150.0, 200.0],
                "Days_Avail": [0, 50],
                "capacity": [4, 6],
            },
            index=["p1", "p2"],
        )
        result = builder.clean_amenities_df(df)
        assert len(result) == 2

    def test_logs_filtered_count(self):
        """Filtering logs how many rows were removed."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
            min_days_available=100,
        )
        df = pd.DataFrame(
            {
                "ADR": [150.0, 200.0, 180.0],
                "Days_Avail": [50, 30, 300],
                "capacity": [4, 6, 8],
            },
            index=["p1", "p2", "p3"],
        )
        with patch("scraper.details_fileset_build.logger") as mock_logger:
            builder.clean_amenities_df(df)
        mock_logger.info.assert_any_call(
            "Filtered 2 listings with Days_Avail < 100 (1 remaining)"
        )

    def test_handles_missing_days_avail_column(self):
        """If Days_Avail column is absent, no filtering occurs."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
            min_days_available=100,
        )
        df = pd.DataFrame(
            {
                "ADR": [150.0, 200.0],
                "capacity": [4, 6],
            },
            index=["p1", "p2"],
        )
        result = builder.clean_amenities_df(df)
        assert len(result) == 2

    def test_init_stores_min_days_available(self):
        """Constructor stores the min_days_available parameter."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
            min_days_available=150,
        )
        assert builder.min_days_available == 150

    def test_init_default_min_days_available(self):
        """min_days_available defaults to 100."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
        )
        assert builder.min_days_available == 100


class TestHasAirdnaDataFlag:
    """Tests for the has_airdna_data flag set during build_fileset."""

    def test_flag_true_for_properties_in_comp_set(self, tmp_path):
        """Properties present in comp_set_data should have has_airdna_data=True."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        comp_set_data = {
            "111": {
                "ADR": 200.0,
                "Occupancy": 70,
                "Days_Available": 300,
                "Revenue": 60000.0,
            }
        }
        comp_set_file = tmp_path / "comp_set.json"
        comp_set_file.write_text(json.dumps(comp_set_data))

        details_dir = tmp_path / "details_scraped"
        details_dir.mkdir()
        (details_dir / "property_details_111.json").write_text(
            json.dumps(
                {
                    "room_type": "Entire home/apt",
                    "person_capacity": 6,
                    "rating": {},
                    "sub_description": {
                        "items": ["guests", "2 bedrooms", "3 beds", "1 baths"]
                    },
                    "amenities": [],
                    "house_rules": {},
                    "highlights": [],
                }
            )
        )

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath=str(comp_set_file),
        )

        with patch(
            "scraper.details_fileset_build.DETAILS_SCRAPED_DIR",
            str(details_dir),
        ):
            with patch("os.makedirs"):
                with patch("pandas.DataFrame.to_csv"):
                    builder.build_fileset()

        assert builder.property_details["111"]["has_airdna_data"] is True

    def test_flag_false_for_properties_not_in_comp_set(self, tmp_path):
        """Properties absent from comp_set_data should have has_airdna_data=False."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        comp_set_file = tmp_path / "comp_set.json"
        comp_set_file.write_text(json.dumps({}))

        details_dir = tmp_path / "details_scraped"
        details_dir.mkdir()
        (details_dir / "property_details_222.json").write_text(
            json.dumps(
                {
                    "room_type": "Entire home/apt",
                    "person_capacity": 4,
                    "rating": {},
                    "sub_description": {
                        "items": ["guests", "1 bedrooms", "2 beds", "1 baths"]
                    },
                    "amenities": [],
                    "house_rules": {},
                    "highlights": [],
                }
            )
        )

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath=str(comp_set_file),
        )

        with patch(
            "scraper.details_fileset_build.DETAILS_SCRAPED_DIR",
            str(details_dir),
        ):
            with patch("os.makedirs"):
                with patch("pandas.DataFrame.to_csv"):
                    builder.build_fileset()

        assert builder.property_details["222"].get("has_airdna_data") is not True
