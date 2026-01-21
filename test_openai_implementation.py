#!/usr/bin/env python3
"""
Test script for OpenAI aggregator implementation.
This script tests the OpenAI integration without running the full pipeline.
"""

import os
import sys
from review_aggregator.openai_aggregator import OpenAIAggregator
from utils.cache_manager import CacheManager
from utils.cost_tracker import CostTracker


def test_openai_aggregator():
    """Test the OpenAI aggregator with sample data."""
    print("Testing OpenAI Aggregator Implementation")
    print("=" * 50)

    # Sample test data
    sample_reviews = [
        "5 Great location, clean apartment, friendly host. Would stay again!",
        "4 Nice place but a bit noisy at night. Good amenities though.",
        "5 Perfect for our weekend getaway. Everything was as described.",
        "3 Decent place but WiFi was slow. Host was responsive to issues.",
        "5 Amazing view from the balcony. Very comfortable bed.",
    ]

    sample_prompt = """Please analyze these Airbnb reviews and provide a structured summary with:
    1. Brief description
    2. Positive aspects mentioned
    3. Negative aspects mentioned 
    4. Overall rating analysis
    
    Reviews to analyze:"""

    # Test the aggregator
    try:
        aggregator = OpenAIAggregator()

        print(f"Model: {aggregator.model}")
        print(f"Temperature: {aggregator.temperature}")
        print(f"Max tokens: {aggregator.max_tokens}")
        print(f"Chunk size: {aggregator.chunk_size}")
        print()

        # Check if OpenAI API key is available
        if not os.getenv("OPENAI_API_KEY"):
            print("❌ OPENAI_API_KEY environment variable not set!")
            print("Please set your OpenAI API key in the .env file or environment.")
            return False
        else:
            print("✅ OpenAI API key found")

        print("\nTesting token estimation...")
        tokens = aggregator.estimate_tokens(sample_prompt + " ".join(sample_reviews))
        print(f"Estimated tokens for sample: {tokens}")

        print("\nTesting cache manager...")
        cache_stats = aggregator.cache_manager.get_cache_stats()
        print(f"Cache enabled: {cache_stats.get('enabled', False)}")

        print("\nTesting cost tracker...")
        cost_summary = aggregator.cost_tracker.get_session_summary()
        print(f"Cost tracking enabled: {cost_summary.get('tracking_enabled', False)}")

        print("\nGenerating summary for sample reviews...")
        summary = aggregator.generate_summary(
            reviews=sample_reviews, prompt=sample_prompt, listing_id="test_listing_123"
        )
        print("Generated Summary:")
        print(summary)

        print("\n" + "=" * 50)
        print("✅ All components initialized successfully!")
        print("The OpenAI aggregator is ready for use.")

        return True

    except Exception as e:
        print(f"❌ Error testing aggregator: {str(e)}")
        return False


def test_individual_components():
    """Test individual components."""
    print("\nTesting Individual Components")
    print("-" * 30)

    try:
        # Test CacheManager
        cache_manager = CacheManager()
        print(f"✅ CacheManager: {cache_manager.enable_cache}")

        # Test CostTracker
        cost_tracker = CostTracker()
        print(f"✅ CostTracker: {cost_tracker.enable_tracking}")

        # Test configuration loading
        from utils.tiny_file_handler import load_json_file

        config = load_json_file("config.json")
        openai_config = config.get("openai", {})
        print(f"✅ OpenAI config loaded: {bool(openai_config)}")

        return True

    except Exception as e:
        print(f"❌ Error testing components: {str(e)}")
        return False


if __name__ == "__main__":
    print("OpenAI Aggregator Test Suite")
    print("=" * 60)

    # Test individual components
    components_ok = test_individual_components()

    # Test main aggregator
    aggregator_ok = test_openai_aggregator()

    print("\n" + "=" * 60)
    if components_ok and aggregator_ok:
        print("🎉 ALL TESTS PASSED!")
        print("\nYour OpenAI aggregator is ready to replace Weaviate.")
        print("You can now run your main aggregation process.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)
