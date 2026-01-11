"""
Unit tests for the Verifier class.

Tests verifier instantiation, job creation, and basic verification structure.
"""


class TestVerifierInstantiation:
    """Test Verifier class instantiation."""

    def test_verifier_can_be_instantiated(self):
        """Test that Verifier can be instantiated."""
        from photo_backup.verify import Verifier

        # Instantiate with test_mode=True to avoid needing real credentials
        verifier = Verifier(test_mode=True)

        assert verifier is not None
        assert verifier.test_mode is True

    def test_verifier_initializes_with_config(self):
        """Test that Verifier initializes with config."""
        from photo_backup.config.config import Config
        from photo_backup.verify import Verifier

        config = Config(test_mode=True)
        verifier = Verifier(config=config)

        assert verifier.config is config

    def test_verifier_initializes_hash_calculator(self):
        """Test that Verifier initializes HashCalculator."""
        from photo_backup.verify import HashCalculator, Verifier

        verifier = Verifier(test_mode=True)

        assert verifier.hash_calculator is not None
        assert isinstance(verifier.hash_calculator, HashCalculator)

    def test_verifier_initializes_remote_lister(self):
        """Test that Verifier initializes RemoteLister."""
        from photo_backup.verify import RemoteLister, Verifier

        verifier = Verifier(test_mode=True)

        assert verifier.remote_lister is not None
        assert isinstance(verifier.remote_lister, RemoteLister)

    def test_verifier_initializes_credential_manager(self):
        """Test that Verifier initializes CredentialManager."""
        from photo_backup.credentials.manager import CredentialManager
        from photo_backup.verify import Verifier

        verifier = Verifier(test_mode=True)

        assert verifier.credential_manager is not None
        assert isinstance(verifier.credential_manager, CredentialManager)


class TestVerificationJob:
    """Test VerificationJob class."""

    def test_verification_job_instantiation(self):
        """Test that VerificationJob can be instantiated."""
        from photo_backup.verify import VerificationJob, VerificationStatus

        job = VerificationJob(
            source_path="/test/photos",
            destination="test-bucket/photos",
        )

        assert job.source_path == "/test/photos"
        assert job.destination == "test-bucket/photos"
        assert job.status == VerificationStatus.PENDING
        assert job.error is None

    def test_verification_job_repr(self):
        """Test VerificationJob string representation."""
        from photo_backup.verify import VerificationJob

        job = VerificationJob(
            source_path="/test/photos",
            destination="test-bucket",
        )

        repr_str = repr(job)
        assert "VerificationJob" in repr_str
        assert "/test/photos" in repr_str
        assert "pending" in repr_str

    def test_verification_job_default_lists(self):
        """Test that VerificationJob initializes with empty lists."""
        from photo_backup.verify import VerificationJob

        job = VerificationJob(
            source_path="/test",
            destination="bucket",
        )

        assert job.local_files == []
        assert job.remote_files == []
        assert job.mismatches == []
        assert job.missing_remote == []
        assert job.missing_local == []


class TestVerificationStatus:
    """Test VerificationStatus enum."""

    def test_verification_status_values(self):
        """Test that all expected statuses exist."""
        from photo_backup.verify import VerificationStatus

        assert VerificationStatus.PENDING.value == "pending"
        assert VerificationStatus.IN_PROGRESS.value == "in_progress"
        assert VerificationStatus.COMPLETED.value == "completed"
        assert VerificationStatus.FAILED.value == "failed"
        assert VerificationStatus.CANCELLED.value == "cancelled"


class TestFileHash:
    """Test FileHash dataclass."""

    def test_file_hash_instantiation(self):
        """Test that FileHash can be instantiated."""
        from photo_backup.verify import FileHash

        file_hash = FileHash(
            path="photos/2024/01/IMG_001.jpg",
            size=1024,
            hash_md5="abc123def456",
        )

        assert file_hash.path == "photos/2024/01/IMG_001.jpg"
        assert file_hash.size == 1024
        assert file_hash.hash_md5 == "abc123def456"
        assert file_hash.hash_type == "md5"

    def test_file_hash_equality_same_path_and_hash(self):
        """Test that FileHash equality compares path and hash."""
        from photo_backup.verify import FileHash

        hash1 = FileHash(path="test.jpg", size=100, hash_md5="abc123")
        hash2 = FileHash(path="test.jpg", size=200, hash_md5="abc123")

        # Same path and hash should be equal (even with different sizes)
        assert hash1 == hash2

    def test_file_hash_equality_different_hash(self):
        """Test that FileHash with different hash is not equal."""
        from photo_backup.verify import FileHash

        hash1 = FileHash(path="test.jpg", size=100, hash_md5="abc123")
        hash2 = FileHash(path="test.jpg", size=100, hash_md5="def456")

        assert hash1 != hash2

    def test_file_hash_equality_different_path(self):
        """Test that FileHash with different path is not equal."""
        from photo_backup.verify import FileHash

        hash1 = FileHash(path="test1.jpg", size=100, hash_md5="abc123")
        hash2 = FileHash(path="test2.jpg", size=100, hash_md5="abc123")

        assert hash1 != hash2


class TestVerificationResult:
    """Test VerificationResult dataclass."""

    def test_verification_result_instantiation(self):
        """Test that VerificationResult can be instantiated."""
        from photo_backup.verify import VerificationResult

        result = VerificationResult(
            success=True,
            total_files=100,
            verified_files=98,
            mismatched_files=2,
        )

        assert result.success is True
        assert result.total_files == 100
        assert result.verified_files == 98
        assert result.mismatched_files == 2

    def test_verification_result_get_summary(self):
        """Test that VerificationResult generates summary."""
        from photo_backup.verify import VerificationResult

        result = VerificationResult(
            success=True,
            total_files=100,
            verified_files=95,
            mismatched_files=3,
            missing_remote=2,
            duration_seconds=12.5,
        )

        summary = result.get_summary()

        assert "PASSED" in summary
        assert "100" in summary
        assert "95" in summary
        assert "12.5" in summary

    def test_verification_result_failed_summary(self):
        """Test that failed VerificationResult shows FAILED."""
        from photo_backup.verify import VerificationResult

        result = VerificationResult(
            success=False,
            total_files=100,
            errors=["File not found", "Hash mismatch"],
        )

        summary = result.get_summary()

        assert "FAILED" in summary
        assert "Errors: 2" in summary


class TestVerifierMethods:
    """Test Verifier methods."""

    def test_create_verification_job(self):
        """Test that Verifier can create a verification job."""
        from photo_backup.verify import VerificationJob, Verifier

        verifier = Verifier(test_mode=True)
        job = verifier.create_verification_job()

        assert job is not None
        assert isinstance(job, VerificationJob)

    def test_get_verification_info(self):
        """Test that Verifier returns verification info."""
        from photo_backup.verify import Verifier

        verifier = Verifier(test_mode=True)
        info = verifier.get_verification_info()

        assert "mode" in info
        assert info["mode"] == "test"
        assert "source_path" in info
        assert "destination" in info
        assert "credential_status" in info

    def test_set_progress_callback(self):
        """Test that Verifier can set progress callback."""
        from photo_backup.verify import Verifier

        verifier = Verifier(test_mode=True)

        callback_called = []

        def progress_callback(bytes_read: int, total_bytes: int) -> None:
            callback_called.append((bytes_read, total_bytes))

        verifier.set_progress_callback(progress_callback)

        assert verifier.hash_calculator.progress_callback is progress_callback
