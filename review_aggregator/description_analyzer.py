"""
DescriptionAnalyzer: Evaluates listing description quality and its impact on ADR.

Normalizes for hard features (capacity, bedrooms, beds, bathrooms) via OLS
regression, then scores each description on quality dimensions using an LLM,
and correlates those scores with the size-adjusted ADR premium (residual).
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from review_aggregator.openai_aggregator import OpenAIAggregator
from utils.tiny_file_handler import load_json_file, save_json_file

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Hard features used to normalize ADR
SIZE_FEATURES = ["capacity", "bedrooms", "beds", "bathrooms"]

# Quality dimensions the LLM scores each description on (1-10)
SCORE_DIMENSIONS = [
    "evocativeness",
    "specificity",
    "emotional_appeal",
    "storytelling",
    "usp_clarity",
    "professionalism",
    "completeness",
]


class DescriptionAnalyzer(BaseModel):
    """Analyzes how listing description quality impacts ADR beyond property size."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    zipcode: str = "00000"
    output_dir: str = "property_correlation_results"
    openai_aggregator: OpenAIAggregator = Field(default_factory=OpenAIAggregator)

    def load_property_data(self) -> pd.DataFrame:
        """Load property data from amenities matrix CSV."""
        csv_path = "property_details_results/property_amenities_matrix.csv"

        if not os.path.exists(csv_path):
            logger.error(f"Property amenities matrix not found at {csv_path}")
            return pd.DataFrame()

        df = pd.read_csv(csv_path, index_col="property_id")
        logger.info(f"Loaded {len(df)} properties from {csv_path}")
        return df

    def load_descriptions(self) -> dict[str, str]:
        """Load property descriptions for analysis."""
        desc_path = "property_details_results/property_descriptions.json"

        if not os.path.exists(desc_path):
            logger.warning(f"Property descriptions not found at {desc_path}")
            return {}

        descriptions = load_json_file(desc_path)
        logger.info(f"Loaded {len(descriptions)} property descriptions")
        return descriptions

    def compute_size_adjusted_residuals(
        self, df: pd.DataFrame
    ) -> tuple[pd.Series, float]:
        """
        Fit OLS regression: ADR ~ capacity + bedrooms + beds + bathrooms.
        Return residuals (actual - predicted) and R-squared.

        Residual > 0 means the property earns MORE than its size predicts.
        Residual < 0 means it earns LESS.
        """
        # Filter to valid ADR rows
        valid = df[df["ADR"].notna() & (df["ADR"] > 0)].copy()

        if len(valid) < len(SIZE_FEATURES) + 1:
            logger.warning(
                f"Not enough properties ({len(valid)}) for regression. "
                f"Need at least {len(SIZE_FEATURES) + 1}."
            )
            return pd.Series(dtype=float), 0.0

        y = valid["ADR"].values
        # Build design matrix with intercept column
        X = np.column_stack(
            [np.ones(len(valid))]
            + [
                pd.to_numeric(valid[col], errors="coerce").fillna(0).values
                for col in SIZE_FEATURES
            ]
        )

        # OLS via numpy least squares
        coeffs, residual_ss, _, _ = np.linalg.lstsq(X, y, rcond=None)

        predicted = X @ coeffs
        residuals = y - predicted

        # R-squared
        ss_total = np.sum((y - np.mean(y)) ** 2)
        ss_residual = np.sum(residuals**2)
        r_squared = 1 - (ss_residual / ss_total) if ss_total > 0 else 0.0

        residual_series = pd.Series(residuals, index=valid.index, name="adr_residual")

        logger.info(
            f"OLS R² = {r_squared:.3f} | "
            f"Coefficients: intercept={coeffs[0]:.1f}, "
            + ", ".join(
                f"{feat}={coeffs[i + 1]:.1f}" for i, feat in enumerate(SIZE_FEATURES)
            )
        )

        return residual_series, r_squared

    def parse_score_response(self, response: Optional[str]) -> dict[str, int]:
        """Parse the LLM scoring response into a dimension → score dict."""
        if response is None:
            return {}

        # Strip markdown code fences if present
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```\s*$", "", text)

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if isinstance(v, (int, float))}
        except (json.JSONDecodeError, TypeError):
            pass

        return {}

    def score_single_description(
        self, property_id: str, description: str, prompt_template: str
    ) -> dict[str, int]:
        """Score a single description using the LLM."""
        prompt = prompt_template.replace("{DESCRIPTION}", description)
        prompt = prompt.replace("{PROPERTY_ID}", property_id)

        response = self.openai_aggregator.generate_summary(
            reviews=[prompt],
            prompt="Score this listing description on the specified quality dimensions. Return ONLY valid JSON.",
            listing_id=f"desc_score_{property_id}",
        )

        return self.parse_score_response(response)

    def score_all_descriptions(
        self,
        residuals: pd.Series,
        descriptions: dict[str, str],
        prompt_template: str,
    ) -> pd.DataFrame:
        """Score every description that has a valid residual."""
        scores_list = []

        for prop_id in residuals.index:
            prop_id_str = str(prop_id)
            if prop_id_str not in descriptions:
                logger.debug(f"No description for {prop_id_str}, skipping")
                continue

            desc = descriptions[prop_id_str]
            if isinstance(desc, list):
                desc = " ".join(str(d) for d in desc)

            scores = self.score_single_description(prop_id_str, desc, prompt_template)

            if scores:
                scores["property_id"] = prop_id_str
                scores["word_count"] = len(desc.split())
                scores_list.append(scores)
            else:
                logger.warning(f"Failed to score description for {prop_id_str}")

        if not scores_list:
            return pd.DataFrame()

        scores_df = pd.DataFrame(scores_list).set_index("property_id")
        logger.info(f"Scored {len(scores_df)} descriptions")
        return scores_df

    def correlate_scores_with_premium(
        self, scores_df: pd.DataFrame, residuals: pd.Series
    ) -> dict[str, dict[str, float]]:
        """Compute Pearson correlation between each score dimension and residual."""
        results = {}

        # Align indices
        common_idx = scores_df.index.intersection(residuals.index.astype(str))
        if len(common_idx) < 3:
            logger.warning(f"Only {len(common_idx)} matched properties, need >= 3")
            return {}

        aligned_residuals = residuals.loc[residuals.index.astype(str).isin(common_idx)]
        aligned_residuals.index = aligned_residuals.index.astype(str)
        aligned_scores = scores_df.loc[common_idx]

        for col in aligned_scores.columns:
            values = pd.to_numeric(aligned_scores[col], errors="coerce")
            if values.isna().all():
                continue

            # Drop NaN pairs
            valid = values.notna()
            if valid.sum() < 3:
                continue

            x = values[valid].values.astype(float)
            y = aligned_residuals[valid].values.astype(float)

            # Pearson correlation
            if np.std(x) == 0 or np.std(y) == 0:
                corr = 0.0
            else:
                corr = float(np.corrcoef(x, y)[0, 1])

            results[col] = {
                "correlation": round(corr, 4),
                "n": int(valid.sum()),
            }

        # Sort by absolute correlation descending
        results = dict(
            sorted(
                results.items(), key=lambda x: abs(x[1]["correlation"]), reverse=True
            )
        )

        return results

    def generate_synthesis(
        self,
        r_squared: float,
        correlation_results: dict,
        residuals: pd.Series,
        descriptions: dict[str, str],
        scores_df: pd.DataFrame,
        synthesis_prompt_template: str,
    ) -> str:
        """Generate the final synthesis report comparing best vs worst descriptions."""
        # Get top 5 and bottom 5 by residual
        sorted_residuals = residuals.sort_values(ascending=False)
        top_ids = [str(x) for x in sorted_residuals.head(5).index]
        bottom_ids = [str(x) for x in sorted_residuals.tail(5).index]

        def format_descriptions(prop_ids: list[str]) -> str:
            lines = []
            for pid in prop_ids:
                if pid in descriptions:
                    residual_val = float(
                        residuals.loc[residuals.index.astype(str) == pid].iloc[0]
                    )
                    desc = descriptions[pid]
                    if isinstance(desc, list):
                        desc = " ".join(str(d) for d in desc)

                    # Include scores if available
                    score_info = ""
                    if pid in scores_df.index:
                        row = scores_df.loc[pid]
                        score_parts = [
                            f"{dim}: {row[dim]}"
                            for dim in SCORE_DIMENSIONS
                            if dim in row.index
                        ]
                        score_info = f"\n  Scores: {', '.join(score_parts)}"

                    lines.append(
                        f"**Property {pid}** (ADR premium: ${residual_val:+.0f}/night)"
                        f"{score_info}\n{desc}\n"
                    )
            return "\n".join(lines)

        high_premium_text = format_descriptions(top_ids)
        low_premium_text = format_descriptions(bottom_ids)

        # Format correlation table
        corr_lines = [
            "| Dimension | Correlation | n |",
            "|-----------|-------------|---|",
        ]
        for dim, stats in correlation_results.items():
            corr_lines.append(
                f"| {dim.replace('_', ' ').title()} | {stats['correlation']:+.3f} | {stats['n']} |"
            )
        correlation_table = "\n".join(corr_lines)

        # Fill prompt
        prompt = synthesis_prompt_template.replace("{ZIPCODE}", self.zipcode)
        prompt = prompt.replace("{R_SQUARED}", f"{r_squared:.3f}")
        prompt = prompt.replace("{CORRELATION_TABLE}", correlation_table)
        prompt = prompt.replace("{HIGH_PREMIUM_DESCRIPTIONS}", high_premium_text)
        prompt = prompt.replace("{LOW_PREMIUM_DESCRIPTIONS}", low_premium_text)
        prompt = prompt.replace("{NUM_PROPERTIES}", str(len(residuals)))

        synthesis = self.openai_aggregator.generate_summary(
            reviews=[prompt],
            prompt="Analyze the description data and provide the requested insights in Markdown format.",
            listing_id=f"desc_synthesis_{self.zipcode}",
        )

        return synthesis or ""

    def save_results(
        self,
        r_squared: float,
        correlation_results: dict,
        residuals: pd.Series,
        scores_df: pd.DataFrame,
        synthesis: str,
    ):
        """Save JSON stats and Markdown insights."""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        # Build stats JSON
        stats = {
            "zipcode": self.zipcode,
            "analysis_type": "description_quality",
            "regression_r_squared": round(r_squared, 4),
            "size_features_used": SIZE_FEATURES,
            "num_properties_analyzed": len(residuals),
            "num_descriptions_scored": len(scores_df),
            "score_dimensions": SCORE_DIMENSIONS,
            "dimension_correlations": correlation_results,
            "residual_stats": {
                "mean": round(float(residuals.mean()), 2),
                "std": round(float(residuals.std()), 2),
                "min": round(float(residuals.min()), 2),
                "max": round(float(residuals.max()), 2),
            },
        }

        json_path = f"{self.output_dir}/description_quality_stats_{self.zipcode}.json"
        save_json_file(json_path, stats)
        logger.info(f"Saved description quality stats to {json_path}")

        # Save Markdown insights
        md_path = f"{self.output_dir}/description_quality_{self.zipcode}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Listing Description Quality Analysis\n\n")
            f.write(f"**Zipcode:** {self.zipcode}\n\n")
            f.write(
                f"**Size-Adjustment R²:** {r_squared:.3f} "
                f"(proportion of ADR variance explained by "
                f"capacity, bedrooms, beds, bathrooms)\n\n"
            )
            f.write(
                f"**Properties Analyzed:** {len(residuals)} "
                f"({len(scores_df)} descriptions scored)\n\n"
            )
            f.write("---\n\n")
            f.write(synthesis)

        logger.info(f"Saved description quality insights to {md_path}")

    def run_analysis(self):
        """Main orchestrator: run description quality analysis."""
        # Load data
        df = self.load_property_data()
        if df.empty:
            logger.error("No property data available. Exiting.")
            return

        descriptions = self.load_descriptions()
        if not descriptions:
            logger.error("No descriptions available. Exiting.")
            return

        # Step 1: Compute size-adjusted residuals
        logger.info("\n" + "=" * 50)
        logger.info("Step 1: Computing size-adjusted ADR residuals")
        logger.info("=" * 50)

        residuals, r_squared = self.compute_size_adjusted_residuals(df)
        if residuals.empty:
            logger.error("Failed to compute residuals. Exiting.")
            return

        # Step 2: Score all descriptions
        logger.info("\n" + "=" * 50)
        logger.info("Step 2: Scoring description quality with LLM")
        logger.info("=" * 50)

        prompt_data = load_json_file("prompts/description_analysis_prompt.json")
        scoring_prompt = prompt_data.get("scoring_prompt", "")

        if not scoring_prompt:
            logger.error("No scoring prompt template found")
            return

        scores_df = self.score_all_descriptions(residuals, descriptions, scoring_prompt)

        if scores_df.empty:
            logger.error("No descriptions could be scored. Exiting.")
            return

        # Step 3: Correlate scores with premium
        logger.info("\n" + "=" * 50)
        logger.info("Step 3: Correlating description quality with ADR premium")
        logger.info("=" * 50)

        correlation_results = self.correlate_scores_with_premium(scores_df, residuals)

        for dim, stats in correlation_results.items():
            logger.info(f"  {dim}: r={stats['correlation']:+.3f} (n={stats['n']})")

        # Step 4: Generate synthesis
        logger.info("\n" + "=" * 50)
        logger.info("Step 4: Generating synthesis report")
        logger.info("=" * 50)

        synthesis_prompt = prompt_data.get("synthesis_prompt", "")
        synthesis = self.generate_synthesis(
            r_squared=r_squared,
            correlation_results=correlation_results,
            residuals=residuals,
            descriptions=descriptions,
            scores_df=scores_df,
            synthesis_prompt_template=synthesis_prompt,
        )

        # Step 5: Save results
        self.save_results(
            r_squared=r_squared,
            correlation_results=correlation_results,
            residuals=residuals,
            scores_df=scores_df,
            synthesis=synthesis,
        )

        # Log cost summary
        self.openai_aggregator.cost_tracker.print_session_summary()
        self.openai_aggregator.cost_tracker.log_session()

        logger.info("\nDescription quality analysis complete.")
