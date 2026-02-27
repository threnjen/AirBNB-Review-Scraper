import os
import shutil


class LocalFileHandler:
    """Minimal file handler — only provides directory operations used by the pipeline."""

    def clear_directory(self, directory: str) -> None:
        """Remove all files and subdirectories inside *directory*, keeping it."""
        if not os.path.isdir(directory):
            return
        for entry in os.listdir(directory):
            entry_path = os.path.join(directory, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path)
            else:
                os.remove(entry_path)

    def clear_files_matching(self, directory: str, substring: str) -> int:
        """Remove files whose names contain *substring*, keeping everything else.

        Args:
            directory: Path to the directory to scan.
            substring: Only files whose name contains this string are removed.

        Returns:
            Number of files removed.
        """
        if not os.path.isdir(directory):
            return 0
        removed = 0
        for entry in os.listdir(directory):
            if substring in entry:
                entry_path = os.path.join(directory, entry)
                if os.path.isdir(entry_path):
                    shutil.rmtree(entry_path)
                else:
                    os.remove(entry_path)
                removed += 1
        return removed
