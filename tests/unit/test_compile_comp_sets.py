"""Tests for compile_airdna_data() in steps/03_airdna_data.py — merging per-listing
JSON files into a single master comp_set_{zipcode}.json file."""

import json
import os
from importlib import import_module

import pytest

# steps.03_airdna_data uses a dotted name that's not a valid Python identifier,
# so we import it dynamically.
_step_module = import_module("steps.03_airdna_data")
compile_airdna_data = _step_module.compile_airdna_data

ZIPCODE = "97067"


class TestCompileCompSets:
    """Tests for compile_airdna_data()."""

    @pytest.fixture
    def airdna_data_dir(self, tmp_path):
        """Create a temp directory simulating outputs/03_airdna_data/."""
        d = tmp_path / "outputs" / "03_airdna_data"
        d.mkdir(parents=True)
        return d

    def test_merges_single_comp_set(self, airdna_data_dir):
        """A single listing file is written verbatim to the master file."""
        data = {
            "listing_1": {"ADR": 100.0, "Occupancy": 50, "Max_Guests": 4},
            "listing_2": {"ADR": 200.0, "Occupancy": 70, "Max_Guests": 6},
        }
        (airdna_data_dir / "listing_111.json").write_text(json.dumps(data))

        compile_airdna_data(ZIPCODE, output_dir=str(airdna_data_dir))

        master_path = airdna_data_dir / f"comp_set_{ZIPCODE}.json"
        assert master_path.exists()
        result = json.loads(master_path.read_text())
        assert len(result) == 2
        assert result["listing_1"]["ADR"] == 100.0
        assert result["listing_2"]["Max_Guests"] == 6

    def test_merges_multiple_airdna_data(self, airdna_data_dir):
        """Multiple listing files are merged into one master file."""
        data_a = {
            "listing_1": {"ADR": 100.0, "Occupancy": 50},
        }
        data_b = {
            "listing_2": {"ADR": 200.0, "Occupancy": 70},
        }
        (airdna_data_dir / "listing_111.json").write_text(json.dumps(data_a))
        (airdna_data_dir / "listing_222.json").write_text(json.dumps(data_b))

        compile_airdna_data(ZIPCODE, output_dir=str(airdna_data_dir))

        result = json.loads((airdna_data_dir / f"comp_set_{ZIPCODE}.json").read_text())
        assert len(result) == 2
        assert "listing_1" in result
        assert "listing_2" in result

    def test_first_write_wins_on_duplicates(self, airdna_data_dir):
        """When a listing appears in multiple comp sets, the first occurrence wins."""
        data_a = {
            "listing_1": {"ADR": 100.0, "Occupancy": 50},
        }
        data_b = {
            "listing_1": {"ADR": 999.0, "Occupancy": 99},
        }
        # listing_111 sorts before listing_222
        (airdna_data_dir / "listing_111.json").write_text(json.dumps(data_a))
        (airdna_data_dir / "listing_222.json").write_text(json.dumps(data_b))

        compile_airdna_data(ZIPCODE, output_dir=str(airdna_data_dir))

        result = json.loads((airdna_data_dir / f"comp_set_{ZIPCODE}.json").read_text())
        assert result["listing_1"]["ADR"] == 100.0

    def test_no_compset_files_produces_empty_master(self, airdna_data_dir):
        """If no listing files exist, the master file is an empty dict."""
        compile_airdna_data(ZIPCODE, output_dir=str(airdna_data_dir))

        result = json.loads((airdna_data_dir / f"comp_set_{ZIPCODE}.json").read_text())
        assert result == {}

    def test_master_file_does_not_include_itself(self, airdna_data_dir):
        """The master comp_set_{zipcode}.json should not be read as a listing input."""
        data = {"listing_1": {"ADR": 100.0}}
        (airdna_data_dir / "listing_111.json").write_text(json.dumps(data))
        # Pre-existing master file from a previous run
        (airdna_data_dir / f"comp_set_{ZIPCODE}.json").write_text(
            json.dumps({"old_listing": {"ADR": 50.0}})
        )

        compile_airdna_data(ZIPCODE, output_dir=str(airdna_data_dir))

        result = json.loads((airdna_data_dir / f"comp_set_{ZIPCODE}.json").read_text())
        assert "old_listing" not in result
        assert "listing_1" in result

    def test_preserves_all_ten_fields(self, airdna_data_dir):
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
        (airdna_data_dir / "listing_111.json").write_text(json.dumps(data))

        compile_airdna_data(ZIPCODE, output_dir=str(airdna_data_dir))

        result = json.loads((airdna_data_dir / f"comp_set_{ZIPCODE}.json").read_text())
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
