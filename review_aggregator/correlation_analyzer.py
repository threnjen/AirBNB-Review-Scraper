"""
CorrelationAnalyzer: Analyzes property attributes that correlate with high ADR and occupancy.
Segments properties into top/bottom percentiles and identifies differentiating features.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from review_aggregator.openai_aggregator import OpenAIAggregator
from utils.tiny_file_handler import load_json_file, save_json_file

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


# Metric configuration mapping
METRIC_CONFIG = {
    "adr": {
        "column": "ADR",
        "display_name": "Average Daily Rate",
        "unit": "$",
        "prompt_key": "adr_prompt",
    },
    "occupancy": {
        "column": "Occ_Rate_Based_on_Avail",
        "display_name": "Occupancy Rate",
        "unit": "%",
        "prompt_key": "occupancy_prompt",
    },
}

# Amenity columns to analyze for prevalence differences
AMENITY_COLUMNS = [
    "SYSTEM_PETS",
    "SYSTEM_JACUZZI",
    "SYSTEM_POOL",
    "SYSTEM_FIREPLACE",
    "SYSTEM_WI_FI",
    "SYSTEM_WORKSPACE",
    "SYSTEM_GRILL",
    "SYSTEM_FIREPIT",
    "SYSTEM_WASHER",
    "SYSTEM_DRYER",
    "SYSTEM_DISHWASHER",
    "SYSTEM_TV",
    "SYSTEM_SNOWFLAKE",  # AC
    "SYSTEM_SUPERHOST",
    "SYSTEM_POOL_TABLE",
    "SYSTEM_VIDEO_GAME",
    "SYSTEM_SAUNA",
    "SYSTEM_EV_CHARGER",
    "SYSTEM_VIEW_MOUNTAIN",
    "SYSTEM_VIEW_OCEAN",
    "SYSTEM_HAMMOCK",
    "SYSTEM_BEACH",
]

# Numeric columns for average comparison
NUMERIC_COLUMNS = ["capacity", "bedrooms", "beds", "bathrooms"]


class CorrelationAnalyzer(BaseModel):
    """Analyzes correlations between property attributes and revenue metrics."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    zipcode: str = "00000"
    metrics: list[str] = ["adr", "occupancy"]
    top_percentile: int = 25
    bottom_percentile: int = 25
    output_dir: str = "property_correlation_results"
    reports_dir: str = "reports"
    openai_aggregator: OpenAIAggregator = Field(default_factory=OpenAIAggregator)

    def load_property_data(self) -> pd.DataFrame:
        """Load property data from amenities matrix CSV."""
        csv_path = "property_details_results/property_amenities_matrix.csv"

        if not os.path.exists(csv_path):
            logger.error(f"Property amenities matrix not found at {csv_path}")
            logger.error("Run with build_details: true first to generate this file.")
            return pd.DataFrame()

        df = pd.read_csv(csv_path, index_col="property_id")
        logger.info(f"Loaded {len(df)} properties from {csv_path}")
        return df

    def load_descriptions(self) -> dict[str, str]:
        """Load property descriptions for LLM context."""
        desc_path = "property_details_results/property_descriptions.json"

        if not os.path.exists(desc_path):
            logger.warning(f"Property descriptions not found at {desc_path}")
            return {}

        descriptions = load_json_file(desc_path)
        logger.info(f"Loaded {len(descriptions)} property descriptions")
        return descriptions

    def segment_by_metric(
        self, df: pd.DataFrame, metric: str
    ) -> tuple[pd.DataFrame, pd.DataFrame, float, float]:
        """
        Split properties into high/low tiers based on percentile thresholds.

        Returns:
            (high_tier_df, low_tier_df, high_threshold, low_threshold)
        """
        config = METRIC_CONFIG.get(metric)
        if not config:
            logger.error(f"Unknown metric: {metric}")
            return pd.DataFrame(), pd.DataFrame(), 0.0, 0.0

        column = config["column"]

        # Filter to properties with valid metric values
        valid_df = df[df[column].notna() & (df[column] > 0)].copy()

        if len(valid_df) < 4:
            logger.warning(f"Not enough properties with valid {column} values")
            return pd.DataFrame(), pd.DataFrame(), 0.0, 0.0

        # Calculate percentile thresholds
        high_threshold = valid_df[column].quantile(1 - (self.top_percentile / 100))
        low_threshold = valid_df[column].quantile(self.bottom_percentile / 100)

        # Segment into tiers
        high_tier = valid_df[valid_df[column] >= high_threshold]
        low_tier = valid_df[valid_df[column] <= low_threshold]

        logger.info(
            f"{metric.upper()}: High tier >= {high_threshold:.2f} ({len(high_tier)} properties)"
        )
        logger.info(
            f"{metric.upper()}: Low tier <= {low_threshold:.2f} ({len(low_tier)} properties)"
        )

        return high_tier, low_tier, high_threshold, low_threshold

    def compute_amenity_prevalence(
        self, high_tier: pd.DataFrame, low_tier: pd.DataFrame
    ) -> dict[str, dict[str, float]]:
        """Calculate percentage of properties with each amenity per tier."""
        comparison = {}

        for col in AMENITY_COLUMNS:
            if col not in high_tier.columns:
                continue

            # Count non-False values (amenity present)
            # CSV stores the string "False", not Python bool False
            high_count = (high_tier[col] != "False").sum()
            low_count = (low_tier[col] != "False").sum()

            high_pct = (high_count / len(high_tier) * 100) if len(high_tier) > 0 else 0
            low_pct = (low_count / len(low_tier) * 100) if len(low_tier) > 0 else 0
            difference = high_pct - low_pct

            comparison[col] = {
                "high_tier_pct": round(high_pct, 1),
                "low_tier_pct": round(low_pct, 1),
                "difference": round(difference, 1),
            }

        # Sort by absolute difference descending
        comparison = dict(
            sorted(
                comparison.items(), key=lambda x: abs(x[1]["difference"]), reverse=True
            )
        )

        return comparison

    def compute_numeric_stats(
        self, high_tier: pd.DataFrame, low_tier: pd.DataFrame
    ) -> dict[str, dict[str, float]]:
        """Calculate average numeric values per tier."""
        comparison = {}

        for col in NUMERIC_COLUMNS:
            if col not in high_tier.columns:
                continue

            # Convert to numeric, coercing errors
            high_values = pd.to_numeric(high_tier[col], errors="coerce")
            low_values = pd.to_numeric(low_tier[col], errors="coerce")

            high_avg = high_values.mean() if not high_values.isna().all() else 0
            low_avg = low_values.mean() if not low_values.isna().all() else 0
            difference = high_avg - low_avg

            comparison[col] = {
                "high_tier_avg": round(high_avg, 2),
                "low_tier_avg": round(low_avg, 2),
                "difference": round(difference, 2),
            }

        return comparison

    def get_sample_descriptions(
        self,
        tier_df: pd.DataFrame,
        descriptions: dict[str, str],
        max_samples: int = 3,
    ) -> list[str]:
        """Extract sample descriptions from a tier for LLM context."""
        samples = []

        for prop_id in tier_df.index[:max_samples]:
            prop_id_str = str(prop_id)
            if prop_id_str in descriptions:
                desc = descriptions[prop_id_str]
                # Truncate long descriptions
                if isinstance(desc, list):
                    desc = " ".join(str(d) for d in desc[:3])
                if len(str(desc)) > 500:
                    desc = str(desc)[:500] + "..."
                samples.append(f"Property {prop_id_str}: {desc}")

        return samples

    def build_feature_comparison_text(
        self,
        amenity_comparison: dict,
        numeric_comparison: dict,
    ) -> str:
        """Format statistics as human-readable text for the prompt."""
        lines = []

        lines.append("### Amenity Prevalence (% of properties with feature)")
        lines.append("")
        lines.append("| Amenity | High Tier | Low Tier | Difference |")
        lines.append("|---------|-----------|----------|------------|")

        for amenity, stats in list(amenity_comparison.items())[:15]:
            # Clean up amenity name for display
            display_name = amenity.replace("SYSTEM_", "").replace("_", " ").title()
            lines.append(
                f"| {display_name} | {stats['high_tier_pct']}% | "
                f"{stats['low_tier_pct']}% | {stats['difference']:+.1f}% |"
            )

        lines.append("")
        lines.append("### Numeric Averages")
        lines.append("")
        lines.append("| Attribute | High Tier Avg | Low Tier Avg | Difference |")
        lines.append("|-----------|---------------|--------------|------------|")

        for attr, stats in numeric_comparison.items():
            display_name = attr.replace("_", " ").title()
            lines.append(
                f"| {display_name} | {stats['high_tier_avg']} | "
                f"{stats['low_tier_avg']} | {stats['difference']:+.2f} |"
            )

        return "\n".join(lines)

    def generate_insights(
        self,
        metric: str,
        feature_comparison_text: str,
        high_tier_descriptions: list[str],
        low_tier_descriptions: list[str],
        high_threshold: float,
        low_threshold: float,
    ) -> str:
        """Generate LLM insights for a metric."""
        config = METRIC_CONFIG.get(metric)
        if not config:
            return ""

        # Load prompt template
        prompt_data = load_json_file("prompts/correlation_prompt.json")
        prompt_template = prompt_data.get(config["prompt_key"], "")

        if not prompt_template:
            logger.error(f"No prompt template found for {metric}")
            return ""

        # Format threshold with unit
        unit = config["unit"]
        if unit == "$":
            high_str = f"${high_threshold:.2f}"
            low_str = f"${low_threshold:.2f}"
        else:
            high_str = f"{high_threshold:.1f}%"
            low_str = f"{low_threshold:.1f}%"

        # Replace placeholders
        prompt = prompt_template.replace("{ZIPCODE}", self.zipcode)
        prompt = prompt.replace("{HIGH_THRESHOLD}", high_str)
        prompt = prompt.replace("{LOW_THRESHOLD}", low_str)
        prompt = prompt.replace("{TOP_PERCENTILE}", str(self.top_percentile))
        prompt = prompt.replace("{BOTTOM_PERCENTILE}", str(self.bottom_percentile))
        prompt = prompt.replace("{FEATURE_COMPARISON}", feature_comparison_text)
        prompt = prompt.replace(
            "{HIGH_TIER_DESCRIPTIONS}",
            "\n\n".join(high_tier_descriptions) or "No descriptions available.",
        )
        prompt = prompt.replace(
            "{LOW_TIER_DESCRIPTIONS}",
            "\n\n".join(low_tier_descriptions) or "No descriptions available.",
        )

        # Generate insights using OpenAI
        insights = self.openai_aggregator.generate_summary(
            reviews=[prompt],
            prompt="Analyze the data and provide the requested insights in Markdown format.",
            listing_id=f"correlation_{metric}_{self.zipcode}",
        )

        return insights

    def save_results(
        self,
        metric: str,
        high_threshold: float,
        low_threshold: float,
        high_tier_count: int,
        low_tier_count: int,
        amenity_comparison: dict,
        numeric_comparison: dict,
        insights: str,
    ):
        """Save JSON stats and Markdown insights for a metric."""
        # Ensure output directory exists
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        config = METRIC_CONFIG.get(metric, {})

        # Build stats JSON
        stats = {
            "zipcode": self.zipcode,
            "metric": metric,
            "metric_column": config.get("column", ""),
            "high_tier_threshold": round(high_threshold, 2),
            "low_tier_threshold": round(low_threshold, 2),
            "high_tier_count": high_tier_count,
            "low_tier_count": low_tier_count,
            "top_percentile": self.top_percentile,
            "bottom_percentile": self.bottom_percentile,
            "amenity_comparison": amenity_comparison,
            "numeric_comparison": numeric_comparison,
        }

        # Save JSON
        json_path = f"{self.output_dir}/correlation_stats_{metric}_{self.zipcode}.json"
        save_json_file(json_path, stats)
        logger.info(f"Saved stats to {json_path}")

        # Save Markdown insights
        Path(self.reports_dir).mkdir(parents=True, exist_ok=True)
        md_path = f"{self.reports_dir}/correlation_insights_{metric}_{self.zipcode}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {config.get('display_name', metric)} Correlation Analysis\n\n")
            f.write(f"**Zipcode:** {self.zipcode}\n\n")
            f.write(
                f"**High Tier:** {config.get('unit', '')}{high_threshold:.2f} "
                f"(top {self.top_percentile}%, n={high_tier_count})\n\n"
            )
            f.write(
                f"**Low Tier:** {config.get('unit', '')}{low_threshold:.2f} "
                f"(bottom {self.bottom_percentile}%, n={low_tier_count})\n\n"
            )
            f.write("---\n\n")
            f.write(insights)

        logger.info(f"Saved insights to {md_path}")

    def run_analysis(self):
        """Main orchestrator: run analysis for each configured metric."""
        # Load data
        df = self.load_property_data()
        if df.empty:
            logger.error("No property data available. Exiting.")
            return

        descriptions = self.load_descriptions()

        # Process each metric
        for metric in self.metrics:
            if metric not in METRIC_CONFIG:
                logger.warning(f"Unknown metric '{metric}', skipping")
                continue

            logger.info(f"\n{'=' * 50}")
            logger.info(f"Analyzing {METRIC_CONFIG[metric]['display_name']}")
            logger.info(f"{'=' * 50}")

            # Segment properties
            high_tier, low_tier, high_threshold, low_threshold = self.segment_by_metric(
                df, metric
            )

            if high_tier.empty or low_tier.empty:
                logger.warning(f"Insufficient data for {metric} analysis")
                continue

            # Compute statistics
            amenity_comparison = self.compute_amenity_prevalence(high_tier, low_tier)
            numeric_comparison = self.compute_numeric_stats(high_tier, low_tier)

            # Get sample descriptions
            high_descriptions = self.get_sample_descriptions(
                high_tier, descriptions, max_samples=3
            )
            low_descriptions = self.get_sample_descriptions(
                low_tier, descriptions, max_samples=3
            )

            # Build comparison text for prompt
            feature_comparison_text = self.build_feature_comparison_text(
                amenity_comparison, numeric_comparison
            )

            # Generate LLM insights
            insights = self.generate_insights(
                metric=metric,
                feature_comparison_text=feature_comparison_text,
                high_tier_descriptions=high_descriptions,
                low_tier_descriptions=low_descriptions,
                high_threshold=high_threshold,
                low_threshold=low_threshold,
            )

            # Save results
            self.save_results(
                metric=metric,
                high_threshold=high_threshold,
                low_threshold=low_threshold,
                high_tier_count=len(high_tier),
                low_tier_count=len(low_tier),
                amenity_comparison=amenity_comparison,
                numeric_comparison=numeric_comparison,
                insights=insights,
            )

        # Log cost summary
        self.openai_aggregator.cost_tracker.print_session_summary()
        self.openai_aggregator.cost_tracker.log_session()

        logger.info("\nCorrelation analysis complete.")
