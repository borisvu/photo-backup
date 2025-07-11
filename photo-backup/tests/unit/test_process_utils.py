import os
import pytest
from photo_backup.process_utils import run_command, retry
from photo_backup.format_utils import format_bytes
from photo_backup.fs_utils import ensure_directory

class TestRunCommand:
    """Test cases for run_command function."""

    @pytest.mark.unit
    def test_run_command_success(self):
        result = run_command(["echo", "hello world"])
        assert result["returncode"] == 0
        assert "hello world" in result["stdout"]
        assert result["stderr"] == ""
        assert result["timeout"] is False

    @pytest.mark.unit
    def test_run_command_error(self):
        result = run_command(["ls", "/nonexistentpath"])
        assert result["returncode"] != 0
        assert result["stdout"] == ""
        assert result["stderr"] != ""
        assert result["timeout"] is False

    @pytest.mark.unit
    def test_run_command_timeout(self):
        result = run_command(["sleep", "2"], timeout=0.5)
        assert result["timeout"] is True
        assert result["returncode"] is None

    @pytest.mark.unit
    def test_run_command_shell_true(self):
        result = run_command("echo shell test", shell=True)
        assert result["returncode"] == 0
        assert "shell test" in result["stdout"]
        assert result["timeout"] is False

class TestRetryDecorator:
    """Test cases for the retry decorator."""

    @pytest.mark.unit
    def test_retry_success_first_try(self, monkeypatch):
        calls = []
        @retry(max_attempts=3, backoff=0)
        def func():
            calls.append(1)
            return 42
        assert func() == 42
        assert len(calls) == 1

    @pytest.mark.unit
    def test_retry_success_after_retries(self, monkeypatch):
        calls = []
        @retry(max_attempts=3, backoff=0)
        def func():
            if len(calls) < 2:
                calls.append('fail')
                raise ValueError("fail")
            calls.append('ok')
            return "done"
        assert func() == "done"
        assert calls == ['fail', 'fail', 'ok']

    @pytest.mark.unit
    def test_retry_exceeds_max_attempts(self, monkeypatch):
        calls = []
        @retry(max_attempts=2, backoff=0)
        def func():
            calls.append(1)
            raise RuntimeError("fail")
        with pytest.raises(RuntimeError):
            func()
        assert len(calls) == 2

    @pytest.mark.unit
    def test_retry_backoff(self, monkeypatch):
        sleep_calls = []
        monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
        calls = []
        @retry(max_attempts=3, backoff=0.1)
        def func():
            calls.append(1)
            raise Exception("fail")
        with pytest.raises(Exception):
            func()
        assert sleep_calls == [0.1, 0.1]

    @pytest.mark.unit
    def test_retry_custom_exception(self):
        class MyError(Exception): pass
        calls = []
        @retry(max_attempts=2, backoff=0, exceptions=(MyError,))
        def func():
            calls.append(1)
            raise MyError("fail")
        with pytest.raises(MyError):
            func()
        assert len(calls) == 2

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