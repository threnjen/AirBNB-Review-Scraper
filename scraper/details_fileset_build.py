import json
import time
import random
import os
import pandas as pd


class DetailsFilesetBuilder:
    def __init__(self) -> None:
        self.property_amenities = {}

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
            # category_name = amenity_category.get("title")
            # print(category_name)
            category_values = amenity_category.get("values", [])

            for amenity in category_values:
                amenity_title = amenity.get("title")
                amenity_icon = amenity.get("icon")

                self.property_amenities[property_id][amenity_icon] = amenity_title
                # print(amenity_title)

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

            self.property_amenities[property_id] = {}

            self.parse_amenity_flags(property_id, property_details)

        amenities_df = pd.DataFrame.from_dict(
            self.property_amenities, orient="index"
        ).fillna(False)

        amenities_df.to_csv("results_property_details/property_amenities_matrix.csv")
        print(
            "Details fileset built and saved to results_property_details/property_amenities_matrix.csv"
        )
