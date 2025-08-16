"""
Unit tests for the backup module.
"""

from photo_backup.backup import BackupEngine, BackupJob


class TestBackupJob:
    """Test BackupJob class."""

    def test_backup_job_initialization(self):
        """Test BackupJob can be initialized correctly."""
        job = BackupJob("/source/path", "dest:bucket")

        assert job.source_path == "/source/path"
        assert job.destination == "dest:bucket"
        assert job.dry_run is False
        assert job.status == "pending"
        assert job.error is None

    def test_backup_job_with_dry_run(self):
        """Test BackupJob with dry run mode."""
        job = BackupJob("/source/path", "dest:bucket", dry_run=True)

        assert job.dry_run is True

    def test_backup_job_repr(self):
        """Test BackupJob string representation."""
        job = BackupJob("/source/path", "dest:bucket")
        expected = "BackupJob(source='/source/path', dest='dest:bucket', status='pending')"

        assert repr(job) == expected


class TestBackupEngine:
    """Test BackupEngine class."""

    def test_backup_engine_initialization_test_mode(self):
        """Test BackupEngine can be instantiated in test mode."""
        engine = BackupEngine(test_mode=True)

        assert engine.test_mode is True
        assert engine.config is not None
        assert engine.credential_manager is not None

    def test_backup_engine_initialization_production_mode(self):
        """Test BackupEngine can be instantiated in production mode."""
        engine = BackupEngine(test_mode=False)

        assert engine.test_mode is False
        assert engine.config is not None
        assert engine.credential_manager is not None

    def test_backup_engine_create_job_test_mode(self):
        """Test creating backup job in test mode."""
        engine = BackupEngine(test_mode=True)
        job = engine.create_backup_job()

        assert isinstance(job, BackupJob)
        assert job.source_path == "/tmp/photo-backup-test-photos"
        assert job.destination == "minio-test:my-photo-backup-bucket-test"

    def test_backup_engine_get_backup_info_test_mode(self):
        """Test getting backup info in test mode."""
        engine = BackupEngine(test_mode=True)
        info = engine.get_backup_info()

        assert info["mode"] == "test"
        assert info["source_path"] == "/tmp/photo-backup-test-photos"
        assert info["destination"] == "minio-test:my-photo-backup-bucket-test"
        assert info["endpoint"] == "localhost:9000"
        assert "dry_run" in info
        assert "credential_status" in info

    def test_backup_engine_get_backup_info_production_mode(self):
        """Test getting backup info in production mode."""
        engine = BackupEngine(test_mode=False)
        info = engine.get_backup_info()

        assert info["mode"] == "production"
        assert info["endpoint"] == "s3.wasabisys.com"

    def test_backup_engine_validate_environment(self):
        """Test environment validation (may fail without Minio)."""
        engine = BackupEngine(test_mode=True)
        is_valid, errors = engine.validate_backup_environment()

        # Environment validation should complete without exceptions
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)
        # In test environment without Minio, validation may fail - that's expected
