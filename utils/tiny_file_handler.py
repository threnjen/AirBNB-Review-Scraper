import json


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
