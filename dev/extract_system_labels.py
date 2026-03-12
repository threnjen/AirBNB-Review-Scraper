import json
import os
from collections import defaultdict

data_dir = "outputs/02_details_scrape/mt_hood"
titles_by_icon = defaultdict(set)

for fname in os.listdir(data_dir):
    if not fname.endswith(".json"):
        continue
    try:
        with open(os.path.join(data_dir, fname)) as f:
            data = json.load(f)
    except Exception:
        continue

    # Scan amenities
    for section in data.get("amenities", []):
        for item in section.get("values", []):
            icon = item.get("icon", "")
            title = item.get("title", "")
            if icon.startswith("SYSTEM_") and title:
                titles_by_icon[icon].add(title)

    # Scan house_rules
    for section in data.get("house_rules", {}).get("general", []):
        for item in section.get("values", []):
            icon = item.get("icon", "")
            title = item.get("title", "")
            if icon.startswith("SYSTEM_") and title:
                titles_by_icon[icon].add(title)

    # Scan highlights
    for item in data.get("highlights", []):
        icon = item.get("icon", "")
        title = item.get("title", "")
        if icon.startswith("SYSTEM_") and title:
            titles_by_icon[icon].add(title)

    # Scan checkout_instructions (top-level list of dicts)
    for section in data.get("checkout_instructions", []):
        icon = section.get("icon", "")
        title = section.get("title", "")
        if icon.startswith("SYSTEM_") and title:
            titles_by_icon[icon].add(title)
        for item in section.get("items", []):
            icon2 = item.get("icon", "")
            title2 = item.get("title", "")
            if icon2.startswith("SYSTEM_") and title2:
                titles_by_icon[icon2].add(title2)

for icon in sorted(titles_by_icon):
    print(f"\n{icon}:")
    for t in sorted(titles_by_icon[icon]):
        print(f"  - {t}")
