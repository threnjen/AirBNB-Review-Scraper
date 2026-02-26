"""
Unit tests for scraper/airdna_scraper.py — per-listing rentalizer scraper.
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
            listing_ids=["17134562"],
            inspect_mode=False,
        )
        assert scraper.cdp_url == "http://localhost:9222"

    def test_init_stores_listing_ids(self):
        """Test that __init__ stores listing IDs."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562", "942203543119276616"],
            inspect_mode=False,
        )
        assert scraper.listing_ids == ["17134562", "942203543119276616"]

    def test_init_stores_inspect_mode(self):
        """Test that __init__ stores inspect mode flag."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            inspect_mode=True,
        )
        assert scraper.inspect_mode is True

    def test_init_default_inspect_mode_is_false(self):
        """Test that inspect_mode defaults to False."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
        )
        assert scraper.inspect_mode is False

    def test_init_stores_min_days_available(self):
        """Test that __init__ stores min_days_available."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            min_days_available=100,
        )
        assert scraper.min_days_available == 100

    def test_init_default_min_days_available(self):
        """Test that min_days_available defaults to 100."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
        )
        assert scraper.min_days_available == 100


class TestAirDNAScraperBuildUrl:
    """Tests for rentalizer URL construction."""

    @pytest.fixture
    def scraper(self):
        """Create an AirDNAScraper instance for testing."""
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            inspect_mode=False,
        )

    def test_build_url_returns_correct_rentalizer_url(self, scraper):
        """Test that _build_rentalizer_url generates the correct URL."""
        url = scraper._build_rentalizer_url("17134562")
        assert url == "https://app.airdna.co/data/rentalizer?&listing_id=abnb_17134562"

    def test_build_url_handles_different_ids(self, scraper):
        """Test URL generation with various listing IDs."""
        url = scraper._build_rentalizer_url("942203543119276616")
        assert (
            url
            == "https://app.airdna.co/data/rentalizer?&listing_id=abnb_942203543119276616"
        )


class TestAirDNAScraperParseMetrics:
    """Tests for metric parsing helper methods."""

    @pytest.fixture
    def scraper(self):
        """Create an AirDNAScraper instance for testing."""
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
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

    def test_parse_revenue_with_k_suffix(self, scraper):
        """Test parsing revenue with K abbreviation."""
        assert scraper._parse_revenue("$47.8K") == 47800.0

    def test_parse_revenue_with_m_suffix(self, scraper):
        """Test parsing revenue with M abbreviation."""
        assert scraper._parse_revenue("$1.2M") == 1200000.0

    def test_parse_revenue_plain_number(self, scraper):
        """Test parsing revenue as plain dollar amount."""
        assert scraper._parse_revenue("$174900") == 174900.0

    def test_parse_bedrooms_integer(self, scraper):
        """Test parsing whole number bedrooms."""
        assert scraper._parse_bedrooms("3") == 3.0

    def test_parse_bedrooms_decimal(self, scraper):
        """Test parsing decimal bathrooms value."""
        assert scraper._parse_bedrooms("2.5") == 2.5


class TestAirDNAScraperSaveResults:
    """Tests for saving per-listing results to JSON files."""

    @pytest.fixture
    def scraper(self):
        """Create an AirDNAScraper instance for testing."""
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            inspect_mode=False,
        )

    def test_save_listing_creates_json_file(self, scraper, tmp_path):
        """Test that save_listing_result creates a JSON file."""
        data = {
            "ADR": 487.5,
            "Occupancy": 32,
            "Revenue": 51700.0,
            "Bedrooms": 4,
            "Bathrooms": 3.0,
            "Max_Guests": 15,
            "Days_Available": 333,
            "LY_Revenue": 0.0,
            "Rating": 4.7,
            "Review_Count": 287,
        }
        scraper.save_listing_result("17134562", data, output_dir=str(tmp_path))

        output_path = tmp_path / "listing_17134562.json"
        assert output_path.exists()

    def test_save_listing_writes_correct_json(self, scraper, tmp_path):
        """Test that saved JSON matches the expected data."""
        data = {
            "ADR": 487.5,
            "Occupancy": 32,
            "Revenue": 51700.0,
            "Bedrooms": 4,
            "Bathrooms": 3.0,
            "Max_Guests": 15,
            "Days_Available": 333,
            "LY_Revenue": 0.0,
            "Rating": 4.7,
            "Review_Count": 287,
        }
        scraper.save_listing_result("17134562", data, output_dir=str(tmp_path))

        output_path = tmp_path / "listing_17134562.json"
        with open(output_path) as f:
            loaded = json.load(f)

        assert loaded == {"17134562": data}

    def test_save_listing_values_have_required_fields(self, scraper, tmp_path):
        """Test that saved listing has all expected metric keys."""
        data = {
            "ADR": 487.5,
            "Occupancy": 32,
            "Revenue": 51700.0,
            "Bedrooms": 4,
            "Bathrooms": 3.0,
            "Max_Guests": 15,
            "Days_Available": 333,
            "LY_Revenue": 0.0,
            "Rating": 4.7,
            "Review_Count": 287,
        }
        scraper.save_listing_result("17134562", data, output_dir=str(tmp_path))

        output_path = tmp_path / "listing_17134562.json"
        with open(output_path) as f:
            loaded = json.load(f)

        expected_keys = {
            "ADR",
            "Occupancy",
            "Revenue",
            "Bedrooms",
            "Bathrooms",
            "Max_Guests",
            "Days_Available",
            "LY_Revenue",
            "Rating",
            "Review_Count",
        }
        for listing_id, metrics in loaded.items():
            assert set(metrics.keys()) == expected_keys

    def test_save_listing_uses_listing_id_in_filename(self, scraper, tmp_path):
        """Test that the output filename includes the listing ID."""
        scraper.save_listing_result(
            "942203543119276616", {"ADR": 1}, output_dir=str(tmp_path)
        )

        assert (tmp_path / "listing_942203543119276616.json").exists()


class TestAirDNAScraperDaysFilter:
    """Tests for min_days_available filtering logic."""

    def test_listing_below_threshold_is_filtered(self):
        """Test that a listing with fewer than min_days is excluded."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            min_days_available=100,
        )
        assert scraper.should_include_listing({"Days_Available": 50}) is False

    def test_listing_at_threshold_is_included(self):
        """Test that a listing with exactly min_days is included."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            min_days_available=100,
        )
        assert scraper.should_include_listing({"Days_Available": 100}) is True

    def test_listing_above_threshold_is_included(self):
        """Test that a listing above min_days is included."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            min_days_available=100,
        )
        assert scraper.should_include_listing({"Days_Available": 333}) is True

    def test_filter_zero_threshold_includes_all(self):
        """Test that threshold of 0 includes everything."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            min_days_available=0,
        )
        assert scraper.should_include_listing({"Days_Available": 0}) is True
