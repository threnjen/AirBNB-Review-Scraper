"""Tests for compile_comp_sets() in main.py — merging per-listing JSON files
into a single master comp_set_{zipcode}.json file."""

import json
import os
from unittest.mock import patch

import pytest


class TestCompileCompSets:
    """Tests for AirBnbReviewAggregator.compile_comp_sets()."""

    @pytest.fixture
    def aggregator(self):
        """Create an AirBnbReviewAggregator without loading real config."""
        with patch("main.AirBnbReviewAggregator.load_configs"):
            from main import AirBnbReviewAggregator

            agg = AirBnbReviewAggregator.__new__(AirBnbReviewAggregator)
            agg.config = {"zipcode": "97067"}
        return agg

    @pytest.fixture
    def comp_sets_dir(self, tmp_path):
        """Create a temp directory simulating outputs/05_comp_sets/."""
        d = tmp_path / "outputs" / "05_comp_sets"
        d.mkdir(parents=True)
        return d

    def test_merges_single_comp_set(self, aggregator, comp_sets_dir):
        """A single listing file is written verbatim to the master file."""
        data = {
            "listing_1": {"ADR": 100.0, "Occupancy": 50, "Max_Guests": 4},
            "listing_2": {"ADR": 200.0, "Occupancy": 70, "Max_Guests": 6},
        }
        (comp_sets_dir / "listing_111.json").write_text(json.dumps(data))

        aggregator.compile_comp_sets(output_dir=str(comp_sets_dir))

        master_path = comp_sets_dir / "comp_set_97067.json"
        assert master_path.exists()
        result = json.loads(master_path.read_text())
        assert len(result) == 2
        assert result["listing_1"]["ADR"] == 100.0
        assert result["listing_2"]["Max_Guests"] == 6

    def test_merges_multiple_comp_sets(self, aggregator, comp_sets_dir):
        """Multiple listing files are merged into one master file."""
        data_a = {
            "listing_1": {"ADR": 100.0, "Occupancy": 50},
        }
        data_b = {
            "listing_2": {"ADR": 200.0, "Occupancy": 70},
        }
        (comp_sets_dir / "listing_111.json").write_text(json.dumps(data_a))
        (comp_sets_dir / "listing_222.json").write_text(json.dumps(data_b))

        aggregator.compile_comp_sets(output_dir=str(comp_sets_dir))

        result = json.loads((comp_sets_dir / "comp_set_97067.json").read_text())
        assert len(result) == 2
        assert "listing_1" in result
        assert "listing_2" in result

    def test_first_write_wins_on_duplicates(self, aggregator, comp_sets_dir):
        """When a listing appears in multiple comp sets, the first occurrence wins."""
        data_a = {
            "listing_1": {"ADR": 100.0, "Occupancy": 50},
        }
        data_b = {
            "listing_1": {"ADR": 999.0, "Occupancy": 99},
        }
        # listing_111 sorts before listing_222
        (comp_sets_dir / "listing_111.json").write_text(json.dumps(data_a))
        (comp_sets_dir / "listing_222.json").write_text(json.dumps(data_b))

        aggregator.compile_comp_sets(output_dir=str(comp_sets_dir))

        result = json.loads((comp_sets_dir / "comp_set_97067.json").read_text())
        assert result["listing_1"]["ADR"] == 100.0

    def test_no_compset_files_produces_empty_master(self, aggregator, comp_sets_dir):
        """If no listing files exist, the master file is an empty dict."""
        aggregator.compile_comp_sets(output_dir=str(comp_sets_dir))

        result = json.loads((comp_sets_dir / "comp_set_97067.json").read_text())
        assert result == {}

    def test_master_file_does_not_include_itself(self, aggregator, comp_sets_dir):
        """The master comp_set_{zipcode}.json should not be read as a listing input."""
        data = {"listing_1": {"ADR": 100.0}}
        (comp_sets_dir / "listing_111.json").write_text(json.dumps(data))
        # Pre-existing master file from a previous run
        (comp_sets_dir / "comp_set_97067.json").write_text(
            json.dumps({"old_listing": {"ADR": 50.0}})
        )

        aggregator.compile_comp_sets(output_dir=str(comp_sets_dir))

        result = json.loads((comp_sets_dir / "comp_set_97067.json").read_text())
        assert "old_listing" not in result
        assert "listing_1" in result

    def test_preserves_all_ten_fields(self, aggregator, comp_sets_dir):
        """All 10 fields from the comp set data are preserved in the master file."""
        data = {
            "listing_1": {
                "ADR": 969.19,
                "Occupancy": 42,
                "Revenue": 132800.0,
                "Bedrooms": 6,
                "Bathrooms": 3.5,
                "Max_Guests": 15,
                "Days_Available": 330,
                "LY_Revenue": 141400.0,
                "Rating": 4.8,
                "Review_Count": 35,
            }
        }
        (comp_sets_dir / "listing_111.json").write_text(json.dumps(data))

        aggregator.compile_comp_sets(output_dir=str(comp_sets_dir))

        result = json.loads((comp_sets_dir / "comp_set_97067.json").read_text())
        listing = result["listing_1"]
        assert listing["ADR"] == 969.19
        assert listing["Occupancy"] == 42
        assert listing["Revenue"] == 132800.0
        assert listing["Bedrooms"] == 6
        assert listing["Bathrooms"] == 3.5
        assert listing["Max_Guests"] == 15
        assert listing["Days_Available"] == 330
        assert listing["LY_Revenue"] == 141400.0
        assert listing["Rating"] == 4.8
        assert listing["Review_Count"] == 35
