import os

import pytest

from photo_backup.fs_utils import calculate_directory_size, ensure_directory, validate_path


class TestEnsureDirectory:
    """Test cases for ensure_directory function."""

    @pytest.mark.unit
    def test_ensure_directory_creates_new_directory(self, temp_dir):
        """Test creating a new directory."""
        test_dir = temp_dir / "new_directory"

        success, error = ensure_directory(str(test_dir))

        assert success is True
        assert error is None
        assert test_dir.is_dir()

    @pytest.mark.unit
    def test_ensure_directory_handles_existing_directory(self, temp_dir):
        """Test with existing directory."""
        test_dir = temp_dir / "existing_dir"
        test_dir.mkdir()

        success, error = ensure_directory(str(test_dir))

        assert success is True
        assert error is None
        assert test_dir.is_dir()

    @pytest.mark.unit
    def test_ensure_directory_creates_nested_directories(self, temp_dir):
        """Test creating nested directory structure."""
        nested_dir = temp_dir / "level1" / "level2" / "level3"

        success, error = ensure_directory(str(nested_dir))

        assert success is True
        assert error is None
        assert nested_dir.is_dir()
        assert (temp_dir / "level1").is_dir()
        assert (temp_dir / "level1" / "level2").is_dir()

    @pytest.mark.parametrize(
        "invalid_path",
        [
            "",
            None,
        ],
    )
    @pytest.mark.unit
    def test_ensure_directory_empty_path(self, invalid_path):
        """Test ensure_directory with empty or None path."""
        success, error = ensure_directory(invalid_path)

        assert success is False
        assert "Path cannot be empty" in error

    @pytest.mark.unit
    def test_ensure_directory_file_exists(self, temp_dir):
        """Test ensure_directory when a file exists at the path."""
        test_file = temp_dir / "test_file.txt"
        test_file.write_text("test content")

        success, error = ensure_directory(str(test_file))

        assert success is False
        assert "not a directory" in error

    @pytest.mark.unit
    def test_ensure_directory_permission_denied(self):
        """Test ensure_directory with permission issues."""
        # Try to create directory in a location that should fail
        invalid_path = "/root/should_fail_permission_test"

        success, error = ensure_directory(invalid_path)

        assert success is False
        assert error is not None
        assert "Permission denied" in error or "OS error" in error

    @pytest.mark.unit
    def test_ensure_directory_returns_absolute_path(self, temp_dir):
        """Test that ensure_directory works with relative paths."""
        # Change to temp directory and use relative path
        original_cwd = os.getcwd()
        try:
            os.chdir(str(temp_dir))
            relative_path = "relative_test_dir"

            success, error = ensure_directory(relative_path)

            assert success is True
            assert error is None
            assert (temp_dir / relative_path).is_dir()
        finally:
            os.chdir(original_cwd)


class TestValidatePath:
    """Test cases for validate_path function."""

    @pytest.mark.unit
    def test_validate_path_valid_file(self, tmp_path):
        test_file = tmp_path / "file.txt"
        test_file.write_text("test")
        valid, error = validate_path(str(test_file))
        assert valid is True
        assert error is None

    @pytest.mark.unit
    def test_validate_path_valid_directory(self, tmp_path):
        valid, error = validate_path(str(tmp_path))
        assert valid is True
        assert error is None

    @pytest.mark.unit
    def test_validate_path_nonexistent(self, tmp_path):
        non_existent = tmp_path / "does_not_exist.txt"
        valid, error = validate_path(str(non_existent))
        assert valid is False
        assert "does not exist" in error

    @pytest.mark.unit
    def test_validate_path_empty_and_none(self):
        valid, error = validate_path("")
        assert valid is False
        assert "non-empty string" in error
        valid, error = validate_path(None)
        assert valid is False
        assert "non-empty string" in error

    @pytest.mark.unit
    def test_validate_path_permission_denied(self, tmp_path):
        # Create a directory and remove read permissions
        test_dir = tmp_path / "no_access_dir"
        test_dir.mkdir()
        test_file = test_dir / "file.txt"
        test_file.write_text("test")
        test_dir.chmod(0o000)
        try:
            valid, error = validate_path(str(test_dir))
            assert valid is False
            assert "not accessible" in error or "Permission denied" in error
        finally:
            # Restore permissions so pytest can clean up
            test_dir.chmod(0o700)


class TestCalculateDirectorySize:
    """Test cases for calculate_directory_size function."""

    @pytest.mark.unit
    def test_calculate_directory_size_basic(self, tmp_path):
        # Create files
        f1 = tmp_path / "file1.txt"
        f1.write_bytes(b"a" * 100)
        f2 = tmp_path / "file2.txt"
        f2.write_bytes(b"b" * 200)
        total, count = calculate_directory_size(str(tmp_path))
        assert total == 300
        assert count == 2

    @pytest.mark.unit
    def test_calculate_directory_size_nested(self, tmp_path):
        d1 = tmp_path / "dir1"
        d1.mkdir()
        d2 = d1 / "dir2"
        d2.mkdir()
        (d1 / "a.txt").write_bytes(b"x" * 50)
        (d2 / "b.txt").write_bytes(b"y" * 150)
        total, count = calculate_directory_size(str(tmp_path))
        assert total == 200
        assert count == 2

    @pytest.mark.unit
    def test_calculate_directory_size_empty(self, tmp_path):
        total, count = calculate_directory_size(str(tmp_path))
        assert total == 0
        assert count == 0

    @pytest.mark.unit
    def test_calculate_directory_size_permission_error(self, tmp_path):
        d1 = tmp_path / "dir1"
        d1.mkdir()
        f1 = d1 / "file.txt"
        f1.write_bytes(b"z" * 123)
        # Remove read permission from dir1
        d1.chmod(0o000)
        try:
            total, count = calculate_directory_size(str(tmp_path))
            # Should skip dir1 and not raise
            assert total == 0
            assert count == 0
        finally:
            d1.chmod(0o700)

    @pytest.mark.unit
    def test_calculate_directory_size_symlink(self, tmp_path):
        f1 = tmp_path / "file.txt"
        f1.write_bytes(b"abc" * 10)
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(f1)
        total, count = calculate_directory_size(str(tmp_path))
        # Should count only the real file, not the symlink
        assert total == 30
        assert count == 1
