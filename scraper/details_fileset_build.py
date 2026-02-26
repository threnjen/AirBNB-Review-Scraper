import json
import logging
import os
import sys
from math import ceil

import pandas as pd

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

DETAILS_SCRAPED_DIR = "outputs/04_details_scraped"


class DetailsFilesetBuilder:
    def __init__(
        self, use_categoricals: bool, comp_set_filepath: str = "custom_listing_ids.json"
    ) -> None:
        self.use_categoricals = use_categoricals
        self.comp_set_filepath = comp_set_filepath
        self.property_details = {}
        self.house_rules = {}
        self.property_descriptions = {}
        self.neighborhood_highlights = {}

    def get_financials(self, property_id: str, property_details: dict):
        adr = property_details.get("ADR", None)
        self.property_details[property_id]["ADR"] = adr

        occupancy_rate_based_on_available_days = property_details.get("Occupancy", 0)
        self.property_details[property_id]["Occ_Rate_Based_on_Avail"] = (
            occupancy_rate_based_on_available_days
        )

        days_available = property_details.get("Days_Available", 0)
        self.property_details[property_id]["Days_Avail"] = days_available

        occupied_days = (
            (occupancy_rate_based_on_available_days / 100 * days_available) * 100 / 365
            if occupancy_rate_based_on_available_days is not None
            else None
        )
        self.property_details[property_id]["Abs_Occ_Rate"] = (
            ceil(occupied_days) if occupied_days is not None else None
        )

        availability = (
            (days_available / 365) * 100 if days_available is not None else None
        )
        self.property_details[property_id]["Avail_Rate"] = (
            round(availability, 2) if availability is not None else None
        )

    def parse_basic_details(self, property_id: str, property_details: dict):
        room_type = property_details.get("room_type", "N/A")

        if not room_type == "Entire home/apt":
            logger.info(
                f"Skipping property {property_id} as it is not an entire home/apt"
            )
            return False

        person_capacity = property_details.get("person_capacity", 0)
        self.property_details[property_id]["capacity"] = person_capacity

        ratings = property_details.get("rating", {})
        self.property_details[property_id].update(ratings)

        house_rules = property_details.get("house_rules", {})
        self.house_rules[property_id] = house_rules.get("aditional")

        title = property_details.get("title", {})
        self.property_details[property_id]["title"] = title

        sub_details = property_details.get("sub_description", {}).get("items", [])

        if "bedrooms" in sub_details[1]:
            bedrooms = sub_details[1].split(" bedrooms")[0]
            self.property_details[property_id]["bedrooms"] = bedrooms

        if "beds" in sub_details[2]:
            beds = sub_details[2].split(" beds")[0]
            self.property_details[property_id]["beds"] = beds
        else:
            bathrooms = sub_details[2].split(" baths")[0]

        # check if sub_details[3] exists
        if len(sub_details) > 3 and "baths" in sub_details[3]:
            bathrooms = sub_details[3].split(" baths")[0]
            self.property_details[property_id]["bathrooms"] = bathrooms

        # TO DO location description
        location_description = property_details.get("location_descriptions", "")
        if len(location_description) > 0:
            if location_description[0].get("title") == "Neighborhood highlights":
                neighborhood_highlights = location_description[0].get("content")
                self.neighborhood_highlights[property_id] = neighborhood_highlights

        description = property_details.get("description", [])
        self.property_descriptions[property_id] = description

        return True

    def clean_amenities_df(self, df: pd.DataFrame) -> pd.DataFrame:
        drop_cols = [
            "link",
            "property_id",
            "Occ_Rate_Based_on_Avail",
            "Abs_Occ_Rate",
            "Avail_Rate",
            "title",
            "review_count",
            "accuracy",
            "checking",
            "cleanliness",
            "communication",
            "location",
            "value",
            "guest_satisfaction",
        ]
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

        # replace any remaining False values with 0
        with pd.option_context("future.no_silent_downcasting", True):
            df = df.replace("False", 0).infer_objects(copy=False)
            df = df.replace(False, 0).infer_objects(copy=False)

        system_colums = [x for x in df.columns if x.startswith("SYSTEM_")]
        if system_colums:
            df[system_colums] = df[system_colums].astype(bool)
            df[system_colums] = df[system_colums].astype(int)

        if "beds" in df.columns:
            df["beds"] = df["beds"].astype(int)
        if "bathrooms" in df.columns:
            df["bathrooms"] = df["bathrooms"].astype(float)
        if "bedrooms" in df.columns:
            df["bedrooms"] = df["bedrooms"].astype(int)

        return df

    def parse_amenity_flags(self, property_id: str, property_details: dict):
        amenities_matrix = property_details.get("amenities", {})

        for amenity_category in amenities_matrix:
            category_values = amenity_category.get("values", [])

            for amenity in category_values:
                amenity_title = amenity.get("title")
                amenity_icon = amenity.get("icon")

                if self.use_categoricals:
                    self.property_details[property_id][amenity_icon] = True
                else:
                    self.property_details[property_id][amenity_icon] = amenity_title

        house_rules_section = property_details.get("house_rules", {}).get("general", [])
        for rule_category in house_rules_section:
            category_values = rule_category.get("values", [])
            for rule in category_values:
                rule_title = rule.get("title")
                rule_icon = rule.get("icon")
                self.property_details[property_id][rule_icon] = rule_title

        highlights_section = property_details.get("highlights", [])
        for highlight in highlights_section:
            highlight_title = highlight.get("title")
            highlight_icon = highlight.get("icon")
            self.property_details[property_id][highlight_icon] = highlight_title

    def build_fileset(self):
        logger.info("Building details fileset...")

        # Discover property IDs from files on disk
        if not os.path.isdir(DETAILS_SCRAPED_DIR):
            logger.info(
                f"No details directory found at {DETAILS_SCRAPED_DIR}. "
                "Please run details scraping first."
            )
            return

        detail_files = [
            f
            for f in os.listdir(DETAILS_SCRAPED_DIR)
            if f.startswith("property_details_") and f.endswith(".json")
        ]

        if not detail_files:
            logger.info("No property detail files found in the directory.")
            return

        logger.info(f"Found {len(detail_files)} property details files on disk.")

        # Load comp set financials if available
        comp_set_data = {}
        if os.path.isfile(self.comp_set_filepath):
            with open(self.comp_set_filepath, "r", encoding="utf-8") as f:
                comp_set_data = json.load(f)
            logger.info(
                f"Loaded financial data for {len(comp_set_data)} properties from comp set."
            )

        for file_name in detail_files:
            property_id = file_name.replace("property_details_", "").replace(
                ".json", ""
            )

            self.property_details[property_id] = {}
            self.property_details[property_id]["link"] = (
                f"https://www.airbnb.com/rooms/{property_id}"
            )

            # Merge financials if available in comp set
            if property_id in comp_set_data:
                self.get_financials(
                    property_id=property_id,
                    property_details=comp_set_data[property_id],
                )

            file_path = os.path.join(DETAILS_SCRAPED_DIR, file_name)
            with open(file_path, "r") as file:
                property_details = json.load(file)

            if not self.parse_basic_details(property_id, property_details):
                continue

            self.parse_amenity_flags(property_id, property_details)

        amenities_df = pd.DataFrame.from_dict(
            self.property_details, orient="index"
        ).fillna(False)

        if "ADR" in amenities_df.columns:
            amenities_df = amenities_df.sort_values(by="ADR", ascending=False)

        amenities_df.index.name = "property_id"

        os.makedirs("outputs/05_details_results", exist_ok=True)
        amenities_df.to_csv("outputs/05_details_results/property_amenities_matrix.csv")
        logger.info(
            "Details fileset built and saved to outputs/05_details_results/property_amenities_matrix.csv"
        )

        cleaned_df = self.clean_amenities_df(amenities_df)
        cleaned_df.to_csv(
            "outputs/05_details_results/property_amenities_matrix_cleaned.csv"
        )
        logger.info(
            "Cleaned details fileset saved to outputs/05_details_results/property_amenities_matrix_cleaned.csv"
        )

        with open(
            "outputs/05_details_results/house_rules_details.json", "w"
        ) as house_rules_file:
            json.dump(self.house_rules, house_rules_file, indent=4)

        with open(
            "outputs/05_details_results/property_descriptions.json", "w"
        ) as descriptions_file:
            json.dump(self.property_descriptions, descriptions_file, indent=4)

        with open(
            "outputs/05_details_results/neighborhood_highlights.json", "w"
        ) as highlights_file:
            json.dump(self.neighborhood_highlights, highlights_file, indent=4)
