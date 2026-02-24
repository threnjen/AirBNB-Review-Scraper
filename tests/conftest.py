"""
Shared pytest fixtures for the AirBNB Review Scraper test suite.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# Get the tests directory path
TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"


@pytest.fixture
def sample_data():
    """Load sample test data from fixtures."""
    with open(FIXTURES_DIR / "sample_data.json") as f:
        return json.load(f)


@pytest.fixture
def sample_reviews(sample_data):
    """Sample review data for testing."""
    return sample_data["sample_reviews"]


@pytest.fixture
def sample_config(sample_data):
    """Sample configuration for testing."""
    return sample_data["sample_config"]


@pytest.fixture
def sample_listing_id(sample_data):
    """Sample listing ID for testing."""
    return sample_data["sample_listing_id"]


@pytest.fixture
def sample_prompt(sample_data):
    """Sample prompt for testing."""
    return sample_data["sample_prompt"]


@pytest.fixture
def sample_openai_response(sample_data):
    """Sample OpenAI response for testing."""
    return sample_data["sample_openai_response"]


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Temporary cache directory for testing."""
    cache_dir = tmp_path / "cache" / "summaries"
    cache_dir.mkdir(parents=True)
    return cache_dir


@pytest.fixture
def tmp_logs_dir(tmp_path):
    """Temporary logs directory for testing."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)
    return logs_dir


@pytest.fixture
def mock_config(sample_config, tmp_path):
    """Create a mock config.json file and patch load_json_file."""
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(sample_config, f)
    return sample_config


@pytest.fixture
def mock_openai_client(sample_openai_response):
    """Mock OpenAI client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = sample_openai_response
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_pgeocode():
    """Mock pgeocode for testing location_calculator."""
    with patch("scraper.location_calculator.pgeocode") as mock_pg:
        mock_nomi = MagicMock()
        mock_pg.Nominatim.return_value = mock_nomi

        # Default query result
        mock_query_result = MagicMock()
        mock_query_result.get = lambda key: {
            "latitude": 45.5155,
            "longitude": -122.6789,
            "place_name": "Portland",
        }.get(key)
        mock_nomi.query_postal_code.return_value = mock_query_result

        yield mock_pg


@pytest.fixture
def review_strings():
    """Convert sample_reviews to string format used by aggregator."""
    return [
        "5 Amazing place! Very clean and great location.",
        "4 Good stay overall. Host was responsive.",
        "5 Perfect getaway spot. Would definitely return.",
        "3 Decent place but could use some updates.",
        "5 Loved everything about this rental!",
    ]


@pytest.fixture
def empty_reviews():
    """Empty reviews list for edge case testing."""
    return []


@pytest.fixture
def single_review():
    """Single review for edge case testing."""
    return [{"rating": 5, "review": "Great place!"}]


@pytest.fixture(autouse=True)
def isolate_tests(tmp_path, monkeypatch):
    """Isolate tests from production config files."""
    # Create empty config.json in tmp_path to prevent loading production config
    empty_config = {"openai": {"enable_caching": False, "enable_cost_tracking": False}}
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(empty_config, f)

    # Don't change working directory - just patch file loading where needed
