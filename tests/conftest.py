"""
Shared pytest fixtures for the AirBNB Review Scraper test suite.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
    empty_config = {
        "openai": {"enable_caching": False, "enable_cost_tracking": False},
        "pipeline_cache_enabled": False,
        "pipeline_cache_ttl_days": 7,
    }
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(empty_config, f)

    # Don't change working directory - just patch file loading where needed


# ============================================================================
# Integration Test Fixtures
# ============================================================================


@pytest.fixture
def sample_property_summary():
    """Sample property summary text for integration testing."""
    return """## Property Summary - Listing 12345678

**Overall Rating:** 4.5/5 (based on 25 reviews)

### Positives
- **Location** (20 of 25 Reviews): Guests consistently praise the central location with easy access to restaurants and shops.
- **Cleanliness** (18 of 25 Reviews): The property is described as spotless and well-maintained.
- **Host Communication** (15 of 25 Reviews): The host is responsive and provides helpful local tips.

### Criticisms
- **Noise** (5 of 25 Reviews): Some guests noted street noise, especially on weekends.
- **Parking** (3 of 25 Reviews): Limited parking options mentioned by a few guests.

### Notable Features
- Hot tub on deck
- Mountain views
- Pet-friendly
"""


@pytest.fixture
def sample_extraction_response():
    """Sample extraction JSON response from OpenAI."""
    return json.dumps(
        {
            "listing_id": "12345678",
            "total_reviews": 25,
            "items": [
                {
                    "category": "Location",
                    "original_topic": "Location",
                    "sentiment": "positive",
                    "mentions": 20,
                    "total_reviews": 25,
                    "description": "Central location with easy access to restaurants and shops",
                },
                {
                    "category": "Cleanliness",
                    "original_topic": "Cleanliness",
                    "sentiment": "positive",
                    "mentions": 18,
                    "total_reviews": 25,
                    "description": "Property is spotless and well-maintained",
                },
                {
                    "category": "Noise",
                    "original_topic": "Noise",
                    "sentiment": "negative",
                    "mentions": 5,
                    "total_reviews": 25,
                    "description": "Street noise on weekends",
                },
            ],
        }
    )


@pytest.fixture
def mock_summary_files_dir(tmp_path, sample_property_summary):
    """Create a temp directory with sample property summary files."""
    summary_dir = tmp_path / "outputs" / "06_generated_summaries"
    summary_dir.mkdir(parents=True)

    # Create sample summary files for zipcode 97067
    summaries = [
        (
            "generated_summaries_97067_12345678.json",
            {"12345678": sample_property_summary},
        ),
        (
            "generated_summaries_97067_87654321.json",
            {"87654321": "Another great property with mountain views."},
        ),
        (
            "generated_summaries_97067_11111111.json",
            {"11111111": "Cozy cabin perfect for families."},
        ),
    ]

    for filename, data in summaries:
        file_path = summary_dir / filename
        with open(file_path, "w") as f:
            json.dump(data, f)

    return summary_dir


@pytest.fixture
def mock_review_files_dir(tmp_path, sample_reviews):
    """Create a temp directory with sample property review files."""
    review_dir = tmp_path / "outputs" / "03_reviews_scraped"
    review_dir.mkdir(parents=True)

    # Create sample review files
    for i, listing_id in enumerate(["12345678", "87654321", "11111111"]):
        file_path = review_dir / f"property_reviews_97067_{listing_id}.json"
        with open(file_path, "w") as f:
            json.dump(sample_reviews, f)

    return review_dir


@pytest.fixture
def mocked_openai_aggregator(mock_openai_client, tmp_cache_dir, tmp_logs_dir):
    """Create an OpenAIAggregator with mocked OpenAI client for integration tests."""
    with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
        mock_load.return_value = {
            "openai": {
                "model": "gpt-4o-mini",
                "temperature": 0.3,
                "max_tokens": 4000,
                "chunk_size": 20,
                "enable_caching": True,
                "enable_cost_tracking": True,
            }
        }
        with patch("utils.cache_manager.load_json_file", return_value={}):
            with patch("utils.cost_tracker.load_json_file", return_value={}):
                from review_aggregator.openai_aggregator import OpenAIAggregator

                agg = OpenAIAggregator(client=mock_openai_client)
                agg.cache_manager.cache_dir = str(tmp_cache_dir)
                agg.cost_tracker.log_file = str(tmp_logs_dir / "cost.json")
                return agg
