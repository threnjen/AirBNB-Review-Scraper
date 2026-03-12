import json
import glob


def find_icon_parents(obj, path=""):
    if isinstance(obj, dict):
        if (
            "icon" in obj
            and isinstance(obj["icon"], str)
            and obj["icon"].startswith("SYSTEM_")
        ):
            print(path)
        for k, v in obj.items():
            find_icon_parents(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            find_icon_parents(v, f"{path}[{i}]")


seen_paths = set()
for f in glob.glob("outputs/02_details_scrape/**/*.json", recursive=True)[:50]:
    d = json.load(open(f))
    import io, sys

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    find_icon_parents(d)
    sys.stdout = old
    for line in buf.getvalue().splitlines():
        # Normalize array indices to []
        import re

        norm = re.sub(r"\[\d+\]", "[]", line)
        seen_paths.add(norm)

for p in sorted(seen_paths):
    print(p)
