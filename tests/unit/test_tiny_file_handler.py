"""
Unit tests for utils/tiny_file_handler.py
"""

import json

import pytest

from utils.tiny_file_handler import load_json_file, save_json_file


class TestLoadJsonFile:
    """Tests for load_json_file function."""

    def test_load_json_file_valid_file(self, tmp_path):
        """Test loading a valid JSON file."""
        test_data = {"key": "value", "number": 42}
        test_file = tmp_path / "test.json"

        with open(test_file, "w") as f:
            json.dump(test_data, f)

        result = load_json_file(str(test_file))

        assert result == test_data

    def test_load_json_file_not_found(self, tmp_path):
        """Test loading a non-existent file returns empty dict."""
        non_existent = tmp_path / "does_not_exist.json"

        result = load_json_file(str(non_existent))

        assert result == {}

    def test_load_json_file_empty_file(self, tmp_path):
        """Test loading an empty file raises exception (invalid JSON)."""
        empty_file = tmp_path / "empty.json"
        empty_file.touch()

        # Empty file is invalid JSON - should raise
        with pytest.raises(json.JSONDecodeError):
            load_json_file(str(empty_file))

    def test_load_json_file_nested_structure(self, tmp_path):
        """Test loading a file with nested JSON structure."""
        test_data = {
            "level1": {"level2": {"items": [1, 2, 3], "nested_str": "hello"}},
            "array": ["a", "b", "c"],
        }
        test_file = tmp_path / "nested.json"

        with open(test_file, "w") as f:
            json.dump(test_data, f)

        result = load_json_file(str(test_file))

        assert result == test_data
        assert result["level1"]["level2"]["items"] == [1, 2, 3]


class TestSaveJsonFile:
    """Tests for save_json_file function."""

    def test_save_json_file_creates_file(self, tmp_path):
        """Test saving creates a new JSON file."""
        test_data = {"name": "test", "value": 123}
        test_file = tmp_path / "output.json"

        save_json_file(str(test_file), test_data)

        assert test_file.exists()
        with open(test_file, "r") as f:
            saved_data = json.load(f)
        assert saved_data == test_data

    def test_save_json_file_overwrites_existing(self, tmp_path):
        """Test saving overwrites an existing file."""
        test_file = tmp_path / "existing.json"

        # Create initial file
        initial_data = {"initial": "data"}
        with open(test_file, "w") as f:
            json.dump(initial_data, f)

        # Overwrite with new data
        new_data = {"new": "content", "count": 99}
        save_json_file(str(test_file), new_data)

        with open(test_file, "r") as f:
            saved_data = json.load(f)
        assert saved_data == new_data
        assert "initial" not in saved_data

    def test_save_json_file_unicode_content(self, tmp_path):
        """Test saving handles unicode characters correctly."""
        test_data = {"greeting": "Hello 世界", "emoji": "🏠"}
        test_file = tmp_path / "unicode.json"

        save_json_file(str(test_file), test_data)

        with open(test_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == test_data

    def test_save_json_file_empty_dict(self, tmp_path):
        """Test saving an empty dictionary."""
        test_file = tmp_path / "empty.json"

        save_json_file(str(test_file), {})

        with open(test_file, "r") as f:
            saved_data = json.load(f)
        assert saved_data == {}

    def test_save_json_file_list_data(self, tmp_path):
        """Test saving a list as JSON."""
        test_data = [1, 2, 3, {"nested": "object"}]
        test_file = tmp_path / "list.json"

        save_json_file(str(test_file), test_data)

        with open(test_file, "r") as f:
            saved_data = json.load(f)
        assert saved_data == test_data
