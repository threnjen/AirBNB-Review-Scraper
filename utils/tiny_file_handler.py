import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    """Load config.json from the repo root, regardless of working directory."""
    return load_json_file(str(_REPO_ROOT / "config.json"))


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
