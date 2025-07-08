"""
Functional tests for utils module 

This test verifies that the utility functions work correctly through direct testing.
"""

import os
import tempfile
import pytest


def test_format_bytes_function():
    """Test format_bytes function with various inputs."""
    from photo_backup.utils import format_bytes
    
    # Test standard cases
    assert format_bytes(0) == "0 B"
    assert format_bytes(512) == "512 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1536) == "1.50 KB"
    assert format_bytes(1048576) == "1.00 MB"
    assert format_bytes(1073741824) == "1.00 GB"
    assert format_bytes(1099511627776) == "1.00 TB"
    
    # Test edge cases
    assert format_bytes(-1) == "0 B"
    assert format_bytes("invalid") == "0 B"
    
    # Test precision formatting
    assert format_bytes(1500) == "1.46 KB"  # < 10, show 2 decimals
    assert format_bytes(15000) == "14.6 KB"  # >= 10, show 1 decimal
    assert format_bytes(150000) == "146 KB"  # >= 100, show 0 decimals


def test_ensure_directory_function():
    """Test ensure_directory function with various scenarios."""
    from photo_backup.utils import ensure_directory
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = os.path.join(temp_dir, "test_subdir")
        
        # Test creating new directory
        success, error = ensure_directory(test_dir)
        assert success is True, f"Failed to create directory: {error}"
        assert error is None
        assert os.path.isdir(test_dir)
        
        # Test with existing directory
        success, error = ensure_directory(test_dir)
        assert success is True, f"Failed with existing directory: {error}"
        assert error is None
        
        # Test creating nested directories
        nested_dir = os.path.join(test_dir, "nested", "deep")
        success, error = ensure_directory(nested_dir)
        assert success is True, f"Failed to create nested directory: {error}"
        assert error is None
        assert os.path.isdir(nested_dir)


def test_ensure_directory_edge_cases():
    """Test ensure_directory function with edge cases."""
    from photo_backup.utils import ensure_directory
    
    # Test with empty path
    success, error = ensure_directory("")
    assert success is False
    assert "Path cannot be empty" in error
    
    # Test with None path
    success, error = ensure_directory(None)
    assert success is False
    assert "Path cannot be empty" in error
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test with file instead of directory
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        success, error = ensure_directory(test_file)
        assert success is False
        assert "not a directory" in error


def test_ensure_directory_permissions():
    """Test ensure_directory function with permission issues."""
    from photo_backup.utils import ensure_directory
    
    # Test with invalid path that should fail (like root with no permissions)
    invalid_path = "/root/should_fail_permission_test"
    
    success, error = ensure_directory(invalid_path)
    assert success is False
    assert error is not None
    assert "Permission denied" in error or "OS error" in error


def test_format_bytes_comprehensive():
    """Comprehensive test of format_bytes with edge cases."""
    from photo_backup.utils import format_bytes
    
    # Test all units
    test_cases = [
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
    ]
    
    for bytes_value, expected in test_cases:
        result = format_bytes(bytes_value)
        assert result == expected, f"format_bytes({bytes_value}) = {result}, expected {expected}"


def test_utils_integration():
    """Integration test using multiple utility functions together."""
    from photo_backup.utils import format_bytes, ensure_directory
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test directory structure
        test_dirs = [
            os.path.join(temp_dir, "photos", "2024"),
            os.path.join(temp_dir, "photos", "2023"),
            os.path.join(temp_dir, "backup", "state"),
        ]
        
        # Ensure all directories exist
        for test_dir in test_dirs:
            success, error = ensure_directory(test_dir)
            assert success is True, f"Failed to create {test_dir}: {error}"
            assert os.path.isdir(test_dir)
        
        # Create some test files and calculate sizes
        test_files = []
        total_size = 0
        
        for i, test_dir in enumerate(test_dirs):
            file_path = os.path.join(test_dir, f"test_file_{i}.txt")
            content = "x" * (1024 * (i + 1))  # 1KB, 2KB, 3KB
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            file_size = os.path.getsize(file_path)
            total_size += file_size
            test_files.append((file_path, file_size))
        
        # Test formatting the total size
        formatted_size = format_bytes(total_size)
        assert "KB" in formatted_size  # Should be in KB range
        
        # Verify all files exist and have correct sizes
        for file_path, expected_size in test_files:
            assert os.path.isfile(file_path)
            actual_size = os.path.getsize(file_path)
            assert actual_size == expected_size