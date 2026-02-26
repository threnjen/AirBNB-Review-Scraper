"""
Unit tests for scraper/airdna_scraper.py — per-listing rentalizer scraper.
"""

import json
from unittest.mock import MagicMock, patch

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

    def test_init_stores_pipeline_cache(self):
        """Test that __init__ stores pipeline_cache."""
        mock_cache = "fake_cache"
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            pipeline_cache=mock_cache,
        )
        assert scraper.pipeline_cache == "fake_cache"

    def test_init_default_pipeline_cache_is_none(self):
        """Test that pipeline_cache defaults to None."""
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
        )
        assert scraper.pipeline_cache is None


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


class TestAirDNAScraperIsEmptyResult:
    """Tests for _is_empty_result detection."""

    @pytest.fixture
    def scraper(self):
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
        )

    def test_all_zeros_is_empty(self, scraper):
        """All-zero metrics indicate a failed/rejected page load."""
        metrics = {"ADR": 0, "Revenue": 0, "Occupancy": 0, "Days_Available": 0}
        assert scraper._is_empty_result(metrics) is True

    def test_all_zero_floats_is_empty(self, scraper):
        """Zero floats are also empty."""
        metrics = {"ADR": 0.0, "Revenue": 0.0, "Occupancy": 0, "Days_Available": 0}
        assert scraper._is_empty_result(metrics) is True

    def test_any_nonzero_adr_is_not_empty(self, scraper):
        """A nonzero ADR means the page loaded."""
        metrics = {"ADR": 487.5, "Revenue": 0, "Occupancy": 0, "Days_Available": 0}
        assert scraper._is_empty_result(metrics) is False

    def test_any_nonzero_revenue_is_not_empty(self, scraper):
        """A nonzero Revenue means the page loaded."""
        metrics = {"ADR": 0, "Revenue": 51700.0, "Occupancy": 0, "Days_Available": 0}
        assert scraper._is_empty_result(metrics) is False

    def test_full_metrics_is_not_empty(self, scraper):
        """Normal metrics are not empty."""
        metrics = {
            "ADR": 487.5,
            "Revenue": 51700.0,
            "Occupancy": 32,
            "Days_Available": 333,
        }
        assert scraper._is_empty_result(metrics) is False

    def test_empty_dict_is_empty(self, scraper):
        """An empty dict defaults to all zeros."""
        assert scraper._is_empty_result({}) is True


class TestAirDNAScraperIsCached:
    """Tests for _is_listing_cached."""

    @pytest.fixture
    def scraper(self):
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
        )

    def test_uncached_listing_without_pipeline_cache(self, scraper, tmp_path):
        """Without a cache manager and no file on disk, listing is not cached."""
        assert scraper._is_listing_cached("99999") is False

    def test_cached_listing_via_pipeline_cache(self):
        """Listing is cached when pipeline_cache says it's fresh."""
        from unittest.mock import MagicMock

        mock_cache = MagicMock()
        mock_cache.is_file_fresh.return_value = True
        scraper = AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            pipeline_cache=mock_cache,
        )
        assert scraper._is_listing_cached("17134562") is True

    def test_cached_listing_via_file_on_disk(self, scraper, tmp_path, monkeypatch):
        """Listing is cached when the output file exists on disk."""
        output_dir = tmp_path / "outputs" / "02_comp_sets"
        output_dir.mkdir(parents=True)
        (output_dir / "listing_17134562.json").write_text("{}")
        monkeypatch.chdir(tmp_path)
        assert scraper._is_listing_cached("17134562") is True


class TestAirDNAScraperScrapeListingTimeout:
    """Tests for scrape_listing KPI timeout and early-return behavior."""

    @pytest.fixture
    def scraper(self):
        """Create an AirDNAScraper instance for testing."""
        return AirDNAScraper(
            cdp_url="http://localhost:9222",
            listing_ids=["17134562"],
            inspect_mode=False,
        )

    def test_kpi_timeout_skips_extraction(self, scraper):
        """When KPI selector times out, skip extra wait and extraction."""
        page = MagicMock()
        page.wait_for_selector.side_effect = Exception("Timeout")

        with (
            patch.object(scraper, "_extract_header_metrics") as mock_header,
            patch.object(scraper, "_extract_kpi_metrics") as mock_kpi,
        ):
            result = scraper.scrape_listing(page, "17134562")

        page.wait_for_timeout.assert_not_called()
        mock_header.assert_not_called()
        mock_kpi.assert_not_called()

    def test_kpi_timeout_returns_all_zeros(self, scraper):
        """When KPI selector times out, return all-zero metrics dict."""
        page = MagicMock()
        page.wait_for_selector.side_effect = Exception("Timeout")

        result = scraper.scrape_listing(page, "17134562")

        assert scraper._is_empty_result(result) is True
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
        assert set(result.keys()) == expected_keys

    def test_kpi_success_runs_extraction(self, scraper):
        """When KPI selector succeeds, perform extra wait and extraction."""
        page = MagicMock()
        page.wait_for_selector.return_value = True

        with (
            patch.object(
                scraper, "_extract_header_metrics", return_value={}
            ) as mock_header,
            patch.object(scraper, "_extract_kpi_metrics", return_value={}) as mock_kpi,
        ):
            scraper.scrape_listing(page, "17134562")

        page.wait_for_timeout.assert_called_once()
        mock_header.assert_called_once_with(page)
        mock_kpi.assert_called_once_with(page)

    def test_kpi_timeout_uses_10_seconds(self, scraper):
        """KPI selector wait uses a 10-second timeout."""
        page = MagicMock()
        page.wait_for_selector.return_value = True

        with (
            patch.object(scraper, "_extract_header_metrics", return_value={}),
            patch.object(scraper, "_extract_kpi_metrics", return_value={}),
        ):
            scraper.scrape_listing(page, "17134562")

        page.wait_for_selector.assert_called_once_with(
            "text=Annual Revenue", state="visible", timeout=10_000
        )
