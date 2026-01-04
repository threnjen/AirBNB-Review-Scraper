import json
import time
import random
import os
import pandas as pd


class DetailsFilesetBuilder:
    def __init__(self) -> None:
        self.property_details = {}
        self.house_rules = {}

    def get_files_list(self):
        files = os.listdir("results_property_details")
        property_details_files = [
            f
            for f in files
            if f.startswith("property_details_") and f.endswith(".json")
        ]
        return property_details_files

    def parse_amenity_flags(self, property_id: str, property_details: dict):
        amenities_dict = property_details.get("amenities_dift", {})

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

    def parse_basic_details(self, property_id: str, property_details: dict):
        print(property_details.keys())

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

        location_description = property_details.get("location_descriptions", "")
        print(location_description)

        return True

    def build_fileset(self):
        print("Building details fileset...")
        # Placeholder for actual implementation

        property_details_files = self.get_files_list()
        print(f"Found {len(property_details_files)} property details files.")

        for file_name in property_details_files:
            file = open(os.path.join("results_property_details", file_name), "r")
            property_details = json.load(file)
            file.close()
            property_id = file_name.split("property_details_")[-1].split(".json")[0]

            self.property_details[property_id] = {}

            if not self.parse_basic_details(property_id, property_details):
                continue

            self.parse_amenity_flags(property_id, property_details)

        # amenities_df = pd.DataFrame.from_dict(
        #     self.property_details, orient="index"
        # ).fillna(False)

        # amenities_df.to_csv("results_property_details/property_amenities_matrix.csv")
        # print(
        #     "Details fileset built and saved to results_property_details/property_amenities_matrix.csv"
        # )
