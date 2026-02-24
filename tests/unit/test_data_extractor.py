"""
Unit tests for review_aggregator/data_extractor.py
"""

import json
import pytest
from unittest.mock import patch, MagicMock


class TestDataExtractor:
    """Tests for DataExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a DataExtractor with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {"enable_caching": False, "enable_cost_tracking": False}
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.data_extractor import DataExtractor

                    return DataExtractor(zipcode="97067")

    @pytest.fixture
    def sample_summary_text(self):
        """Sample property summary text with review mentions."""
        return """1. This listing is a charming log cabin. There are a total of 20 reviews.

2. Positives:
   - Location: Beautiful and secluded environment. Mentions: 15 of 20 Reviews (75%)
   - Host: Highly communicative. Mentions: 10 of 20 Reviews (50%)
   - Hot Tub: A highlight. Mentions: 7 of 20 Reviews (35%)

3. Criticisms:
   - Cleanliness: Could benefit from a deep clean. Mentions: 2 of 20 Reviews (10%)
   - Privacy: Hot tub not private. Mentions: 1 of 20 Reviews (5%)
"""

    @pytest.fixture
    def sample_extraction_response(self):
        """Sample LLM extraction response."""
        return json.dumps(
            {
                "listing_id": "25923",
                "total_reviews": 20,
                "items": [
                    {
                        "category": "Location",
                        "original_topic": "Location",
                        "sentiment": "positive",
                        "mentions": 15,
                        "total_reviews": 20,
                        "description": "Beautiful and secluded environment",
                    },
                    {
                        "category": "Host Communication",
                        "original_topic": "Host",
                        "sentiment": "positive",
                        "mentions": 10,
                        "total_reviews": 20,
                        "description": "Highly communicative",
                    },
                    {
                        "category": "Amenities",
                        "original_topic": "Hot Tub",
                        "sentiment": "positive",
                        "mentions": 7,
                        "total_reviews": 20,
                        "description": "A highlight",
                    },
                    {
                        "category": "Cleanliness Issues",
                        "original_topic": "Cleanliness",
                        "sentiment": "negative",
                        "mentions": 2,
                        "total_reviews": 20,
                        "description": "Could benefit from a deep clean",
                    },
                    {
                        "category": "Privacy Concerns",
                        "original_topic": "Privacy",
                        "sentiment": "negative",
                        "mentions": 1,
                        "total_reviews": 20,
                        "description": "Hot tub not private",
                    },
                ],
            }
        )

    def test_load_property_summaries_empty_dir(self, extractor):
        """Test loading summaries from empty directory returns empty dict."""
        with patch(
            "review_aggregator.data_extractor.os.path.exists", return_value=False
        ):
            result = extractor.load_property_summaries()

        assert result == {}

    def test_load_property_summaries_with_files(self, extractor):
        """Test loading summaries from directory with matching files."""
        with patch(
            "review_aggregator.data_extractor.os.path.exists", return_value=True
        ):
            with patch(
                "review_aggregator.data_extractor.os.listdir",
                return_value=[
                    "generated_summaries_97067_12345.json",
                    "generated_summaries_97067_67890.json",
                    "generated_summaries_00000_99999.json",
                ],
            ):
                with patch(
                    "review_aggregator.data_extractor.load_json_file"
                ) as mock_load:
                    mock_load.side_effect = [
                        {"12345": "Summary for listing 12345"},
                        {"67890": "Summary for listing 67890"},
                    ]
                    result = extractor.load_property_summaries()

        assert len(result) == 2
        assert "12345" in result
        assert "67890" in result

    def test_extract_data_from_summary_basic(
        self, extractor, sample_summary_text, sample_extraction_response
    ):
        """Test extraction from summary text produces expected structure."""
        with patch(
            "review_aggregator.data_extractor.OpenAIAggregator.generate_summary",
            return_value=sample_extraction_response,
        ):
            result = extractor.extract_data_from_summary("25923", sample_summary_text)

        assert result["listing_id"] == "25923"
        assert result["total_reviews"] == 20
        assert len(result["items"]) == 5

    def test_extract_data_from_summary_json_cleanup(
        self, extractor, sample_summary_text
    ):
        """Test extraction handles markdown-wrapped JSON response."""
        wrapped_response = (
            "```json\n"
            + json.dumps({"listing_id": "25923", "total_reviews": 20, "items": []})
            + "\n```"
        )

        with patch(
            "review_aggregator.data_extractor.OpenAIAggregator.generate_summary",
            return_value=wrapped_response,
        ):
            result = extractor.extract_data_from_summary("25923", sample_summary_text)

        assert result["listing_id"] == "25923"
        assert result["total_reviews"] == 20

    def test_extract_data_from_summary_invalid_json(
        self, extractor, sample_summary_text
    ):
        """Test extraction returns empty structure on invalid JSON."""
        with patch(
            "review_aggregator.data_extractor.OpenAIAggregator.generate_summary",
            return_value="This is not valid JSON",
        ):
            result = extractor.extract_data_from_summary("25923", sample_summary_text)

        assert result["listing_id"] == "25923"
        assert result["total_reviews"] == 0
        assert result["items"] == []

    def test_aggregate_extractions_positive(self, extractor):
        """Test aggregation of positive category items."""
        extractions = [
            {
                "listing_id": "111",
                "total_reviews": 20,
                "items": [
                    {
                        "category": "Location",
                        "original_topic": "Location",
                        "sentiment": "positive",
                        "mentions": 15,
                        "total_reviews": 20,
                        "description": "Great location",
                    }
                ],
            },
            {
                "listing_id": "222",
                "total_reviews": 30,
                "items": [
                    {
                        "category": "Location",
                        "original_topic": "Views",
                        "sentiment": "positive",
                        "mentions": 25,
                        "total_reviews": 30,
                        "description": "Amazing views",
                    }
                ],
            },
        ]

        result = extractor.aggregate_extractions(extractions)

        assert result["zipcode"] == "97067"
        assert result["total_properties_analyzed"] == 2
        assert result["total_reviews_in_area"] == 50
        assert "Location" in result["positive_categories"]
        assert result["positive_categories"]["Location"]["total_mentions"] == 40
        assert result["positive_categories"]["Location"]["total_reviews"] == 50
        assert len(result["positive_categories"]["Location"]["properties"]) == 2

    def test_aggregate_extractions_negative(self, extractor):
        """Test aggregation of negative category items."""
        extractions = [
            {
                "listing_id": "111",
                "total_reviews": 20,
                "items": [
                    {
                        "category": "Cleanliness Issues",
                        "original_topic": "Cleanliness",
                        "sentiment": "negative",
                        "mentions": 3,
                        "total_reviews": 20,
                        "description": "Needs cleaning",
                    }
                ],
            }
        ]

        result = extractor.aggregate_extractions(extractions)

        assert "Cleanliness Issues" in result["negative_categories"]
        assert (
            result["negative_categories"]["Cleanliness Issues"]["total_mentions"] == 3
        )

    def test_aggregate_extractions_percentage(self, extractor):
        """Test percentage calculation in aggregation."""
        extractions = [
            {
                "listing_id": "111",
                "total_reviews": 100,
                "items": [
                    {
                        "category": "Location",
                        "original_topic": "Location",
                        "sentiment": "positive",
                        "mentions": 80,
                        "total_reviews": 100,
                        "description": "Great spot",
                    }
                ],
            }
        ]

        result = extractor.aggregate_extractions(extractions)

        assert result["positive_categories"]["Location"]["percentage"] == 80.0

    def test_run_extraction_no_summaries(self, extractor):
        """Test run_extraction handles no summaries gracefully."""
        with patch(
            "review_aggregator.data_extractor.os.path.exists", return_value=False
        ):
            result = extractor.run_extraction()

        assert result is None
