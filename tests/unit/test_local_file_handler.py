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
