"""
Unit tests for utils module.

These tests focus on individual utility functions in isolation.
"""

import os
import pytest
from photo_backup.utils import format_bytes, ensure_directory


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