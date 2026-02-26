"""
Unit tests for utils/local_file_handler.py
"""

import pytest

from utils.local_file_handler import LocalFileHandler


class TestLocalFileHandler:
    """Tests for LocalFileHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a LocalFileHandler instance."""
        return LocalFileHandler()

    def test_clear_directory_removes_files_and_subdirs(self, handler, tmp_path):
        """Test clear_directory removes all files and subdirectories."""
        target_dir = tmp_path / "to_clear"
        target_dir.mkdir()
        (target_dir / "file1.json").write_text("{}")
        (target_dir / "file2.csv").write_text("a,b")
        sub = target_dir / "subdir"
        sub.mkdir()
        (sub / "nested.txt").write_text("hello")

        handler.clear_directory(str(target_dir))

        assert target_dir.exists()
        assert list(target_dir.iterdir()) == []

    def test_clear_directory_keeps_directory(self, handler, tmp_path):
        """Test clear_directory preserves the directory itself."""
        target_dir = tmp_path / "keep_me"
        target_dir.mkdir()
        (target_dir / "file.txt").write_text("data")

        handler.clear_directory(str(target_dir))

        assert target_dir.exists()
        assert target_dir.is_dir()

    def test_clear_directory_handles_empty_directory(self, handler, tmp_path):
        """Test clear_directory is a no-op on an already empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        handler.clear_directory(str(empty_dir))

        assert empty_dir.exists()
        assert list(empty_dir.iterdir()) == []

    def test_clear_directory_handles_nonexistent_directory(self, handler, tmp_path):
        """Test clear_directory does not raise for a nonexistent directory."""
        missing_dir = tmp_path / "does_not_exist"

        handler.clear_directory(str(missing_dir))

    def test_clear_files_matching_removes_only_matching(self, handler, tmp_path):
        """Test clear_files_matching removes only files containing the substring."""
        target_dir = tmp_path / "outputs"
        target_dir.mkdir()
        (target_dir / "reviews_97067_123.json").write_text("{}")
        (target_dir / "reviews_97067_456.json").write_text("{}")
        (target_dir / "reviews_90210_789.json").write_text("{}")

        removed = handler.clear_files_matching(str(target_dir), "97067")

        remaining = sorted(f.name for f in target_dir.iterdir())
        assert remaining == ["reviews_90210_789.json"]
        assert removed == 2

    def test_clear_files_matching_preserves_directory(self, handler, tmp_path):
        """Test that the directory itself survives matching clear."""
        target_dir = tmp_path / "outputs"
        target_dir.mkdir()
        (target_dir / "data_97067.json").write_text("{}")

        handler.clear_files_matching(str(target_dir), "97067")

        assert target_dir.exists()
        assert target_dir.is_dir()

    def test_clear_files_matching_no_matches(self, handler, tmp_path):
        """Test that no files are removed when none match."""
        target_dir = tmp_path / "outputs"
        target_dir.mkdir()
        (target_dir / "data_90210.json").write_text("{}")

        removed = handler.clear_files_matching(str(target_dir), "97067")

        assert removed == 0
        assert len(list(target_dir.iterdir())) == 1

    def test_clear_files_matching_handles_nonexistent_directory(
        self, handler, tmp_path
    ):
        """Test that clear_files_matching doesn't raise for missing directory."""
        missing_dir = tmp_path / "does_not_exist"

        removed = handler.clear_files_matching(str(missing_dir), "97067")

        assert removed == 0

    def test_clear_files_matching_handles_empty_directory(self, handler, tmp_path):
        """Test that clear_files_matching is a no-op on empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        removed = handler.clear_files_matching(str(empty_dir), "97067")

        assert removed == 0

    def test_clear_files_matching_by_listing_ids(self, handler, tmp_path):
        """Test clearing files by specific listing ID substrings."""
        target_dir = tmp_path / "details"
        target_dir.mkdir()
        (target_dir / "property_details_111.json").write_text("{}")
        (target_dir / "property_details_222.json").write_text("{}")
        (target_dir / "property_details_999.json").write_text("{}")

        # Clear files matching listing IDs 111 and 222
        total = 0
        for lid in ["_111.", "_222."]:
            total += handler.clear_files_matching(str(target_dir), lid)

        remaining = sorted(f.name for f in target_dir.iterdir())
        assert remaining == ["property_details_999.json"]
        assert total == 2
