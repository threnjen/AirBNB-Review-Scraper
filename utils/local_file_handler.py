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
