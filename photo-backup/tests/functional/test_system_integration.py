"""
Comprehensive system integration tests.

These tests verify that all major components work together correctly.
"""

import pytest


class TestSystemIntegration:
    """Comprehensive system integration tests."""

    MINIO_PORT = 9009

    # Use shared fixture factory to avoid code duplication
    from tests.functional.minio_test_utils import MinioTestUtils

    minio_container = MinioTestUtils.create_minio_fixture("photo-backup-system-test", port=MINIO_PORT)

    @pytest.mark.functional
    def test_modules_can_be_imported(self):
        """Test that all main modules can be imported."""
        from photo_backup.config import Config
        from photo_backup.format_utils import format_bytes
        from photo_backup.fs_utils import ensure_directory
        from photo_backup.logger import setup_logger
        from photo_backup.main import main

        assert main is not None
        assert Config is not None
        assert setup_logger is not None
        assert format_bytes is not None
        assert ensure_directory is not None

    @pytest.mark.functional
    def test_config_system_integration(self):
        """Test that config system works in both modes."""
        from photo_backup.config import Config

        # Production config
        prod_config = Config(test_mode=False)
        prod_config.load_config()
        assert prod_config.get("storage.endpoint") == "s3.wasabisys.com"

        # Test config
        test_config = Config(test_mode=True)
        test_config.load_config()
        assert test_config.get("storage.endpoint") == "localhost:9000"

    @pytest.mark.functional
    def test_logger_system_integration(self):
        """Test that logger system works."""
        import logging

        from photo_backup.logger import setup_logger

        logger = setup_logger("integration_test", logging.INFO)
        assert logger.name == "integration_test"
        assert logger.level == logging.INFO

    @pytest.mark.functional
    def test_utils_system_integration(self, temp_dir):
        """Test that utils system works."""
        from photo_backup.format_utils import format_bytes
        from photo_backup.fs_utils import ensure_directory

        # Test format_bytes
        assert format_bytes(1048576) == "1.00 MB"

        # Test ensure_directory
        test_dir = temp_dir / "integration_test"
        success, error = ensure_directory(str(test_dir))
        assert success is True
        assert error is None
        assert test_dir.is_dir()

    @pytest.mark.functional
    def test_cli_production_mode_integration(self, cli_runner):
        """Test CLI production mode integration."""
        result = cli_runner([])

        assert result.returncode == 0
        assert "PRODUCTION MODE" in result.stdout
        assert "s3.wasabisys.com" in result.stdout
        assert "INFO" in result.stdout
        assert "CLI initialization completed successfully" in result.stdout

    @pytest.mark.functional
    def test_cli_test_mode_integration(self, cli_runner):
        """Test CLI test mode integration."""
        result = cli_runner(["--test-mode"])

        assert result.returncode == 0
        assert "TEST MODE" in result.stdout
        assert "localhost:9000" in result.stdout
        assert "DEBUG" in result.stdout
        assert "CLI initialization completed successfully" in result.stdout

    @pytest.mark.functional
    @pytest.mark.slow
    def test_full_infrastructure_integration(self, minio_container, test_photos):  # noqa: ARG002
        """Test complete integration with all infrastructure components."""
        import os
        import subprocess

        # Verify test photos exist
        assert test_photos.exists()

        # Count all photo files (should be 5 from conftest.py)
        photo_files = list(test_photos.rglob("*"))
        photo_files = [f for f in photo_files if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".dng", ".cr2"]]
        assert len(photo_files) == 5, f"Should have 5 test photos, found {len(photo_files)}"

        # Configure environment for custom Minio endpoint
        env = os.environ.copy()
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
        env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
        env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

        # Run CLI in test mode
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        combined_output = result.stdout + result.stderr

        assert result.returncode == 0
        assert "TEST MODE" in combined_output
        assert f"localhost:{self.MINIO_PORT}" in combined_output
        assert "starting in TEST MODE" in combined_output
        assert "CLI initialization completed successfully" in combined_output

        # Note: Minio container is started by the fixture, but we don't need to verify
        # it's running here since that's tested in infrastructure tests

    @pytest.mark.functional
    def test_config_logger_utils_integration(self, temp_dir):
        """Test integration between config, logger, and utils."""
        import logging

        from photo_backup.config import Config
        from photo_backup.format_utils import format_bytes
        from photo_backup.fs_utils import ensure_directory
        from photo_backup.logger import setup_logger

        # Initialize config in test mode
        config = Config(test_mode=True)
        config.load_config()

        # Initialize logger with DEBUG level for test mode
        logger = setup_logger("integration", logging.DEBUG)

        # Use utils to create state directory
        state_dir = temp_dir / "state"
        success, error = ensure_directory(str(state_dir))
        assert success is True

        # Log the operation with formatted size
        dir_size = sum(f.stat().st_size for f in state_dir.rglob("*") if f.is_file())
        formatted_size = format_bytes(dir_size)

        # This should work without errors
        logger.info(f"Created state directory: {state_dir} (size: {formatted_size})")

        # Verify everything worked
        assert state_dir.is_dir()
        assert logger.level == logging.DEBUG  # Test mode
        assert "0 B" in formatted_size  # Empty directory

    @pytest.mark.functional
    def test_error_handling_integration(self):
        """Test that error handling works across components."""
        from photo_backup.format_utils import format_bytes
        from photo_backup.fs_utils import ensure_directory

        # Test utils error handling
        success, error = ensure_directory("/root/should_fail")
        assert success is False
        assert error is not None

        # Test format_bytes error handling
        result = format_bytes("invalid")
        assert result == "0 B"

        # Test config error handling (should not crash)
        from photo_backup.config import Config

        config = Config(test_mode=True)
        config.load_config()

        # Missing key should return None
        assert config.get("nonexistent.key") is None

    @pytest.mark.functional
    def test_mode_isolation_integration(self):
        """Test that test and production modes are properly isolated."""
        import logging

        from photo_backup.config import Config
        from photo_backup.logger import setup_logger

        # Production mode
        prod_config = Config(test_mode=False)
        prod_config.load_config()
        prod_logger = setup_logger("prod", logging.INFO)

        # Test mode
        test_config = Config(test_mode=True)
        test_config.load_config()
        test_logger = setup_logger("test", logging.DEBUG)

        # Verify isolation
        assert prod_config.get("storage.endpoint") != test_config.get("storage.endpoint")
        assert prod_config.get("backup.source_path") != test_config.get("backup.source_path")
        assert prod_logger.level != test_logger.level

        # Verify specific values
        assert prod_config.get("storage.endpoint") == "s3.wasabisys.com"
        assert test_config.get("storage.endpoint") == "localhost:9000"
        assert prod_logger.level == logging.INFO
        assert test_logger.level == logging.DEBUG

    @pytest.mark.functional
    def test_cli_version_integration(self, cli_runner):
        """Test CLI version integration."""
        result = cli_runner(["--version"])

        assert result.returncode == 0
        assert result.stdout.strip() == "Photo Backup v0.1.0"

    @pytest.mark.functional
    def test_cli_help_integration(self, cli_runner):
        """Test CLI help integration."""
        result = cli_runner(["--help"])

        assert result.returncode == 0
        assert "--test-mode" in result.stdout
        assert "--version" in result.stdout
        assert "Photo Backup System" in result.stdout

    @pytest.mark.functional
    def test_component_interaction_workflow(self, temp_dir):
        """Test a complete workflow using all components."""
        import logging

        from photo_backup.config import Config
        from photo_backup.format_utils import format_bytes
        from photo_backup.fs_utils import ensure_directory
        from photo_backup.logger import setup_logger

        # Step 1: Initialize config
        config = Config(test_mode=True)
        config.load_config()

        # Step 2: Setup logger based on config
        logger = setup_logger("workflow", logging.DEBUG)

        # Step 3: Create directories using utils
        base_dir = temp_dir / "workflow_test"
        state_dir = base_dir / "state"
        photos_dir = base_dir / "photos"

        for directory in [base_dir, state_dir, photos_dir]:
            success, error = ensure_directory(str(directory))
            assert success is True, f"Failed to create {directory}: {error}"
            logger.debug(f"Created directory: {directory}")

        # Step 4: Create some test files
        test_files = []
        for i in range(3):
            test_file = photos_dir / f"photo_{i}.jpg"
            content = f"Test photo content {i}" * 100  # Make it bigger
            test_file.write_text(content)
            test_files.append(test_file)
            logger.debug(f"Created test file: {test_file}")

        # Step 5: Calculate and format total size
        total_size = sum(f.stat().st_size for f in test_files)
        formatted_size = format_bytes(total_size)
        logger.info(f"Total test data size: {formatted_size}")

        # Step 6: Verify everything worked
        assert all(f.exists() for f in test_files)
        assert total_size > 0
        assert "B" in formatted_size  # Should have some unit
        assert config.get("storage.endpoint") == "localhost:9000"  # Test mode
        assert logger.level == logging.DEBUG
