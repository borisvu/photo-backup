"""
Unit tests for utils module.

These tests focus on individual utility functions in isolation.
"""

import os
import pytest
from photo_backup.utils import format_bytes, ensure_directory, validate_path, get_state_directories, save_json_state, load_json_state, acquire_lock, release_lock


class TestFormatBytes:
    """Test cases for format_bytes function."""
    
    @pytest.mark.parametrize("bytes_value,expected", [
        (0, "0 B"),
        (1, "1 B"),
        (512, "512 B"),
        (1023, "1023 B"),
        (1024, "1.00 KB"),
        (1536, "1.50 KB"),
        (10240, "10.0 KB"),
        (102400, "100 KB"),
        (1048576, "1.00 MB"),
        (1073741824, "1.00 GB"),
        (1099511627776, "1.00 TB"),
        (1125899906842624, "1.00 PB"),
    ])
    @pytest.mark.unit
    def test_format_bytes_standard_cases(self, bytes_value, expected):
        """Test format_bytes with standard byte values."""
        result = format_bytes(bytes_value)
        assert result == expected, f"format_bytes({bytes_value}) = {result}, expected {expected}"
    
    @pytest.mark.parametrize("invalid_input,expected", [
        (-1, "0 B"),
        ("invalid", "0 B"),
        (None, "0 B"),
        ([], "0 B"),
        ({}, "0 B"),
    ])
    @pytest.mark.unit
    def test_format_bytes_edge_cases(self, invalid_input, expected):
        """Test format_bytes with invalid inputs."""
        result = format_bytes(invalid_input)
        assert result == expected
    
    @pytest.mark.parametrize("bytes_value,expected_precision", [
        (1500, 2),  # 1.46 KB - < 10, show 2 decimals
        (15000, 1),  # 14.6 KB - >= 10, show 1 decimal
        (150000, 0),  # 146 KB - >= 100, show 0 decimals
    ])
    @pytest.mark.unit
    def test_format_bytes_precision(self, bytes_value, expected_precision):
        """Test format_bytes precision formatting."""
        result = format_bytes(bytes_value)
        if expected_precision == 0:
            assert "." not in result.split()[0]
        else:
            decimal_part = result.split()[0].split(".")[1]
            assert len(decimal_part) == expected_precision


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
    
    @pytest.mark.parametrize("invalid_path", [
        "",
        None,
    ])
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
        assert ("Permission denied" in error or "OS error" in error)
    
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
    def test_validate_path_permission_denied(self, tmp_path, monkeypatch):
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


class TestGetStateDirectories:
    """Test cases for get_state_directories function."""

    @pytest.mark.unit
    def test_get_state_directories_test_mode(self, tmp_path, monkeypatch):
        # Patch /tmp to a temp dir to avoid polluting real /tmp
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        # Patch base dir to use a subdir of tmp_path
        monkeypatch.setattr("photo_backup.utils.os.path.expanduser", lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p)
        # Test test_mode
        dirs = get_state_directories(test_mode=True)
        assert dirs["base"].startswith("/tmp/photo-backup-test")
        for sub in ["state", "config", "temp"]:
            assert sub in dirs
            assert os.path.isdir(dirs[sub])
            # Check permissions (should be 0o755)
            mode = os.stat(dirs[sub]).st_mode & 0o777
            assert mode == 0o755

    @pytest.mark.unit
    def test_get_state_directories_normal_mode(self, tmp_path, monkeypatch):
        # Patch expanduser to use tmp_path for home
        monkeypatch.setattr("photo_backup.utils.os.path.expanduser", lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p)
        dirs = get_state_directories(test_mode=False)
        assert "base" in dirs and "state" in dirs and "config" in dirs and "temp" in dirs
        for sub in ["base", "state", "config", "temp"]:
            assert os.path.isdir(dirs[sub])
            mode = os.stat(dirs[sub]).st_mode & 0o777
            assert mode == 0o755

    @pytest.mark.unit
    def test_get_state_directories_error(self, monkeypatch):
        # Simulate ensure_directory failure
        monkeypatch.setattr("photo_backup.utils.ensure_directory", lambda path: (False, "fail"))
        with pytest.raises(RuntimeError):
            get_state_directories(test_mode=True)


class TestJsonStateHelpers:
    """Test cases for save_json_state and load_json_state functions."""

    @pytest.mark.unit
    def test_save_and_load_json_state(self, tmp_path, monkeypatch):
        # Patch expanduser to use tmp_path for home
        monkeypatch.setattr("photo_backup.utils.os.path.expanduser", lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p)
        data = {"foo": 123, "bar": [1, 2, 3]}
        filename = "test_state.json"
        # Save
        success, error = save_json_state(data, filename, test_mode=False)
        assert success is True
        assert error is None
        # Load
        loaded, error = load_json_state(filename, test_mode=False)
        assert error is None
        assert loaded == data

    @pytest.mark.unit
    def test_load_json_state_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr("photo_backup.utils.os.path.expanduser", lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p)
        loaded, error = load_json_state("does_not_exist.json", test_mode=False)
        assert loaded is None
        assert "does not exist" in error

    @pytest.mark.unit
    def test_save_json_state_error(self, monkeypatch):
        # Simulate get_state_directories failure
        monkeypatch.setattr("photo_backup.utils.get_state_directories", lambda test_mode=False: (_ for _ in ()).throw(RuntimeError("fail")))
        success, error = save_json_state({}, "file.json", test_mode=False)
        assert success is False
        assert "Error saving JSON state" in error

    @pytest.mark.unit
    def test_load_json_state_error(self, monkeypatch):
        # Simulate get_state_directories failure
        monkeypatch.setattr("photo_backup.utils.get_state_directories", lambda test_mode=False: (_ for _ in ()).throw(RuntimeError("fail")))
        loaded, error = load_json_state("file.json", test_mode=False)
        assert loaded is None
        assert "Error loading JSON state" in error


class TestProcessLock:
    """Test cases for acquire_lock and release_lock functions."""

    @pytest.mark.unit
    def test_acquire_and_release_lock(self, tmp_path, monkeypatch):
        # Patch expanduser to use tmp_path for home
        monkeypatch.setattr("photo_backup.utils.os.path.expanduser", lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p)
        lock_name = "test.lock"
        # Acquire lock
        success, error = acquire_lock(lock_name=lock_name, test_mode=False)
        assert success is True
        assert error is None
        # Try to acquire again (should fail)
        success, error = acquire_lock(lock_name=lock_name, test_mode=False)
        assert success is False
        assert "Lock already acquired" in error
        # Release lock
        success, error = release_lock(lock_name=lock_name, test_mode=False)
        assert success is True
        assert error is None
        # Release again (should fail)
        success, error = release_lock(lock_name=lock_name, test_mode=False)
        assert success is False
        assert "does not exist" in error

    @pytest.mark.unit
    def test_release_lock_wrong_pid(self, tmp_path, monkeypatch):
        monkeypatch.setattr("photo_backup.utils.os.path.expanduser", lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p)
        lock_name = "test2.lock"
        dirs = get_state_directories(test_mode=False)
        temp_dir = dirs["temp"]
        lock_path = os.path.join(temp_dir, lock_name)
        # Write a fake PID
        with open(lock_path, "w") as f:
            f.write("999999")
        # Try to release (should fail)
        success, error = release_lock(lock_name=lock_name, test_mode=False)
        assert success is False
        assert "owned by PID" in error

    @pytest.mark.unit
    def test_acquire_lock_stale_pid(self, tmp_path, monkeypatch):
        monkeypatch.setattr("photo_backup.utils.os.path.expanduser", lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p)
        lock_name = "test3.lock"
        dirs = get_state_directories(test_mode=False)
        temp_dir = dirs["temp"]
        lock_path = os.path.join(temp_dir, lock_name)
        # Write a stale PID (should not exist)
        with open(lock_path, "w") as f:
            f.write("999999")
        # Should acquire lock (stale PID)
        success, error = acquire_lock(lock_name=lock_name, test_mode=False)
        assert success is True
        assert error is None
        # Clean up
        release_lock(lock_name=lock_name, test_mode=False)


class TestUtilsIntegration:
    """Integration tests using multiple utility functions together."""
    
    @pytest.mark.unit
    def test_utils_workflow(self, temp_dir):
        """Test a typical workflow using multiple utility functions."""
        # Create directory structure
        dirs_to_create = [
            temp_dir / "photos" / "2024",
            temp_dir / "photos" / "2023",
            temp_dir / "backup" / "state",
        ]
        
        # Ensure all directories exist
        for test_dir in dirs_to_create:
            success, error = ensure_directory(str(test_dir))
            assert success is True, f"Failed to create {test_dir}: {error}"
            assert test_dir.is_dir()
        
        # Create test files and calculate sizes
        total_size = 0
        test_files = []
        
        for i, test_dir in enumerate(dirs_to_create):
            file_path = test_dir / f"test_file_{i}.txt"
            content = "x" * (1024 * (i + 1))  # 1KB, 2KB, 3KB
            
            file_path.write_text(content)
            file_size = file_path.stat().st_size
            total_size += file_size
            test_files.append((file_path, file_size))
        
        # Test formatting the total size
        formatted_size = format_bytes(total_size)
        assert "KB" in formatted_size  # Should be in KB range
        
        # Verify all files exist and have correct sizes
        for file_path, expected_size in test_files:
            assert file_path.is_file()
            actual_size = file_path.stat().st_size
            assert actual_size == expected_size