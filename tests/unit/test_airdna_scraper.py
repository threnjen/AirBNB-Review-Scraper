"""
Unit tests for scraper/airdna_scraper.py
"""

import json

import pytest

from scraper.airdna_scraper import AirDNAScraper


class TestAirDNAScraperInit:
    """Tests for AirDNAScraper initialization."""

    def test_init_stores_cdp_url(self):
        """Test that __init__ stores the CDP URL."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            comp_set_ids=["365519"],
            inspect_mode=False,
        )
        assert scraper.cdp_url == "http://localhost:9222"

    def test_init_stores_comp_set_ids(self):
        """Test that __init__ stores comp set IDs."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            comp_set_ids=["365519", "123456"],
            inspect_mode=False,
        )
        assert scraper.comp_set_ids == ["365519", "123456"]

    def test_init_stores_inspect_mode(self):
        """Test that __init__ stores inspect mode flag."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            comp_set_ids=["365519"],
            inspect_mode=True,
        )
        assert scraper.inspect_mode is True

    def test_init_default_inspect_mode_is_false(self):
        """Test that inspect_mode defaults to False."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            comp_set_ids=["365519"],
        )
        assert scraper.inspect_mode is False


class TestAirDNAScraperBuildUrl:
    """Tests for comp set URL construction."""

    @pytest.fixture
    def scraper(self):
        """Create an AirDNAScraper instance for testing."""
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            comp_set_ids=["365519"],
            inspect_mode=False,
        )

    def test_build_url_returns_correct_url(self, scraper):
        """Test that _build_comp_set_url generates the correct URL."""
        url = scraper._build_comp_set_url("365519")
        assert url == "https://app.airdna.co/data/comp-sets/365519"

    def test_build_url_handles_different_ids(self, scraper):
        """Test URL generation with various comp set IDs."""
        url = scraper._build_comp_set_url("999999")
        assert url == "https://app.airdna.co/data/comp-sets/999999"


class TestAirDNAScraperParseMetrics:
    """Tests for metric parsing helper methods."""

    @pytest.fixture
    def scraper(self):
        """Create an AirDNAScraper instance for testing."""
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            comp_set_ids=["365519"],
            inspect_mode=False,
        )

    def test_parse_currency_value_strips_dollar_sign(self, scraper):
        """Test parsing a dollar amount string."""
        assert scraper._parse_currency("$945.57") == 945.57

    def test_parse_currency_value_strips_commas(self, scraper):
        """Test parsing a dollar amount with commas."""
        assert scraper._parse_currency("$1,234.56") == 1234.56

    def test_parse_currency_value_handles_no_symbol(self, scraper):
        """Test parsing a plain number string."""
        assert scraper._parse_currency("945.57") == 945.57

    def test_parse_percentage_strips_percent_sign(self, scraper):
        """Test parsing a percentage string."""
        assert scraper._parse_percentage("88%") == 88

    def test_parse_percentage_handles_no_symbol(self, scraper):
        """Test parsing a plain number as percentage."""
        assert scraper._parse_percentage("88") == 88

    def test_parse_days_value(self, scraper):
        """Test parsing a days available string."""
        assert scraper._parse_days("335") == 335

    def test_parse_days_with_label(self, scraper):
        """Test parsing days string with trailing label."""
        assert scraper._parse_days("335 days") == 335


class TestAirDNAScraperSaveResults:
    """Tests for saving results to JSON files."""

    @pytest.fixture
    def scraper(self):
        """Create an AirDNAScraper instance for testing."""
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            comp_set_ids=["365519"],
            inspect_mode=False,
        )

    def test_save_results_creates_json_file(self, scraper, tmp_path):
        """Test that save_results creates a JSON file."""
        data = {
            "1050769200886027711": {
                "ADR": 945.57,
                "Occupancy": 39,
                "Days_Available": 335,
            }
        }
        output_path = tmp_path / "compset_365519.json"
        scraper.save_results("365519", data, output_dir=str(tmp_path))

        assert output_path.exists()

    def test_save_results_writes_correct_json_format(self, scraper, tmp_path):
        """Test that saved JSON matches the expected format."""
        data = {
            "1050769200886027711": {
                "ADR": 945.57,
                "Occupancy": 39,
                "Days_Available": 335,
            },
            "549180550450067551": {
                "ADR": 377.19,
                "Occupancy": 88,
                "Days_Available": 357,
            },
        }
        scraper.save_results("365519", data, output_dir=str(tmp_path))

        output_path = tmp_path / "compset_365519.json"
        with open(output_path) as f:
            loaded = json.load(f)

        assert loaded == data

    def test_save_results_keys_are_listing_id_strings(self, scraper, tmp_path):
        """Test that output keys are string listing IDs."""
        data = {
            "49019599": {
                "ADR": 464.92,
                "Occupancy": 63,
                "Days_Available": 353,
            }
        }
        scraper.save_results("365519", data, output_dir=str(tmp_path))

        output_path = tmp_path / "compset_365519.json"
        with open(output_path) as f:
            loaded = json.load(f)

        for key in loaded:
            assert isinstance(key, str)

    def test_save_results_values_have_required_fields(self, scraper, tmp_path):
        """Test that each listing value contains ADR, Occupancy, Days_Available."""
        data = {
            "49019599": {
                "ADR": 464.92,
                "Occupancy": 63,
                "Days_Available": 353,
            }
        }
        scraper.save_results("365519", data, output_dir=str(tmp_path))

        output_path = tmp_path / "compset_365519.json"
        with open(output_path) as f:
            loaded = json.load(f)

        for listing_id, metrics in loaded.items():
            assert "ADR" in metrics
            assert "Occupancy" in metrics
            assert "Days_Available" in metrics

    def test_save_results_empty_data_writes_empty_json(self, scraper, tmp_path):
        """Test that empty data writes an empty JSON object."""
        scraper.save_results("365519", {}, output_dir=str(tmp_path))

        output_path = tmp_path / "compset_365519.json"
        with open(output_path) as f:
            loaded = json.load(f)

        assert loaded == {}

    def test_save_results_uses_comp_set_id_in_filename(self, scraper, tmp_path):
        """Test that the output filename includes the comp set ID."""
        scraper.save_results("999999", {"id": {"ADR": 1}}, output_dir=str(tmp_path))

        assert (tmp_path / "compset_999999.json").exists()


class TestAirDNAScraperScrollDetection:
    """Tests for infinite scroll termination logic."""

    @pytest.fixture
    def scraper(self):
        """Create an AirDNAScraper instance for testing."""
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            comp_set_ids=["365519"],
            inspect_mode=False,
        )

    def test_should_continue_scrolling_returns_true_when_new_elements(self, scraper):
        """Test that scrolling continues when new elements appear."""
        assert (
            scraper._should_continue_scrolling(
                previous_count=10, current_count=15, max_retries=3, retry_count=0
            )
            is True
        )

    def test_should_continue_scrolling_returns_false_when_count_stable(self, scraper):
        """Test that scrolling stops when element count stabilizes."""
        assert (
            scraper._should_continue_scrolling(
                previous_count=52, current_count=52, max_retries=3, retry_count=3
            )
            is False
        )

    def test_should_continue_scrolling_retries_before_stopping(self, scraper):
        """Test that scrolling retries a few times before giving up."""
        assert (
            scraper._should_continue_scrolling(
                previous_count=52, current_count=52, max_retries=3, retry_count=1
            )
            is True
        )

    def test_should_continue_scrolling_returns_false_at_max_retries(self, scraper):
        """Test that scrolling stops at max retries."""
        assert (
            scraper._should_continue_scrolling(
                previous_count=52, current_count=52, max_retries=3, retry_count=3
            )
            is False
        )
