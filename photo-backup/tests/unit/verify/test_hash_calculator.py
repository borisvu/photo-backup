"""
Unit tests for the HashCalculator class (Task 94).

Tests hash calculation with support for large files and progress reporting.
"""

import hashlib

import pytest
from pathlib import Path


class TestHashCalculatorInstantiation:
    """Test HashCalculator instantiation."""

    def test_hash_calculator_can_be_instantiated(self):
        """Test that HashCalculator can be instantiated."""
        from photo_backup.verify import HashCalculator

        calculator = HashCalculator()

        assert calculator is not None
        assert calculator.chunk_size == HashCalculator.DEFAULT_CHUNK_SIZE

    def test_hash_calculator_custom_chunk_size(self):
        """Test that HashCalculator accepts custom chunk size."""
        from photo_backup.verify import HashCalculator

        calculator = HashCalculator(chunk_size=1024)

        assert calculator.chunk_size == 1024

    def test_hash_calculator_with_progress_callback(self):
        """Test that HashCalculator accepts progress callback."""
        from photo_backup.verify import HashCalculator

        progress_calls = []

        def callback(bytes_read: int, total: int) -> None:
            progress_calls.append((bytes_read, total))

        calculator = HashCalculator(progress_callback=callback)

        assert calculator.progress_callback is callback


class TestHashCalculatorMD5:
    """Test HashCalculator MD5 calculation."""

    def test_calculate_md5_simple_file(self, tmp_path: Path):
        """Test MD5 calculation for a simple file."""
        from photo_backup.verify import HashCalculator

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)

        # Calculate expected MD5
        expected_md5 = hashlib.md5(test_content).hexdigest()

        # Calculate with HashCalculator
        calculator = HashCalculator()
        result_md5 = calculator.calculate_md5(test_file)

        assert result_md5 == expected_md5

    def test_calculate_md5_empty_file(self, tmp_path: Path):
        """Test MD5 calculation for an empty file."""
        from photo_backup.verify import HashCalculator

        # Create an empty file
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        # Calculate expected MD5 (empty string)
        expected_md5 = hashlib.md5(b"").hexdigest()

        calculator = HashCalculator()
        result_md5 = calculator.calculate_md5(test_file)

        assert result_md5 == expected_md5

    def test_calculate_md5_large_file(self, tmp_path: Path):
        """Test MD5 calculation for a file larger than chunk size."""
        from photo_backup.verify import HashCalculator

        # Create a file larger than default chunk size (64KB)
        test_file = tmp_path / "large.bin"
        # Create 100KB of data
        test_content = b"A" * (100 * 1024)
        test_file.write_bytes(test_content)

        # Calculate expected MD5
        expected_md5 = hashlib.md5(test_content).hexdigest()

        # Use small chunk size to ensure multiple reads
        calculator = HashCalculator(chunk_size=1024)
        result_md5 = calculator.calculate_md5(test_file)

        assert result_md5 == expected_md5

    def test_calculate_md5_binary_content(self, tmp_path: Path):
        """Test MD5 calculation for binary content."""
        from photo_backup.verify import HashCalculator

        # Create binary content (simulating image data)
        test_file = tmp_path / "image.bin"
        # Random-ish binary data
        test_content = bytes(range(256)) * 100
        test_file.write_bytes(test_content)

        # Calculate expected MD5
        expected_md5 = hashlib.md5(test_content).hexdigest()

        calculator = HashCalculator()
        result_md5 = calculator.calculate_md5(test_file)

        assert result_md5 == expected_md5

    def test_calculate_md5_file_not_found(self, tmp_path: Path):
        """Test MD5 calculation raises error for missing file."""
        from photo_backup.verify import HashCalculator

        calculator = HashCalculator()
        non_existent = tmp_path / "does_not_exist.txt"

        with pytest.raises(FileNotFoundError):
            calculator.calculate_md5(non_existent)

    def test_calculate_md5_directory_raises_error(self, tmp_path: Path):
        """Test MD5 calculation raises error for directory."""
        from photo_backup.verify import HashCalculator

        calculator = HashCalculator()

        with pytest.raises(ValueError, match="Not a file"):
            calculator.calculate_md5(tmp_path)

    def test_calculate_md5_accepts_string_path(self, tmp_path: Path):
        """Test MD5 calculation accepts string path."""
        from photo_backup.verify import HashCalculator

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content")

        calculator = HashCalculator()
        # Pass as string instead of Path
        result_md5 = calculator.calculate_md5(str(test_file))

        assert len(result_md5) == 32  # MD5 is 32 hex chars


class TestHashCalculatorProgress:
    """Test HashCalculator progress reporting."""

    def test_progress_callback_is_called(self, tmp_path: Path):
        """Test that progress callback is called during hashing."""
        from photo_backup.verify import HashCalculator

        # Create a test file larger than chunk size
        test_file = tmp_path / "progress_test.bin"
        test_file.write_bytes(b"X" * (10 * 1024))  # 10KB

        progress_calls: list[tuple[int, int]] = []

        def callback(bytes_read: int, total: int) -> None:
            progress_calls.append((bytes_read, total))

        # Use small chunk to get multiple progress calls
        calculator = HashCalculator(chunk_size=1024, progress_callback=callback)
        calculator.calculate_md5(test_file)

        # Should have multiple progress calls
        assert len(progress_calls) > 1

        # Total should be correct
        assert progress_calls[-1][1] == 10 * 1024

        # Final bytes_read should equal total
        assert progress_calls[-1][0] == progress_calls[-1][1]

    def test_progress_callback_reports_increasing_bytes(self, tmp_path: Path):
        """Test that progress callback reports monotonically increasing bytes."""
        from photo_backup.verify import HashCalculator

        test_file = tmp_path / "monotonic_test.bin"
        test_file.write_bytes(b"Y" * (5 * 1024))

        progress_values: list[int] = []

        def callback(bytes_read: int, _total: int) -> None:
            progress_values.append(bytes_read)

        calculator = HashCalculator(chunk_size=512, progress_callback=callback)
        calculator.calculate_md5(test_file)

        # Verify monotonically increasing
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1]


class TestHashCalculatorFileHash:
    """Test HashCalculator.calculate_file_hash method."""

    def test_calculate_file_hash_returns_filehash(self, tmp_path: Path):
        """Test that calculate_file_hash returns FileHash object."""
        from photo_backup.verify import FileHash, HashCalculator

        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"file hash test")

        calculator = HashCalculator()
        result = calculator.calculate_file_hash(test_file)

        assert isinstance(result, FileHash)
        assert result.path == str(test_file)
        assert result.size == 14  # len("file hash test")
        assert result.hash_md5 is not None
        assert result.hash_type == "md5"

    def test_calculate_file_hash_includes_size(self, tmp_path: Path):
        """Test that calculate_file_hash includes correct file size."""
        from photo_backup.verify import HashCalculator

        test_file = tmp_path / "sized.bin"
        test_file.write_bytes(b"A" * 1234)

        calculator = HashCalculator()
        result = calculator.calculate_file_hash(test_file)

        assert result.size == 1234


class TestHashCalculatorDirectoryHashes:
    """Test HashCalculator.calculate_directory_hashes method."""

    def test_calculate_directory_hashes_empty_dir(self, tmp_path: Path):
        """Test hashing an empty directory."""
        from photo_backup.verify import HashCalculator

        calculator = HashCalculator()
        result = calculator.calculate_directory_hashes(tmp_path)

        assert result == []

    def test_calculate_directory_hashes_single_file(self, tmp_path: Path):
        """Test hashing a directory with one file."""
        from photo_backup.verify import HashCalculator

        test_file = tmp_path / "single.txt"
        test_file.write_bytes(b"single file content")

        calculator = HashCalculator()
        result = calculator.calculate_directory_hashes(tmp_path)

        assert len(result) == 1
        assert result[0].path == "single.txt"

    def test_calculate_directory_hashes_multiple_files(self, tmp_path: Path):
        """Test hashing a directory with multiple files."""
        from photo_backup.verify import HashCalculator

        (tmp_path / "file1.txt").write_bytes(b"content 1")
        (tmp_path / "file2.txt").write_bytes(b"content 2")
        (tmp_path / "file3.txt").write_bytes(b"content 3")

        calculator = HashCalculator()
        result = calculator.calculate_directory_hashes(tmp_path)

        assert len(result) == 3
        paths = {fh.path for fh in result}
        assert "file1.txt" in paths
        assert "file2.txt" in paths
        assert "file3.txt" in paths

    def test_calculate_directory_hashes_nested_directories(self, tmp_path: Path):
        """Test hashing a directory with nested subdirectories."""
        from photo_backup.verify import HashCalculator

        # Create nested structure
        (tmp_path / "2024" / "01").mkdir(parents=True)
        (tmp_path / "2024" / "02").mkdir(parents=True)

        (tmp_path / "2024" / "01" / "photo1.jpg").write_bytes(b"photo1")
        (tmp_path / "2024" / "02" / "photo2.jpg").write_bytes(b"photo2")

        calculator = HashCalculator()
        result = calculator.calculate_directory_hashes(tmp_path)

        assert len(result) == 2
        paths = {fh.path for fh in result}
        assert "2024/01/photo1.jpg" in paths
        assert "2024/02/photo2.jpg" in paths

    def test_calculate_directory_hashes_excludes_hidden_files(self, tmp_path: Path):
        """Test that hidden files are excluded by default."""
        from photo_backup.verify import HashCalculator

        (tmp_path / "visible.txt").write_bytes(b"visible")
        (tmp_path / ".hidden").write_bytes(b"hidden")
        (tmp_path / ".DS_Store").write_bytes(b"mac junk")

        calculator = HashCalculator()
        result = calculator.calculate_directory_hashes(tmp_path)

        assert len(result) == 1
        assert result[0].path == "visible.txt"

    def test_calculate_directory_hashes_excludes_thumbs_db(self, tmp_path: Path):
        """Test that Thumbs.db is excluded."""
        from photo_backup.verify import HashCalculator

        (tmp_path / "photo.jpg").write_bytes(b"photo")
        (tmp_path / "Thumbs.db").write_bytes(b"windows junk")

        calculator = HashCalculator()
        result = calculator.calculate_directory_hashes(tmp_path)

        assert len(result) == 1
        assert result[0].path == "photo.jpg"

    def test_calculate_directory_hashes_custom_exclusions(self, tmp_path: Path):
        """Test custom exclusion patterns."""
        from photo_backup.verify import HashCalculator

        (tmp_path / "keep.txt").write_bytes(b"keep")
        (tmp_path / "exclude.log").write_bytes(b"exclude")
        (tmp_path / "also_exclude.tmp").write_bytes(b"also exclude")

        calculator = HashCalculator()
        result = calculator.calculate_directory_hashes(
            tmp_path,
            exclude_patterns=["*.log", "*.tmp"],
        )

        assert len(result) == 1
        assert result[0].path == "keep.txt"

    def test_calculate_directory_hashes_nonexistent_dir(self, tmp_path: Path):
        """Test error when directory doesn't exist."""
        from photo_backup.verify import HashCalculator

        calculator = HashCalculator()
        non_existent = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError):
            calculator.calculate_directory_hashes(non_existent)


class TestHashCalculatorWithTestPhotos:
    """Test HashCalculator with realistic test photo fixtures."""

    def test_hashes_match_for_identical_content(self, tmp_path: Path):
        """Test that identical files produce identical hashes."""
        from photo_backup.verify import HashCalculator

        content = b"JPEG HEADER" + b"\x00" * 1000 + b"image data"

        file1 = tmp_path / "photo1.jpg"
        file2 = tmp_path / "photo2.jpg"
        file1.write_bytes(content)
        file2.write_bytes(content)

        calculator = HashCalculator()
        hash1 = calculator.calculate_md5(file1)
        hash2 = calculator.calculate_md5(file2)

        assert hash1 == hash2

    def test_hashes_differ_for_different_content(self, tmp_path: Path):
        """Test that different files produce different hashes."""
        from photo_backup.verify import HashCalculator

        file1 = tmp_path / "photo1.jpg"
        file2 = tmp_path / "photo2.jpg"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")

        calculator = HashCalculator()
        hash1 = calculator.calculate_md5(file1)
        hash2 = calculator.calculate_md5(file2)

        assert hash1 != hash2

    def test_hash_consistency_across_calls(self, tmp_path: Path):
        """Test that hashing the same file multiple times gives consistent results."""
        from photo_backup.verify import HashCalculator

        test_file = tmp_path / "consistent.bin"
        test_file.write_bytes(b"consistent content" * 100)

        calculator = HashCalculator()

        # Calculate hash multiple times
        hashes = [calculator.calculate_md5(test_file) for _ in range(5)]

        # All hashes should be identical
        assert all(h == hashes[0] for h in hashes)
