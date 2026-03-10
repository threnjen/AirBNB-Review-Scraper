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
            comp_set_filepath="outputs/03_airdna_data/comp_set_97067.json",
        )
        assert builder.comp_set_filepath == "outputs/03_airdna_data/comp_set_97067.json"

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
        (details_dir / "00000").mkdir()
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
        (details_dir / "00000" / "property_details_12345.json").write_text(
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
            with patch("pandas.DataFrame.to_csv"):
                with patch("scraper.details_fileset_build.json.dump"):
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
        os.makedirs(os.path.join(empty_details_dir, "00000"), exist_ok=True)

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
        (details_dir / "00000").mkdir()
        (details_dir / "00000" / "property_details_111.json").write_text(
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
            with patch("pandas.DataFrame.to_csv"):
                with patch("scraper.details_fileset_build.json.dump"):
                    builder.build_fileset()

        assert builder.property_details["111"]["has_airdna_data"] is True

    def test_flag_false_for_properties_not_in_comp_set(self, tmp_path):
        """Properties absent from comp_set_data should have has_airdna_data=False."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        comp_set_file = tmp_path / "comp_set.json"
        comp_set_file.write_text(json.dumps({}))

        details_dir = tmp_path / "details_scraped"
        details_dir.mkdir()
        (details_dir / "00000").mkdir()
        (details_dir / "00000" / "property_details_222.json").write_text(
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
            with patch("pandas.DataFrame.to_csv"):
                with patch("scraper.details_fileset_build.json.dump"):
                    builder.build_fileset()

        assert builder.property_details["222"].get("has_airdna_data") is not True


class TestEngineeredPerPersonFeatures:
    """Tests for BEDS_PER_PERSON, BATHS_PER_PERSON, BEDROOMS_PER_PERSON in clean_amenities_df."""

    def test_computes_per_person_features(self):
        """Per-person ratios are computed correctly from beds/bathrooms/bedrooms ÷ capacity."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
        )
        df = pd.DataFrame(
            {
                "ADR": [200.0, 300.0],
                "capacity": [4, 8],
                "beds": [2, 6],
                "bathrooms": [1.0, 3.0],
                "bedrooms": [1, 4],
            },
            index=["p1", "p2"],
        )
        result = builder.clean_amenities_df(df)

        assert result.loc["p1", "BEDS_PER_PERSON"] == 0.5
        assert result.loc["p2", "BEDS_PER_PERSON"] == 0.75
        assert result.loc["p1", "BATHS_PER_PERSON"] == 0.25
        assert result.loc["p2", "BATHS_PER_PERSON"] == 0.38
        assert result.loc["p1", "BEDROOMS_PER_PERSON"] == 0.25
        assert result.loc["p2", "BEDROOMS_PER_PERSON"] == 0.5

    def test_zero_capacity_produces_nan(self):
        """Properties with capacity=0 should get NaN for per-person features."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
            min_days_available=0,
        )
        df = pd.DataFrame(
            {
                "ADR": [200.0],
                "capacity": [0],
                "beds": [2],
                "bathrooms": [1.0],
                "bedrooms": [1],
            },
            index=["p1"],
        )
        result = builder.clean_amenities_df(df)

        assert pd.isna(result.loc["p1", "BEDS_PER_PERSON"])
        assert pd.isna(result.loc["p1", "BATHS_PER_PERSON"])
        assert pd.isna(result.loc["p1", "BEDROOMS_PER_PERSON"])


class TestParseBasicDetailsSubDetails:
    """parse_basic_details must not crash on short or empty sub_details arrays."""

    @pytest.fixture
    def builder(self):
        from scraper.details_fileset_build import DetailsFilesetBuilder

        b = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
        )
        b.property_details["P1"] = {}
        return b

    def _make_details(self, items):
        return {
            "room_type": "Entire home/apt",
            "person_capacity": 4,
            "rating": {},
            "sub_description": {"items": items},
            "house_rules": {},
            "location_descriptions": [],
            "description": [],
        }

    def test_empty_sub_details(self, builder):
        """Empty sub_details list should not raise."""
        result = builder.parse_basic_details("P1", self._make_details([]))
        assert result is True
        assert "bedrooms" not in builder.property_details["P1"]
        assert "beds" not in builder.property_details["P1"]
        assert "bathrooms" not in builder.property_details["P1"]

    def test_single_element_sub_details(self, builder):
        """sub_details with only 1 element should not raise."""
        result = builder.parse_basic_details("P1", self._make_details(["4 guests"]))
        assert result is True

    def test_two_element_sub_details_with_bedrooms(self, builder):
        """sub_details with 2 elements should parse bedrooms if present."""
        result = builder.parse_basic_details(
            "P1", self._make_details(["4 guests", "2 bedrooms"])
        )
        assert result is True
        assert builder.property_details["P1"]["bedrooms"] == "2"

    def test_beds_without_baths(self, builder):
        """sub_details = ['guests', 'bed', '3 beds'] must not crash on missing baths."""
        result = builder.parse_basic_details(
            "P1", self._make_details(["4 guests", "Studio", "3 beds"])
        )
        assert result is True
        assert builder.property_details["P1"]["beds"] == "3"
        assert "bathrooms" not in builder.property_details["P1"]

    def test_full_sub_details(self, builder):
        """Normal 4-element sub_details parses all fields."""
        result = builder.parse_basic_details(
            "P1", self._make_details(["4 guests", "2 bedrooms", "3 beds", "1.5 baths"])
        )
        assert result is True
        assert builder.property_details["P1"]["bedrooms"] == "2"
        assert builder.property_details["P1"]["beds"] == "3"
        assert builder.property_details["P1"]["bathrooms"] == "1.5"


class TestCoordinatesAndDistToPoi:
    """Tests for lat/lng extraction and DIST_TO_POI calculation."""

    def _make_property_json(self, lat=None, lon=None):
        """Minimal property details JSON with optional coordinates."""
        data = {
            "room_type": "Entire home/apt",
            "person_capacity": 6,
            "rating": {},
            "sub_description": {
                "items": ["6 guests", "2 bedrooms", "3 beds", "1 baths"]
            },
            "amenities": [],
            "house_rules": {},
            "highlights": [],
            "location_descriptions": [],
            "description": [],
        }
        if lat is not None and lon is not None:
            data["coordinates"] = {"latitude": lat, "longitude": lon}
        return data

    def test_coordinates_extracted_into_property_details(self, tmp_path):
        """build_fileset should store latitude and longitude from JSON."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        comp_set_file = tmp_path / "comp_set.json"
        comp_set_file.write_text(json.dumps({}))

        details_dir = tmp_path / "details"
        (details_dir / "zone1").mkdir(parents=True)
        (details_dir / "zone1" / "property_details_100.json").write_text(
            json.dumps(self._make_property_json(lat=45.37, lon=-121.91))
        )

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath=str(comp_set_file),
            zone_name="zone1",
            poi_lat=45.31,
            poi_long=-121.83,
        )
        with patch(
            "scraper.details_fileset_build.DETAILS_SCRAPED_DIR", str(details_dir)
        ):
            with patch("pandas.DataFrame.to_csv"):
                with patch("scraper.details_fileset_build.json.dump"):
                    builder.build_fileset()

        assert builder.property_details["100"]["latitude"] == 45.37
        assert builder.property_details["100"]["longitude"] == -121.91

    def test_dist_to_poi_calculated_when_poi_and_coords_present(self, tmp_path):
        """DIST_TO_POI should be a positive float when POI and coords exist."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        comp_set_file = tmp_path / "comp_set.json"
        comp_set_file.write_text(json.dumps({}))

        details_dir = tmp_path / "details"
        (details_dir / "zone1").mkdir(parents=True)
        (details_dir / "zone1" / "property_details_100.json").write_text(
            json.dumps(self._make_property_json(lat=45.37, lon=-121.91))
        )

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath=str(comp_set_file),
            zone_name="zone1",
            poi_lat=45.31,
            poi_long=-121.83,
        )
        with patch(
            "scraper.details_fileset_build.DETAILS_SCRAPED_DIR", str(details_dir)
        ):
            with patch("pandas.DataFrame.to_csv"):
                with patch("scraper.details_fileset_build.json.dump"):
                    builder.build_fileset()

        dist = builder.property_details["100"]["DIST_TO_POI"]
        assert isinstance(dist, float)
        assert dist > 0

    def test_missing_coordinates_yields_none(self, tmp_path):
        """Properties without coordinates should have None lat/lng and DIST_TO_POI."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        comp_set_file = tmp_path / "comp_set.json"
        comp_set_file.write_text(json.dumps({}))

        details_dir = tmp_path / "details"
        (details_dir / "zone1").mkdir(parents=True)
        (details_dir / "zone1" / "property_details_200.json").write_text(
            json.dumps(self._make_property_json())  # no coordinates
        )

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath=str(comp_set_file),
            zone_name="zone1",
            poi_lat=45.31,
            poi_long=-121.83,
        )
        with patch(
            "scraper.details_fileset_build.DETAILS_SCRAPED_DIR", str(details_dir)
        ):
            with patch("pandas.DataFrame.to_csv"):
                with patch("scraper.details_fileset_build.json.dump"):
                    builder.build_fileset()

        assert builder.property_details["200"]["latitude"] is None
        assert builder.property_details["200"]["longitude"] is None
        assert builder.property_details["200"]["DIST_TO_POI"] is None

    def test_no_poi_configured_yields_none_dist(self, tmp_path):
        """Without poi_lat/poi_long, DIST_TO_POI should be None."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        comp_set_file = tmp_path / "comp_set.json"
        comp_set_file.write_text(json.dumps({}))

        details_dir = tmp_path / "details"
        (details_dir / "zone1").mkdir(parents=True)
        (details_dir / "zone1" / "property_details_300.json").write_text(
            json.dumps(self._make_property_json(lat=45.37, lon=-121.91))
        )

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath=str(comp_set_file),
            zone_name="zone1",
        )
        with patch(
            "scraper.details_fileset_build.DETAILS_SCRAPED_DIR", str(details_dir)
        ):
            with patch("pandas.DataFrame.to_csv"):
                with patch("scraper.details_fileset_build.json.dump"):
                    builder.build_fileset()

        assert builder.property_details["300"]["latitude"] == 45.37
        assert builder.property_details["300"]["DIST_TO_POI"] is None

    def test_dist_to_poi_not_dropped_by_clean(self):
        """clean_amenities_df should preserve DIST_TO_POI column."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
        )
        df = pd.DataFrame(
            {
                "ADR": [150.0],
                "DIST_TO_POI": [5.3],
                "latitude": [45.37],
                "longitude": [-121.91],
                "capacity": [4],
            },
            index=["p1"],
        )
        result = builder.clean_amenities_df(df)
        assert "DIST_TO_POI" in result.columns
        assert "latitude" in result.columns
        assert "longitude" in result.columns

    def test_dist_to_poi_coerced_to_float(self):
        """clean_amenities_df should coerce DIST_TO_POI to float."""
        from scraper.details_fileset_build import DetailsFilesetBuilder

        builder = DetailsFilesetBuilder(
            use_categoricals=False,
            comp_set_filepath="unused.json",
        )
        df = pd.DataFrame(
            {
                "ADR": [150.0],
                "DIST_TO_POI": ["5.3"],
                "capacity": [4],
            },
            index=["p1"],
        )
        result = builder.clean_amenities_df(df)
        assert result["DIST_TO_POI"].dtype == float
