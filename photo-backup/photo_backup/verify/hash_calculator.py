"""
Hash calculator for file integrity verification.

This module provides functionality to calculate MD5 hashes for files,
with support for large files and progress reporting.

Task 94: Hash Calculation
"""

import hashlib
import logging
from collections.abc import Callable

from pathlib import Path

from .models import FileHash


class HashCalculator:
    """Calculates file hashes with support for large files and progress reporting."""

    # Default chunk size for reading files (64KB)
    DEFAULT_CHUNK_SIZE = 64 * 1024

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """Initialize the hash calculator.

        Args:
            chunk_size: Size of chunks to read at a time (in bytes)
            progress_callback: Optional callback(bytes_read, total_bytes) for progress
        """
        self.chunk_size = chunk_size
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)

    def calculate_md5(self, file_path: str | Path) -> str:
        """Calculate MD5 hash of a file.

        Uses chunked reading to support large files without loading
        entire file into memory.

        Args:
            file_path: Path to the file to hash

        Returns:
            MD5 hash as hexadecimal string

        Raises:
            FileNotFoundError: If file does not exist
            PermissionError: If file cannot be read
            OSError: For other file system errors
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        total_size = file_path.stat().st_size
        bytes_read = 0

        md5_hash = hashlib.md5()

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break

                md5_hash.update(chunk)
                bytes_read += len(chunk)

                # Report progress if callback provided
                if self.progress_callback:
                    self.progress_callback(bytes_read, total_size)

        return md5_hash.hexdigest()

    def calculate_file_hash(self, file_path: str | Path) -> FileHash:
        """Calculate hash and gather file information.

        Args:
            file_path: Path to the file

        Returns:
            FileHash object with file information and hash
        """
        file_path = Path(file_path)
        stat_info = file_path.stat()

        return FileHash(
            path=str(file_path),
            size=stat_info.st_size,
            hash_md5=self.calculate_md5(file_path),
            hash_type="md5",
            modified_time=str(stat_info.st_mtime),
        )

    def calculate_directory_hashes(
        self,
        directory: str | Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[FileHash]:
        """Calculate hashes for all files in a directory.

        Args:
            directory: Directory to scan
            exclude_patterns: Optional list of glob patterns to exclude

        Returns:
            List of FileHash objects for all files
        """
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        exclude_patterns = exclude_patterns or [".*", "Thumbs.db", ".DS_Store"]
        file_hashes = []

        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue

            # Check exclusions
            should_exclude = False
            for pattern in exclude_patterns:
                if file_path.match(pattern):
                    should_exclude = True
                    break

            if should_exclude:
                self.logger.debug(f"Excluding file: {file_path}")
                continue

            try:
                file_hash = self.calculate_file_hash(file_path)
                # Store relative path from directory
                file_hash.path = str(file_path.relative_to(directory))
                file_hashes.append(file_hash)
            except Exception as e:
                self.logger.warning(f"Failed to hash {file_path}: {e}")

        return file_hashes
