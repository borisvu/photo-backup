"""
Functional tests for install script.

These tests verify that the install script correctly checks prerequisites
and creates the necessary directory structure.
"""

import os
import plistlib
import shutil
import subprocess

import pytest
from pathlib import Path


class TestInstallScript:
    """Functional tests for install.py script."""

    @pytest.mark.functional
    def test_install_script_test_mode_creates_directories(self):
        """Test that install script creates test structure in test mode."""
        from photo_backup.consts import TEST_MODE_BASE_DIR

        test_base_dir = Path(TEST_MODE_BASE_DIR)

        # Clean up if it exists
        if test_base_dir.exists():
            shutil.rmtree(test_base_dir)

        # Run install script in test mode
        install_script = Path(__file__).parent.parent.parent / "install.py"
        result = subprocess.run(
            ["python3", str(install_script), "--test"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        # Check that script succeeded
        assert result.returncode == 0, f"Install script failed: {result.stderr}"

        # Verify directories were created
        assert test_base_dir.exists(), "Base directory should exist"
        assert (test_base_dir / "state").exists(), "State directory should exist"
        assert (test_base_dir / "config").exists(), "Config directory should exist"
        assert (test_base_dir / "temp").exists(), "Temp directory should exist"

        # Verify output mentions test mode
        assert "TEST MODE" in result.stdout, "Output should mention test mode"
        assert "test structure" in result.stdout.lower() or "test mode" in result.stdout.lower()

        # Clean up
        if test_base_dir.exists():
            shutil.rmtree(test_base_dir)

    @pytest.mark.functional
    def test_install_script_checks_prerequisites(self):
        """Test that install script checks prerequisites."""
        install_script = Path(__file__).parent.parent.parent / "install.py"
        result = subprocess.run(
            ["python3", str(install_script), "--test"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        # Check that script checks prerequisites
        assert "Checking prerequisites" in result.stdout or "Checking Python" in result.stdout
        assert "Python" in result.stdout, "Should check Python version"
        assert "rclone" in result.stdout, "Should check rclone"

        # In test mode, should check Docker
        assert "Docker" in result.stdout, "Should check Docker in test mode"

    @pytest.mark.functional
    def test_install_script_production_mode(self):
        """Test that install script works in production mode."""
        from photo_backup.consts import PROD_MODE_BASE_DIR

        prod_base_dir = Path(os.path.expanduser(PROD_MODE_BASE_DIR))

        # Clean up if it exists (but be careful not to delete user's real data)
        # Only clean up if it's a test directory
        if prod_base_dir.exists() and "test" in str(prod_base_dir).lower():
            shutil.rmtree(prod_base_dir)

        # Run install script in production mode (no --test flag)
        install_script = Path(__file__).parent.parent.parent / "install.py"
        result = subprocess.run(
            ["python3", str(install_script)],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        # Check that script succeeded
        assert result.returncode == 0, f"Install script failed: {result.stderr}"

        # Verify directories were created
        assert prod_base_dir.exists(), "Base directory should exist"
        assert (prod_base_dir / "state").exists(), "State directory should exist"
        assert (prod_base_dir / "config").exists(), "Config directory should exist"
        assert (prod_base_dir / "temp").exists(), "Temp directory should exist"

        # Verify output mentions production mode
        assert "PRODUCTION MODE" in result.stdout, "Output should mention production mode"

    @pytest.mark.functional
    def test_install_script_creates_test_structure(self):
        """Test that install script creates test structure (task requirement)."""
        from photo_backup.consts import TEST_MODE_BASE_DIR

        test_base_dir = Path(TEST_MODE_BASE_DIR)

        # Clean up if it exists
        if test_base_dir.exists():
            shutil.rmtree(test_base_dir)

        # Run install script in test mode
        install_script = Path(__file__).parent.parent.parent / "install.py"
        result = subprocess.run(
            ["python3", str(install_script), "--test"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        # Verify script succeeded
        assert result.returncode == 0, f"Install script failed: {result.stderr}"

        # Verify test structure was created
        assert test_base_dir.exists(), "Test base directory should exist"
        assert (test_base_dir / "state").is_dir(), "Test state directory should exist and be a directory"
        assert (test_base_dir / "config").is_dir(), "Test config directory should exist and be a directory"
        assert (test_base_dir / "temp").is_dir(), "Test temp directory should exist and be a directory"

        # Verify permissions (should be 0o755)
        for subdir in ["state", "config", "temp"]:
            subdir_path = test_base_dir / subdir
            mode = os.stat(subdir_path).st_mode & 0o777
            assert mode == 0o755, f"Directory {subdir} should have permissions 0o755, got {oct(mode)}"

        # Clean up
        if test_base_dir.exists():
            shutil.rmtree(test_base_dir)

    @pytest.mark.functional
    def test_create_launchd_plist_test_mode(self):
        """Test that create_launchd_plist creates valid plist for test mode."""
        import sys

        # Import the function
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import create_launchd_plist

        # Create temporary output path
        test_output = Path("/tmp/test_photo_backup_test.plist")

        # Clean up if exists
        if test_output.exists():
            test_output.unlink()

        # Create plist
        success, result = create_launchd_plist(test_mode=True, output_path=str(test_output))

        # Verify success
        assert success, f"Plist creation failed: {result}"
        assert test_output.exists(), "Plist file should be created"

        # Verify file permissions (should be 600)
        mode = os.stat(test_output).st_mode & 0o777
        assert mode == 0o600, f"Plist should have permissions 0o600, got {oct(mode)}"

        # Verify plist content
        with open(test_output, "rb") as f:
            plist_data = plistlib.load(f)

        # Check label
        assert plist_data["Label"] == "com.example.photo-backup.test", "Should use test label"

        # Check program arguments
        assert "ProgramArguments" in plist_data, "Should have ProgramArguments"
        program_args = plist_data["ProgramArguments"]
        assert len(program_args) >= 2, "Should have at least 2 arguments"
        assert "--test-mode" in program_args, "Should include --test-mode flag"

        # Check KeepAlive (test mode should use SuccessfulExit)
        assert "KeepAlive" in plist_data, "Should have KeepAlive"
        keepalive = plist_data["KeepAlive"]
        assert "SuccessfulExit" in keepalive, "Test mode should use SuccessfulExit"
        assert keepalive["SuccessfulExit"] is False, "Should restart on failure"

        # Check log paths (should use test paths)
        assert "StandardOutPath" in plist_data, "Should have StandardOutPath"
        assert "/tmp/photo-backup-test" in plist_data["StandardOutPath"], "Should use test log path"

        # Clean up
        if test_output.exists():
            test_output.unlink()

    @pytest.mark.functional
    def test_create_launchd_plist_production_mode(self):
        """Test that create_launchd_plist creates valid plist for production mode."""
        import sys

        # Import the function
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import create_launchd_plist

        # Create temporary output path
        test_output = Path("/tmp/test_photo_backup_prod.plist")

        # Clean up if exists
        if test_output.exists():
            test_output.unlink()

        # Create plist
        success, result = create_launchd_plist(test_mode=False, output_path=str(test_output))

        # Verify success
        assert success, f"Plist creation failed: {result}"
        assert test_output.exists(), "Plist file should be created"

        # Verify file permissions (should be 600)
        mode = os.stat(test_output).st_mode & 0o777
        assert mode == 0o600, f"Plist should have permissions 0o600, got {oct(mode)}"

        # Verify plist content
        with open(test_output, "rb") as f:
            plist_data = plistlib.load(f)

        # Check label
        assert plist_data["Label"] == "com.example.photo-backup", "Should use production label"

        # Check program arguments
        assert "ProgramArguments" in plist_data, "Should have ProgramArguments"
        program_args = plist_data["ProgramArguments"]
        assert len(program_args) >= 2, "Should have at least 2 arguments"
        assert "--test-mode" not in program_args, "Should not include --test-mode flag in production"

        # Check StartOnMount (production should have it)
        assert "StartOnMount" in plist_data, "Production mode should have StartOnMount"
        start_on_mount = plist_data["StartOnMount"]
        assert "/Volumes/4TB-SSD" in start_on_mount, "Should watch for drive mount"

        # Check KeepAlive (production should use PathState)
        assert "KeepAlive" in plist_data, "Should have KeepAlive"
        keepalive = plist_data["KeepAlive"]
        assert "PathState" in keepalive, "Production mode should use PathState"
        assert "/Volumes/4TB-SSD" in keepalive["PathState"], "Should keep alive while drive mounted"

        # Check log paths (should use production paths)
        assert "StandardOutPath" in plist_data, "Should have StandardOutPath"
        assert "Library/Logs/photo-backup" in plist_data["StandardOutPath"], "Should use production log path"

        # Clean up
        if test_output.exists():
            test_output.unlink()

    @pytest.mark.functional
    def test_create_launchd_plist_returns_string(self):
        """Test that create_launchd_plist returns plist as string when no output_path."""
        import sys

        # Import the function
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import create_launchd_plist

        # Create plist without output path
        success, result = create_launchd_plist(test_mode=True, output_path=None)

        # Verify success
        assert success, f"Plist creation failed: {result}"
        assert isinstance(result, str), "Should return string when no output_path"
        assert len(result) > 0, "Should return non-empty string"

        # Verify it's valid XML/plist
        plist_data = plistlib.loads(result.encode("utf-8"))
        assert "Label" in plist_data, "Should contain Label key"
        assert plist_data["Label"] == "com.example.photo-backup.test", "Should use test label"
