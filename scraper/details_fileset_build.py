import json
import os
import pandas as pd
from math import ceil


class DetailsFilesetBuilder:
    def __init__(self) -> None:
        self.property_details = {}
        self.house_rules = {}
        self.property_descriptions = {}
        self.neighborhood_highlights = {}

    def get_files_list(self):
        files = os.listdir("property_details_results")
        property_details_files = [
            f
            for f in files
            if f.startswith("property_details_") and f.endswith(".json")
        ]
        return property_details_files

    def parse_amenity_flags(self, property_id: str, property_details: dict):
        amenities_matrix = property_details.get("amenities", {})

        for amenity_category in amenities_matrix:
            category_values = amenity_category.get("values", [])

            for amenity in category_values:
                amenity_title = amenity.get("title")
                amenity_icon = amenity.get("icon")

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

    def parse_basic_details(self, property_id: str, property_details: dict):
        room_type = property_details.get("room_type", "N/A")

        if not room_type == "Entire home/apt":
            print(f"Skipping property {property_id} as it is not an entire home/apt")
            return False

        person_capacity = property_details.get("person_capacity", 0)
        self.property_details[property_id]["capacity"] = person_capacity

        ratings = property_details.get("rating", {})
        self.property_details[property_id].update(ratings)

        house_rules = property_details.get("house_rules", {})
        self.house_rules[property_id] = house_rules.get("aditional")

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

        # host_details = property_details.get("host_details", {})
        # print(host_details)

        return True

    def get_financials(self, property_id: str, property_details: dict):
        adr = property_details.get("ADR", None)
        self.property_details[property_id]["ADR"] = adr

        occupancy_rate_based_on_available_days = property_details.get("Occupancy", None)
        self.property_details[property_id]["Occ_Rate_Based_on_Avail"] = (
            occupancy_rate_based_on_available_days
        )

        days_available = property_details.get("Days_Avail", None)
        self.property_details[property_id]["Days_Available"] = days_available

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

    def build_fileset(self):
        print("Building details fileset...")
        # Placeholder for actual implementation

        if os.path.isfile("custom_listing_ids.json"):
            with open("custom_listing_ids.json", "r", encoding="utf-8") as f:
                properties = json.load(f)

            for property_id, property_details in properties.items():
                self.property_details[property_id] = {}
                self.get_financials(
                    property_id=property_id, property_details=property_details
                )

        property_details_files = self.get_files_list()
        print(f"Found {len(property_details_files)} property details files.")

        for file_name in property_details_files:
            file = open(os.path.join("property_details_results", file_name), "r")
            property_details = json.load(file)
            file.close()
            property_id = file_name.split("property_details_")[-1].split(".json")[0]

            if not self.parse_basic_details(property_id, property_details):
                continue

            self.parse_amenity_flags(property_id, property_details)

        amenities_df = pd.DataFrame.from_dict(
            self.property_details, orient="index"
        ).fillna(False)

        amenities_df.to_csv("property_details_results/property_amenities_matrix.csv")
        print(
            "Details fileset built and saved to property_details_results/property_amenities_matrix.csv"
        )

        with open(
            "property_details_results/house_rules_details.json", "w"
        ) as house_rules_file:
            json.dump(self.house_rules, house_rules_file, indent=4)

        with open(
            "property_details_results/property_descriptions.json", "w"
        ) as descriptions_file:
            json.dump(self.property_descriptions, descriptions_file, indent=4)

        with open(
            "property_details_results/neighborhood_highlights.json", "w"
        ) as highlights_file:
            json.dump(self.neighborhood_highlights, highlights_file, indent=4)
