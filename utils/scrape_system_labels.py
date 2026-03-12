"""
Scrapes all SYSTEM_ icon label values from every property details file in
outputs/02_details_scrape and writes the results to
outputs/10_system_label_values/system_label_values.json.

Output format:
{
    "SYSTEM_FOO": {
        "titles": ["Title A", "Title B", ...],
        "sources": ["amenity", "highlight", ...]
    },
    ...
}
"""

import json
import os
import glob
from collections import defaultdict


INPUT_GLOB = os.path.join("outputs", "02_details_scrape", "**", "*.json")
OUTPUT_DIR = os.path.join("outputs", "10_system_label_values")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "system_label_values.json")


def collect_items(data: dict) -> list[dict]:
    """Return all dicts that have a SYSTEM_ icon key, with a 'source' field added."""
    items = []

    # amenities[].values[]
    for section in data.get("amenities", []):
        for item in section.get("values", []):
            if isinstance(item.get("icon"), str) and item["icon"].startswith("SYSTEM_"):
                items.append({**item, "source": "amenity"})

    # house_rules.general[].values[]
    for section in data.get("house_rules", {}).get("general", []):
        for item in section.get("values", []):
            if isinstance(item.get("icon"), str) and item["icon"].startswith("SYSTEM_"):
                items.append({**item, "source": "house_rule"})

    # highlights[]
    for item in data.get("highlights", []):
        if isinstance(item.get("icon"), str) and item["icon"].startswith("SYSTEM_"):
            items.append({**item, "source": "highlight"})

    # host_details prompts
    prompts = (
        data.get("host_details", {})
        .get("data", {})
        .get("node", {})
        .get("prompts", {})
        .get("displayProfilePrompts", [])
    )
    for item in prompts:
        if isinstance(item.get("icon"), str) and item["icon"].startswith("SYSTEM_"):
            items.append({**item, "source": "host_prompt"})

    return items


def main() -> None:
    titles: dict[str, set[str]] = defaultdict(set)
    sources: dict[str, set[str]] = defaultdict(set)

    files = glob.glob(INPUT_GLOB, recursive=True)
    if not files:
        print(f"No files found matching: {INPUT_GLOB}")
        return

    print(f"Processing {len(files)} files...")

    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  Skipping {path}: {e}")
            continue

        for item in collect_items(data):
            icon = item["icon"]
            title = item.get("title", "").strip()
            source = item["source"]
            if title:
                titles[icon].add(title)
            sources[icon].add(source)

    result = {
        icon: {
            "titles": sorted(titles[icon]),
            "sources": sorted(sources[icon]),
        }
        for icon in sorted(titles)
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Done. {len(result)} unique SYSTEM_ icons written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
