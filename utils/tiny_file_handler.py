import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str = str(_REPO_ROOT / "config.json")) -> dict:
    """Load config.json from the repo root, regardless of working directory."""
    return load_json_file(path)


def validate_config(config: dict) -> None:
    """Validate required search-zone config keys.

    Raises ValueError with a descriptive message if any validation fails.
    """
    zone_name = config.get("search_zone_name", "")
    if not zone_name:
        raise ValueError("config missing required key: search_zone_name")
    if not re.match(r"^[a-zA-Z0-9_-]+$", zone_name):
        raise ValueError(
            f"search_zone_name must contain only letters, digits, underscores, "
            f"or hyphens; got: {zone_name!r}"
        )

    for key in ("start_lat", "start_long"):
        val = config.get(key)
        if val is None:
            raise ValueError(f"config missing required key: {key}")
        try:
            float(val)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a valid float; got: {val!r}")

    radius = config.get("search_radius_miles")
    if radius is None:
        raise ValueError("config missing required key: search_radius_miles")
    try:
        radius_float = float(radius)
    except (TypeError, ValueError):
        raise ValueError(f"search_radius_miles must be a valid number; got: {radius!r}")
    if radius_float <= 0:
        raise ValueError(f"search_radius_miles must be > 0; got: {radius_float}")


def load_json_file(filename):
    try:
        existing_file = open(filename).read()
        data = json.loads(existing_file)
        return data
    except FileNotFoundError:
        return {}


def save_json_file(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False))
