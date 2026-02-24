"""
Unit tests for review_aggregator/property_review_aggregator.py
"""

import pytest
from unittest.mock import patch


class TestPropertyRagAggregator:
    """Tests for PropertyRagAggregator class."""

    @pytest.fixture
    def aggregator(self):
        """Create a PropertyRagAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {"enable_caching": False, "enable_cost_tracking": False}
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.property_review_aggregator import (
                        PropertyRagAggregator,
                    )

                    return PropertyRagAggregator(
                        zipcode="97067", num_listings_to_summarize=5
                    )

    def test_get_listing_id_mean_rating_valid_reviews(self, aggregator, sample_reviews):
        """Test mean rating calculation with valid reviews."""
        mean = aggregator.get_listing_id_mean_rating(sample_reviews)

        # (5 + 4 + 5 + 3 + 5) / 5 = 4.4
        assert mean == 4.4

    def test_get_listing_id_mean_rating_empty_list(self, aggregator):
        """Test mean rating with empty reviews list."""
        mean = aggregator.get_listing_id_mean_rating([])

        assert mean == 0

    def test_get_listing_id_mean_rating_none_ratings(self, aggregator):
        """Test mean rating when some ratings are None."""
        reviews = [
            {"rating": 5, "review": "Great"},
            {"rating": None, "review": "Good"},
            {"rating": 4, "review": "Nice"},
        ]

        mean = aggregator.get_listing_id_mean_rating(reviews)

        # (5 + 4) / 3 = 3.0 (None contributes 0 but counts in denominator via len)
        # Actually the code skips None but still divides by len
        assert mean == 3.0

    def test_get_listing_id_mean_rating_precision(self, aggregator):
        """Test that mean rating has correct precision (4 decimals)."""
        reviews = [
            {"rating": 5, "review": "A"},
            {"rating": 4, "review": "B"},
            {"rating": 3, "review": "C"},
        ]

        mean = aggregator.get_listing_id_mean_rating(reviews)

        assert mean == 4.0
        # Check rounding
        decimal_places = len(str(mean).split(".")[-1]) if "." in str(mean) else 0
        assert decimal_places <= 4

    def test_get_overall_mean_rating(self, aggregator):
        """Test overall mean rating across multiple listings."""
        reviews = {
            "listing1": [{"rating": 5, "review": "A"}, {"rating": 5, "review": "B"}],
            "listing2": [{"rating": 3, "review": "C"}, {"rating": 3, "review": "D"}],
        }

        overall = aggregator.get_overall_mean_rating(reviews)

        # listing1 mean = 5.0, listing2 mean = 3.0
        # overall = (5.0 + 3.0) / 2 = 4.0
        assert overall == 4.0

    def test_prompt_replacement_all_placeholders(self, aggregator):
        """Test that all placeholders are replaced."""
        prompt = "Zipcode: {ZIP_CODE_HERE}, ISO: {ISO_CODE_HERE}, Rating: {RATING_AVERAGE_HERE}, Overall: {OVERALL_MEAN}"

        with patch(
            "review_aggregator.property_review_aggregator.load_json_file"
        ) as mock:
            mock.return_value = {"iso_code": "us"}

            result = aggregator.prompt_replacement(
                current_prompt=prompt, listing_mean="4.5", overall_mean="4.2"
            )

        assert "97067" in result
        assert "us" in result
        assert "4.5" in result
        assert "4.2" in result
        assert "{" not in result  # No unresolved placeholders

    def test_prompt_replacement_preserves_other_text(self, aggregator):
        """Test that non-placeholder text is preserved."""
        prompt = "This is a prompt with {ZIP_CODE_HERE} embedded."

        with patch(
            "review_aggregator.property_review_aggregator.load_json_file"
        ) as mock:
            mock.return_value = {"iso_code": "us"}

            result = aggregator.prompt_replacement(prompt, "4.0", "4.0")

        assert "This is a prompt with" in result
        assert "embedded." in result

    def test_clean_single_item_reviews_format(self, aggregator, sample_reviews):
        """Test that reviews are cleaned to correct format."""
        result = aggregator.clean_single_item_reviews(sample_reviews)

        assert isinstance(result, list)
        assert len(result) == 5
        # Each item should be "rating review_text"
        assert result[0].startswith("5 ")

    def test_clean_single_item_reviews_combines_fields(self, aggregator):
        """Test that rating and review are combined."""
        reviews = [{"rating": 4, "review": "Test review text"}]

        result = aggregator.clean_single_item_reviews(reviews)

        assert result[0] == "4 Test review text"

    def test_adjust_list_length_under_limit(self, aggregator):
        """Test adjustment when fewer listings than limit."""
        aggregator.num_listings_to_summarize = 10
        reviews = {"a": [], "b": [], "c": []}

        result = aggregator.adjust_list_length_upper_bound_for_config(reviews)

        assert result == 3  # Total listings < configured limit

    def test_adjust_list_length_over_limit(self, aggregator):
        """Test adjustment when more listings than limit."""
        aggregator.num_listings_to_summarize = 2
        reviews = {"a": [], "b": [], "c": [], "d": []}

        result = aggregator.adjust_list_length_upper_bound_for_config(reviews)

        assert result == 2  # Returns configured limit

    def test_review_threshold_default(self, aggregator):
        """Test default review threshold value."""
        assert aggregator.review_thresh_to_include_prop == 5

    def test_process_single_listing_skips_empty_reviews(self, aggregator):
        """Test that listings with no reviews are skipped."""
        # This should log and return None (skip)
        result = aggregator.process_single_listing([], "listing123")

        assert result is None

    def test_process_single_listing_skips_below_threshold(self, aggregator):
        """Test that listings below review threshold are skipped."""
        reviews = [{"rating": 5, "review": "Only one review"}]
        aggregator.review_thresh_to_include_prop = 5

        result = aggregator.process_single_listing(reviews, "listing123")

        assert result is None

    def test_initialization_defaults(self):
        """Test that aggregator initializes with correct defaults."""
        with patch(
            "review_aggregator.openai_aggregator.load_json_file", return_value={}
        ):
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.property_review_aggregator import (
                        PropertyRagAggregator,
                    )

                    agg = PropertyRagAggregator()

                    assert agg.review_thresh_to_include_prop == 5
                    assert agg.zipcode == "00501"
                    assert agg.overall_mean == 0.0


class TestPropertyRagAggregatorFiltering:
    """Tests for PropertyRagAggregator filtering methods."""

    @pytest.fixture
    def aggregator(self):
        """Create a PropertyRagAggregator with mocked dependencies."""
        with patch("review_aggregator.openai_aggregator.load_json_file") as mock_load:
            mock_load.return_value = {
                "openai": {"enable_caching": False, "enable_cost_tracking": False}
            }
            with patch("utils.cache_manager.load_json_file", return_value={}):
                with patch("utils.cost_tracker.load_json_file", return_value={}):
                    from review_aggregator.property_review_aggregator import (
                        PropertyRagAggregator,
                    )

                    return PropertyRagAggregator(
                        zipcode="97067", num_listings_to_summarize=5
                    )

    def test_filter_out_processed_reviews(self, aggregator):
        """Test filtering out already processed reviews."""
        reviews = {
            "listing1": [{"rating": 5}],
            "listing2": [{"rating": 4}],
            "listing3": [{"rating": 3}],
        }
        already_processed = {"listing1": "summary1"}

        result = aggregator.filter_out_processed_reviews(reviews, already_processed)

        assert "listing1" not in result
        assert "listing2" in result
        assert "listing3" in result
        assert len(result) == 2

    def test_filter_out_processed_reviews_empty(self, aggregator):
        """Test filtering when nothing has been processed."""
        reviews = {"listing1": [], "listing2": []}
        already_processed = {}

        result = aggregator.filter_out_processed_reviews(reviews, already_processed)

        assert len(result) == 2

    def test_get_unfinished_aggregated_reviews(self, aggregator):
        """Test identifying reviews with incomplete summaries."""
        summaries = {
            "listing1": "Complete summary without issues",
            "listing2": "Summary with ? question marks",
            "listing3": "Another complete summary",
        }

        result = aggregator.get_unfinished_aggregated_reviews(summaries)

        assert "listing2" in result
        assert len(result) == 1

    def test_get_unfinished_aggregated_reviews_none(self, aggregator):
        """Test when all summaries are complete."""
        summaries = {
            "listing1": "Complete summary",
            "listing2": "Another complete summary",
        }

        result = aggregator.get_unfinished_aggregated_reviews(summaries)

        assert len(result) == 0

    def test_get_empty_aggregated_reviews(self, aggregator):
        """Test identifying empty summaries."""
        summaries = {
            "listing1": "Valid summary",
            "listing2": "",
            "listing3": None,
            "listing4": "Another valid",
        }

        result = aggregator.get_empty_aggregated_reviews(summaries)

        assert "listing2" in result
        assert "listing3" in result
        assert len(result) == 2

    def test_get_empty_aggregated_reviews_all_valid(self, aggregator):
        """Test when no summaries are empty."""
        summaries = {"listing1": "Valid", "listing2": "Also valid"}

        result = aggregator.get_empty_aggregated_reviews(summaries)

        assert len(result) == 0
