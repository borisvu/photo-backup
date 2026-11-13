"""
Functional tests for install script.

These tests verify that the install script correctly checks prerequisites
and creates the necessary directory structure.
"""

import os
import plistlib
import shutil
import subprocess
import sys

import pytest
from pathlib import Path

# install.py manages a launchd agent: macOS only.
pytestmark = pytest.mark.launchd


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

        # Run install script in test mode (now using 'install' subcommand)
        install_script = Path(__file__).parent.parent.parent / "install.py"
        result = subprocess.run(
            [sys.executable, str(install_script), "install", "--test"],
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
            [sys.executable, str(install_script), "install", "--test"],
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
            [sys.executable, str(install_script), "install"],
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
            [sys.executable, str(install_script), "install", "--test"],
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


class TestPlistInstallation:
    """Tests for Plist Installation."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and clean up for each test."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import (
            TEST_SERVICE_LABEL,
            get_plist_path,
            get_service_label,
            is_service_loaded,
            unload_service,
        )

        self.get_plist_path = get_plist_path
        self.get_service_label = get_service_label
        self.is_service_loaded = is_service_loaded
        self.unload_service = unload_service
        self.TEST_SERVICE_LABEL = TEST_SERVICE_LABEL

        # Store original state
        self.was_loaded = is_service_loaded(test_mode=True)

        yield

        # Cleanup: unload test service and remove plist
        unload_service(test_mode=True)
        plist_path = get_plist_path(test_mode=True)
        if os.path.exists(plist_path):
            os.unlink(plist_path)

    @pytest.mark.functional
    def test_get_plist_path_test_mode(self):
        """Test that get_plist_path returns test path in test mode."""
        path = self.get_plist_path(test_mode=True)
        assert "/tmp/photo-backup-test" in path, "Test mode should use temp directory"
        assert "com.example.photo-backup.test.plist" in path, "Should use test service name"

    @pytest.mark.functional
    def test_get_plist_path_production_mode(self):
        """Test that get_plist_path returns LaunchAgents path in production mode."""
        path = self.get_plist_path(test_mode=False)
        assert "Library/LaunchAgents" in path, "Production mode should use LaunchAgents"
        assert "com.example.photo-backup.plist" in path, "Should use production service name"

    @pytest.mark.functional
    def test_get_service_label(self):
        """Test that get_service_label returns correct labels."""
        test_label = self.get_service_label(test_mode=True)
        prod_label = self.get_service_label(test_mode=False)

        assert test_label == "com.example.photo-backup.test", "Test label should have .test suffix"
        assert prod_label == "com.example.photo-backup", "Production label should not have .test suffix"

    @pytest.mark.functional
    def test_install_plist_test_mode(self):
        """Test that install_plist installs and loads test service."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist

        # Install the plist
        success, message = install_plist(test_mode=True)

        # Verify success
        assert success, f"Plist installation failed: {message}"

        # Verify plist file was created
        plist_path = self.get_plist_path(test_mode=True)
        assert os.path.exists(plist_path), f"Plist file should exist at {plist_path}"

        # Verify plist content
        with open(plist_path, "rb") as f:
            plist_data = plistlib.load(f)
        assert plist_data["Label"] == self.TEST_SERVICE_LABEL, "Should use test label"

        # Verify service is loaded
        assert self.is_service_loaded(test_mode=True), "Service should be loaded after installation"

    @pytest.mark.functional
    def test_install_plist_reinstalls_existing(self):
        """Test that install_plist can reinstall over existing service."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist

        # Install first time
        success1, _ = install_plist(test_mode=True)
        assert success1, "First installation should succeed"

        # Install again (should unload and reload)
        success2, message = install_plist(test_mode=True)
        assert success2, f"Reinstallation should succeed: {message}"

        # Verify service is still loaded
        assert self.is_service_loaded(test_mode=True), "Service should be loaded after reinstallation"

    @pytest.mark.functional
    def test_unload_service(self):
        """Test that unload_service properly unloads the service."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist

        # First install the service
        success, _ = install_plist(test_mode=True)
        assert success, "Installation should succeed"
        assert self.is_service_loaded(test_mode=True), "Service should be loaded"

        # Now unload it
        success, message = self.unload_service(test_mode=True)
        assert success, f"Unload should succeed: {message}"

        # Verify service is no longer loaded
        assert not self.is_service_loaded(test_mode=True), "Service should not be loaded after unload"


class TestConfigSetup:
    """Tests for Configuration Setup."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and clean up for each test."""
        from photo_backup.consts import TEST_MODE_BASE_DIR

        self.test_base_dir = Path(TEST_MODE_BASE_DIR)
        self.config_path = self.test_base_dir / "config" / "config.yaml"

        # Clean up before test
        if self.test_base_dir.exists():
            shutil.rmtree(self.test_base_dir)

        yield

        # Clean up after test
        if self.test_base_dir.exists():
            shutil.rmtree(self.test_base_dir)

    @pytest.mark.functional
    def test_setup_config_creates_config_file(self):
        """Test that setup_config creates config.yaml in config directory."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import setup_config

        # Run setup_config
        success, message = setup_config(test_mode=True)

        # Verify success
        assert success, f"Config setup failed: {message}"

        # Verify config file was created
        assert self.config_path.exists(), f"Config file should exist at {self.config_path}"

    @pytest.mark.functional
    def test_setup_config_copies_example(self):
        """Test that setup_config copies content from example config."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import setup_config

        # Get example config content for comparison
        example_config = Path(__file__).parent.parent.parent / "config.yaml.example"
        with open(example_config) as f:
            example_content = f.read()

        # Run setup_config
        success, _ = setup_config(test_mode=True)
        assert success, "Config setup should succeed"

        # Verify content matches example
        with open(self.config_path) as f:
            config_content = f.read()

        assert config_content == example_content, "Config content should match example"

    @pytest.mark.functional
    def test_setup_config_sets_permissions(self):
        """Test that setup_config sets secure permissions on config file."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import setup_config

        # Run setup_config
        success, _ = setup_config(test_mode=True)
        assert success, "Config setup should succeed"

        # Verify permissions (should be 0600)
        mode = os.stat(self.config_path).st_mode & 0o777
        assert mode == 0o600, f"Config should have permissions 0o600, got {oct(mode)}"

    @pytest.mark.functional
    def test_setup_config_preserves_existing(self):
        """Test that setup_config does not overwrite existing config."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import setup_config

        # First create the config
        success, _ = setup_config(test_mode=True)
        assert success, "First setup should succeed"

        # Modify the config
        custom_content = "# Custom configuration\ntest: value\n"
        with open(self.config_path, "w") as f:
            f.write(custom_content)

        # Run setup_config again
        success, message = setup_config(test_mode=True)
        assert success, "Second setup should succeed (no-op)"
        assert "already exists" in message, "Should indicate config already exists"

        # Verify content was not overwritten
        with open(self.config_path) as f:
            content = f.read()
        assert content == custom_content, "Config content should not be overwritten"

    @pytest.mark.functional
    def test_setup_config_creates_state_directories(self):
        """Test that setup_config ensures state directories exist."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import setup_config

        # Run setup_config
        success, _ = setup_config(test_mode=True)
        assert success, "Config setup should succeed"

        # Verify state directories were created
        assert (self.test_base_dir / "state").exists(), "State directory should exist"
        assert (self.test_base_dir / "config").exists(), "Config directory should exist"
        assert (self.test_base_dir / "temp").exists(), "Temp directory should exist"

    @pytest.mark.functional
    def test_install_with_config_setup(self):
        """Test that full install process creates ready-to-use config."""
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # Run install in test mode (skip service to avoid launchctl dependencies)
        result = subprocess.run(
            [sys.executable, str(install_script), "install", "--test", "--skip-service"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        # Verify script succeeded
        assert result.returncode == 0, f"Install script failed: {result.stderr}"

        # Verify config file was created
        assert self.config_path.exists(), "Config file should be created by install"

        # Verify config is valid YAML
        import yaml

        with open(self.config_path) as f:
            config_data = yaml.safe_load(f)

        assert "backup" in config_data, "Config should have backup section"
        assert "storage" in config_data, "Config should have storage section"
        assert "monitoring" in config_data, "Config should have monitoring section"


class TestUninstall:
    """Tests for Uninstall Script."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and clean up for each test."""
        import sys

        from photo_backup.consts import TEST_MODE_BASE_DIR

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import (
            get_plist_path,
            is_service_loaded,
            unload_service,
        )

        self.test_base_dir = Path(TEST_MODE_BASE_DIR)
        self.get_plist_path = get_plist_path
        self.is_service_loaded = is_service_loaded
        self.unload_service = unload_service

        # Clean up before test
        if self.test_base_dir.exists():
            shutil.rmtree(self.test_base_dir)

        yield

        # Clean up after test
        unload_service(test_mode=True)
        plist_path = get_plist_path(test_mode=True)
        if os.path.exists(plist_path):
            os.unlink(plist_path)
        if self.test_base_dir.exists():
            shutil.rmtree(self.test_base_dir)

    @pytest.mark.functional
    def test_uninstall_service_function(self):
        """Test that uninstall_service function removes service correctly."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist, uninstall_service

        # First install the service
        success, _ = install_plist(test_mode=True)
        assert success, "Installation should succeed"

        plist_path = self.get_plist_path(test_mode=True)
        assert os.path.exists(plist_path), "Plist should exist after install"

        # Now uninstall
        success, message = uninstall_service(test_mode=True, remove_data=False)
        assert success, f"Uninstall should succeed: {message}"

        # Verify service is unloaded
        assert not self.is_service_loaded(test_mode=True), "Service should be unloaded"

        # Verify plist is removed
        assert not os.path.exists(plist_path), "Plist should be removed"

    @pytest.mark.functional
    def test_uninstall_with_remove_data(self):
        """Test that uninstall removes data directories when --remove-data is used."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist, setup_config, uninstall_service
        from photo_backup.state_utils import get_state_directories

        # First install everything
        get_state_directories(test_mode=True)  # Create directories
        setup_config(test_mode=True)
        install_plist(test_mode=True)

        # Verify directories exist
        assert self.test_base_dir.exists(), "Base directory should exist"

        # Now uninstall with remove_data
        success, message = uninstall_service(test_mode=True, remove_data=True)
        assert success, f"Uninstall should succeed: {message}"

        # Verify directories are removed
        assert not self.test_base_dir.exists(), "Base directory should be removed"

    @pytest.mark.functional
    def test_uninstall_preserves_data_by_default(self):
        """Test that uninstall preserves data directories by default."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist, setup_config, uninstall_service
        from photo_backup.state_utils import get_state_directories

        # First install everything
        get_state_directories(test_mode=True)  # Create directories
        setup_config(test_mode=True)
        install_plist(test_mode=True)

        # Verify directories exist
        assert self.test_base_dir.exists(), "Base directory should exist"

        # Now uninstall without remove_data
        success, message = uninstall_service(test_mode=True, remove_data=False)
        assert success, f"Uninstall should succeed: {message}"

        # Verify directories are preserved
        assert self.test_base_dir.exists(), "Base directory should be preserved"

    @pytest.mark.functional
    def test_uninstall_cli_command(self):
        """Test that uninstall CLI command works correctly."""
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # First install
        result = subprocess.run(
            [sys.executable, str(install_script), "install", "--test"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Now uninstall (with --yes to skip confirmation)
        result = subprocess.run(
            [sys.executable, str(install_script), "uninstall", "--test", "--yes"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )
        assert result.returncode == 0, f"Uninstall failed: {result.stderr}"
        assert "Uninstall completed" in result.stdout, "Should show success message"

    @pytest.mark.functional
    def test_uninstall_cli_with_remove_data(self):
        """Test that uninstall CLI command removes data with --remove-data."""
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # First install
        result = subprocess.run(
            [sys.executable, str(install_script), "install", "--test"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Verify directories exist
        assert self.test_base_dir.exists(), "Base directory should exist after install"

        # Now uninstall with --remove-data
        result = subprocess.run(
            [sys.executable, str(install_script), "uninstall", "--test", "--remove-data", "--yes"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )
        assert result.returncode == 0, f"Uninstall failed: {result.stderr}"

        # Verify directories are removed
        assert not self.test_base_dir.exists(), "Base directory should be removed"


class TestValidation:
    """Tests for Install Validation."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and clean up for each test."""
        import sys

        from photo_backup.consts import TEST_MODE_BASE_DIR

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import get_plist_path, unload_service

        self.test_base_dir = Path(TEST_MODE_BASE_DIR)
        self.get_plist_path = get_plist_path
        self.unload_service = unload_service

        # Clean up before test
        if self.test_base_dir.exists():
            shutil.rmtree(self.test_base_dir)

        yield

        # Clean up after test
        unload_service(test_mode=True)
        plist_path = get_plist_path(test_mode=True)
        if os.path.exists(plist_path):
            os.unlink(plist_path)
        if self.test_base_dir.exists():
            shutil.rmtree(self.test_base_dir)

    @pytest.mark.functional
    def test_validate_installation_passes_after_install(self):
        """Test that validate_installation passes after successful install."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist, setup_config, validate_installation
        from photo_backup.state_utils import get_state_directories

        # Install everything
        get_state_directories(test_mode=True)
        setup_config(test_mode=True)
        install_plist(test_mode=True)

        # Validate (note: Minio check will likely fail, but core checks should pass)
        _all_passed, results = validate_installation(test_mode=True)

        # Check that core components passed
        core_checks = [
            r
            for r in results
            if r[0] in ["Base directory", "State directory", "Config directory", "Config file", "Plist file"]
        ]
        for check_name, passed, message in core_checks:
            assert passed, f"{check_name} should pass: {message}"

    @pytest.mark.functional
    def test_validate_installation_fails_without_install(self):
        """Test that validate_installation fails when not installed."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import validate_installation

        # Validate without installing
        all_passed, results = validate_installation(test_mode=True)

        # Should fail because directories don't exist
        assert not all_passed, "Validation should fail without installation"

        # Check that base directory check failed
        base_check = next(r for r in results if r[0] == "Base directory")
        assert not base_check[1], "Base directory check should fail"

    @pytest.mark.functional
    def test_validate_checks_permissions(self):
        """Test that validate_installation checks file permissions."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import setup_config, validate_installation
        from photo_backup.state_utils import get_state_directories

        # Create directories and config
        get_state_directories(test_mode=True)
        setup_config(test_mode=True)

        # Validate
        _, results = validate_installation(test_mode=True)

        # Check that permissions are validated
        perm_checks = [r for r in results if "permissions" in r[0].lower()]
        assert len(perm_checks) > 0, "Should check permissions"

        # Config permissions should pass (0600)
        config_perm = [r for r in perm_checks if "Config" in r[0]]
        if config_perm:
            assert config_perm[0][1], f"Config permissions should be correct: {config_perm[0][2]}"

    @pytest.mark.functional
    def test_validate_cli_command(self):
        """Test that validate CLI command works correctly."""
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # First install (skip service to simplify)
        result = subprocess.run(
            [sys.executable, str(install_script), "install", "--test", "--skip-service"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Now validate
        result = subprocess.run(
            [sys.executable, str(install_script), "validate", "--test"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        # Check output contains validation results
        assert "Validation Results" in result.stdout, "Should show validation results"
        assert "Base directory" in result.stdout, "Should check base directory"
        assert "Config file" in result.stdout, "Should check config file"

    @pytest.mark.functional
    def test_validate_reports_issues(self):
        """Test that validate command reports issues correctly."""
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # Validate without installing (should fail)
        result = subprocess.run(
            [sys.executable, str(install_script), "validate", "--test"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        # Should exit with error code
        assert result.returncode != 0, "Validate should fail when not installed"
        assert "issues" in result.stdout.lower() or "✗" in result.stdout, "Should report issues"

    @pytest.mark.functional
    def test_validate_checks_minio_in_test_mode(self):
        """Test that validate checks Minio connectivity in test mode."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import validate_installation

        # Validate in test mode
        _, results = validate_installation(test_mode=True)

        # Should include Minio check
        minio_check = [r for r in results if "Minio" in r[0]]
        assert len(minio_check) > 0, "Should check Minio connectivity in test mode"


class TestUpgrade:
    """Tests for Upgrade Support."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and clean up for each test."""
        import sys

        from photo_backup.consts import TEST_MODE_BASE_DIR

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import get_plist_path, unload_service

        self.test_base_dir = Path(TEST_MODE_BASE_DIR)
        self.config_path = self.test_base_dir / "config" / "config.yaml"
        self.get_plist_path = get_plist_path
        self.unload_service = unload_service

        # Clean up before test
        if self.test_base_dir.exists():
            shutil.rmtree(self.test_base_dir)

        yield

        # Clean up after test
        unload_service(test_mode=True)
        plist_path = get_plist_path(test_mode=True)
        if os.path.exists(plist_path):
            os.unlink(plist_path)
        if self.test_base_dir.exists():
            shutil.rmtree(self.test_base_dir)

    @pytest.mark.functional
    def test_detect_existing_install_no_install(self):
        """Test that detect_existing_install returns correct info when not installed."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import detect_existing_install

        # Nothing installed yet
        info = detect_existing_install(test_mode=True)

        assert not info["installed"], "Should not be installed"
        assert not info["has_config"], "Should not have config"
        assert not info["has_plist"], "Should not have plist"
        assert not info["service_loaded"], "Service should not be loaded"

    @pytest.mark.functional
    def test_detect_existing_install_after_install(self):
        """Test that detect_existing_install detects installation correctly."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import detect_existing_install, install_plist, setup_config
        from photo_backup.state_utils import get_state_directories

        # Install everything
        get_state_directories(test_mode=True)
        setup_config(test_mode=True)
        install_plist(test_mode=True)

        # Now detect
        info = detect_existing_install(test_mode=True)

        assert info["installed"], "Should be installed"
        assert info["has_config"], "Should have config"
        assert info["has_plist"], "Should have plist"
        assert info["service_loaded"], "Service should be loaded"

    @pytest.mark.functional
    def test_backup_config(self):
        """Test that backup_config creates a backup file."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import backup_config, setup_config
        from photo_backup.state_utils import get_state_directories

        # Create config
        get_state_directories(test_mode=True)
        setup_config(test_mode=True)

        # Write some custom content
        with open(self.config_path, "w") as f:
            f.write("custom: content\n")

        # Backup
        success, backup_path = backup_config(test_mode=True)

        assert success, f"Backup should succeed: {backup_path}"
        assert os.path.exists(backup_path), "Backup file should exist"

        # Verify backup content matches original
        with open(backup_path) as f:
            backup_content = f.read()
        assert backup_content == "custom: content\n", "Backup should have original content"

    @pytest.mark.functional
    def test_upgrade_preserves_config(self):
        """Test that upgrade preserves existing config by default."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist, setup_config, upgrade_installation
        from photo_backup.state_utils import get_state_directories

        # Install everything first
        get_state_directories(test_mode=True)
        setup_config(test_mode=True)
        install_plist(test_mode=True)

        # Modify config
        custom_content = "# Custom user config\ntest: value\n"
        with open(self.config_path, "w") as f:
            f.write(custom_content)

        # Upgrade
        success, message = upgrade_installation(test_mode=True, preserve_config=True)

        assert success, f"Upgrade should succeed: {message}"

        # Verify config was preserved
        with open(self.config_path) as f:
            content = f.read()
        assert content == custom_content, "Config should be preserved"

    @pytest.mark.functional
    def test_upgrade_replaces_config_when_requested(self):
        """Test that upgrade replaces config when preserve_config=False."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist, setup_config, upgrade_installation
        from photo_backup.state_utils import get_state_directories

        # Install everything first
        get_state_directories(test_mode=True)
        setup_config(test_mode=True)
        install_plist(test_mode=True)

        # Modify config
        custom_content = "# Custom user config\ntest: value\n"
        with open(self.config_path, "w") as f:
            f.write(custom_content)

        # Upgrade without preserving config
        success, message = upgrade_installation(test_mode=True, preserve_config=False)

        assert success, f"Upgrade should succeed: {message}"

        # Verify config was replaced (should have example config content)
        with open(self.config_path) as f:
            content = f.read()
        assert content != custom_content, "Config should be replaced"
        assert "backup" in content.lower(), "Should have default config content"

    @pytest.mark.functional
    def test_upgrade_fails_without_existing_install(self):
        """Test that upgrade fails when no existing installation and not forced."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import upgrade_installation

        # Try to upgrade without existing installation
        success, message = upgrade_installation(test_mode=True, force=False)

        assert not success, "Upgrade should fail without existing installation"
        assert "No existing installation" in message, "Should indicate no existing installation"

    @pytest.mark.functional
    def test_upgrade_with_force_flag(self):
        """Test that upgrade works with --force flag even without existing installation."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import upgrade_installation

        # Try to upgrade with force flag
        success, message = upgrade_installation(test_mode=True, force=True)

        assert success, f"Forced upgrade should succeed: {message}"

        # Verify installation was created
        assert self.test_base_dir.exists(), "Base directory should exist"
        assert self.config_path.exists(), "Config should exist"

    @pytest.mark.functional
    def test_upgrade_cli_command(self):
        """Test that upgrade CLI command works correctly."""
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # First install
        result = subprocess.run(
            [sys.executable, str(install_script), "install", "--test"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Now upgrade
        result = subprocess.run(
            [sys.executable, str(install_script), "upgrade", "--test", "--yes"],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )
        assert result.returncode == 0, f"Upgrade failed: {result.stderr}"
        assert "Upgrade completed" in result.stdout, "Should show success message"

    @pytest.mark.functional
    def test_upgrade_creates_backup(self):
        """Test that upgrade creates config backup."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from install import install_plist, setup_config, upgrade_installation
        from photo_backup.state_utils import get_state_directories

        # Install everything first
        get_state_directories(test_mode=True)
        setup_config(test_mode=True)
        install_plist(test_mode=True)

        # Upgrade
        success, message = upgrade_installation(test_mode=True, preserve_config=True)

        assert success, f"Upgrade should succeed: {message}"
        assert "Backup at:" in message or "completed successfully" in message, "Should indicate backup or success"

        # Check for backup file
        config_dir = self.test_base_dir / "config"
        backup_files = list(config_dir.glob("config.yaml.backup.*"))
        assert len(backup_files) >= 1, "Should have at least one backup file"
