"""
Unit tests for hash comparison functionality.

Tests the compare_hashes method and related dataclasses.
"""

from photo_backup.verify import (
    ComparisonResult,
    FileHash,
    FileMismatch,
    Verifier,
)


class TestFileMismatchDataclass:
    """Test FileMismatch dataclass."""

    def test_file_mismatch_instantiation(self):
        """Test that FileMismatch can be instantiated."""
        mismatch = FileMismatch(
            path="photos/test.jpg",
            local_hash="abc123",
            remote_hash="def456",
            local_size=1000,
            remote_size=1000,
            mismatch_type="hash",
        )

        assert mismatch.path == "photos/test.jpg"
        assert mismatch.local_hash == "abc123"
        assert mismatch.remote_hash == "def456"
        assert mismatch.mismatch_type == "hash"

    def test_file_mismatch_repr(self):
        """Test FileMismatch string representation."""
        mismatch = FileMismatch(
            path="test.jpg",
            local_hash="abc",
            remote_hash="def",
            local_size=100,
            remote_size=200,
            mismatch_type="both",
        )

        repr_str = repr(mismatch)
        assert "FileMismatch" in repr_str
        assert "test.jpg" in repr_str
        assert "both" in repr_str


class TestComparisonResultDataclass:
    """Test ComparisonResult dataclass."""

    def test_comparison_result_instantiation(self):
        """Test that ComparisonResult can be instantiated."""
        result = ComparisonResult()

        assert result.matched_files == []
        assert result.mismatched_files == []
        assert result.missing_remote == []
        assert result.missing_local == []

    def test_comparison_result_total_local_files(self):
        """Test total_local_files property."""
        result = ComparisonResult(
            matched_files=["a.jpg", "b.jpg"],
            mismatched_files=[FileMismatch("c.jpg", "abc", "def", 100, 100, "hash")],
            missing_remote=[FileHash("d.jpg", 100, "ghi")],
        )

        assert result.total_local_files == 4  # 2 matched + 1 mismatch + 1 missing_remote

    def test_comparison_result_total_remote_files(self):
        """Test total_remote_files property."""
        result = ComparisonResult(
            matched_files=["a.jpg", "b.jpg"],
            mismatched_files=[FileMismatch("c.jpg", "abc", "def", 100, 100, "hash")],
            missing_local=[FileHash("e.jpg", 100, "jkl")],
        )

        assert result.total_remote_files == 4  # 2 matched + 1 mismatch + 1 missing_local

    def test_comparison_result_has_issues_with_mismatches(self):
        """Test has_issues property with mismatches."""
        result = ComparisonResult(
            matched_files=["a.jpg"],
            mismatched_files=[FileMismatch("b.jpg", "abc", "def", 100, 100, "hash")],
        )

        assert result.has_issues is True

    def test_comparison_result_has_issues_with_missing_remote(self):
        """Test has_issues property with missing remote files."""
        result = ComparisonResult(
            matched_files=["a.jpg"],
            missing_remote=[FileHash("b.jpg", 100, "abc")],
        )

        assert result.has_issues is True

    def test_comparison_result_has_issues_with_missing_local(self):
        """Test has_issues property with missing local files."""
        result = ComparisonResult(
            matched_files=["a.jpg"],
            missing_local=[FileHash("b.jpg", 100, "abc")],
        )

        assert result.has_issues is True

    def test_comparison_result_no_issues(self):
        """Test has_issues property when all files match."""
        result = ComparisonResult(
            matched_files=["a.jpg", "b.jpg", "c.jpg"],
        )

        assert result.has_issues is False

    def test_comparison_result_get_summary(self):
        """Test get_summary method."""
        result = ComparisonResult(
            matched_files=["a.jpg", "b.jpg"],
            mismatched_files=[FileMismatch("c.jpg", "abc", "def", 100, 100, "hash")],
            comparison_time_seconds=1.5,
        )

        summary = result.get_summary()

        assert "ISSUES FOUND" in summary
        assert "Matched files: 2" in summary
        assert "Mismatched files: 1" in summary

    def test_comparison_result_get_summary_all_matched(self):
        """Test get_summary when all files match."""
        result = ComparisonResult(
            matched_files=["a.jpg", "b.jpg"],
        )

        summary = result.get_summary()

        assert "ALL MATCHED" in summary


class TestVerifierCompareHashes:
    """Test Verifier.compare_hashes method."""

    def test_compare_hashes_all_match(self):
        """Test comparison when all files match."""
        verifier = Verifier(test_mode=True)

        local_files = [
            FileHash("photo1.jpg", 1000, "abc123"),
            FileHash("photo2.jpg", 2000, "def456"),
            FileHash("photo3.jpg", 3000, "ghi789"),
        ]

        remote_files = [
            FileHash("photo1.jpg", 1000, "abc123"),
            FileHash("photo2.jpg", 2000, "def456"),
            FileHash("photo3.jpg", 3000, "ghi789"),
        ]

        result = verifier.compare_hashes(local_files, remote_files)

        assert len(result.matched_files) == 3
        assert len(result.mismatched_files) == 0
        assert len(result.missing_remote) == 0
        assert len(result.missing_local) == 0
        assert result.has_issues is False

    def test_compare_hashes_same_size_different_hash_is_a_match(self):
        """Same size is a match even if hashes differ (size + existence by design).

        Remote MD5s are no longer fetched (too slow on Wasabi), so the verifier
        deliberately ignores hash_md5 and only compares size.
        """
        verifier = Verifier(test_mode=True)

        local_files = [
            FileHash("photo1.jpg", 1000, "abc123"),
            FileHash("photo2.jpg", 2000, "def456"),
        ]

        remote_files = [
            FileHash("photo1.jpg", 1000, "abc123"),
            FileHash("photo2.jpg", 2000, "DIFFERENT"),  # Different hash, same size
        ]

        result = verifier.compare_hashes(local_files, remote_files)

        assert sorted(result.matched_files) == ["photo1.jpg", "photo2.jpg"]
        assert result.mismatched_files == []
        assert result.has_issues is False

    def test_compare_hashes_finds_size_mismatches(self):
        """Test comparison flags files whose sizes differ (e.g. truncated upload)."""
        verifier = Verifier(test_mode=True)

        local_files = [
            FileHash("photo1.jpg", 1000),
            FileHash("photo2.jpg", 2000),
        ]

        remote_files = [
            FileHash("photo1.jpg", 1000),
            FileHash("photo2.jpg", 1500),  # Truncated on remote
        ]

        result = verifier.compare_hashes(local_files, remote_files)

        assert result.matched_files == ["photo1.jpg"]
        assert len(result.mismatched_files) == 1
        mismatch = result.mismatched_files[0]
        assert mismatch.path == "photo2.jpg"
        assert mismatch.local_size == 2000
        assert mismatch.remote_size == 1500
        assert mismatch.mismatch_type == "size"
        assert result.has_issues is True

    def test_compare_hashes_finds_missing_remote(self):
        """Test comparison finds files missing on remote."""
        verifier = Verifier(test_mode=True)

        local_files = [
            FileHash("photo1.jpg", 1000, "abc123"),
            FileHash("photo2.jpg", 2000, "def456"),
            FileHash("photo3.jpg", 3000, "ghi789"),  # Only local
        ]

        remote_files = [
            FileHash("photo1.jpg", 1000, "abc123"),
            FileHash("photo2.jpg", 2000, "def456"),
        ]

        result = verifier.compare_hashes(local_files, remote_files)

        assert len(result.matched_files) == 2
        assert len(result.missing_remote) == 1
        assert result.missing_remote[0].path == "photo3.jpg"

    def test_compare_hashes_finds_missing_local(self):
        """Test comparison finds files missing locally."""
        verifier = Verifier(test_mode=True)

        local_files = [
            FileHash("photo1.jpg", 1000, "abc123"),
        ]

        remote_files = [
            FileHash("photo1.jpg", 1000, "abc123"),
            FileHash("photo2.jpg", 2000, "def456"),  # Only remote
        ]

        result = verifier.compare_hashes(local_files, remote_files)

        assert len(result.matched_files) == 1
        assert len(result.missing_local) == 1
        assert result.missing_local[0].path == "photo2.jpg"

    def test_compare_hashes_size_mismatch_reported_as_size_even_if_hash_differs(self):
        """A size difference is reported as type 'size'; hashes are carried, not compared."""
        verifier = Verifier(test_mode=True)

        local_files = [
            FileHash("photo1.jpg", 1000, "abc123"),
        ]

        remote_files = [
            FileHash("photo1.jpg", 2000, "def456"),  # Different size AND hash
        ]

        result = verifier.compare_hashes(local_files, remote_files)

        assert len(result.mismatched_files) == 1
        mismatch = result.mismatched_files[0]
        assert mismatch.mismatch_type == "size"
        assert mismatch.local_hash == "abc123"
        assert mismatch.remote_hash == "def456"

    def test_compare_hashes_empty_lists(self):
        """Test comparison with empty lists."""
        verifier = Verifier(test_mode=True)

        result = verifier.compare_hashes([], [])

        assert len(result.matched_files) == 0
        assert len(result.mismatched_files) == 0
        assert len(result.missing_remote) == 0
        assert len(result.missing_local) == 0
        assert result.has_issues is False

    def test_compare_hashes_handles_nested_paths(self):
        """Test comparison handles nested directory paths."""
        verifier = Verifier(test_mode=True)

        local_files = [
            FileHash("2024/01/photo1.jpg", 1000, "abc123"),
            FileHash("2024/02/photo2.jpg", 2000, "def456"),
        ]

        remote_files = [
            FileHash("2024/01/photo1.jpg", 1000, "abc123"),
            FileHash("2024/02/photo2.jpg", 2000, "def456"),
        ]

        result = verifier.compare_hashes(local_files, remote_files)

        assert len(result.matched_files) == 2
        assert "2024/01/photo1.jpg" in result.matched_files
        assert "2024/02/photo2.jpg" in result.matched_files

    def test_compare_hashes_handles_missing_hash_gracefully(self):
        """Test comparison handles files with missing hashes."""
        verifier = Verifier(test_mode=True)

        local_files = [
            FileHash("photo1.jpg", 1000, None),  # No hash
        ]

        remote_files = [
            FileHash("photo1.jpg", 1000, None),  # No hash
        ]

        result = verifier.compare_hashes(local_files, remote_files)

        # Should assume match when hashes are missing
        assert len(result.matched_files) == 1

    def test_compare_hashes_records_timing(self):
        """Test comparison records execution time."""
        verifier = Verifier(test_mode=True)

        local_files = [FileHash(f"photo{i}.jpg", 1000, f"hash{i}") for i in range(10)]
        remote_files = [FileHash(f"photo{i}.jpg", 1000, f"hash{i}") for i in range(10)]

        result = verifier.compare_hashes(local_files, remote_files)

        assert result.comparison_time_seconds >= 0

    def test_compare_hashes_complex_scenario(self):
        """Test comparison with mixed scenario."""
        verifier = Verifier(test_mode=True)

        local_files = [
            FileHash("match1.jpg", 1000, "aaa"),  # Matches
            FileHash("match2.jpg", 2000, "bbb"),  # Same size, different hash: still a match
            FileHash("mismatch.jpg", 3000, "ccc"),  # Size mismatch
            FileHash("only_local.jpg", 4000, "ddd"),  # Only local
        ]

        remote_files = [
            FileHash("match1.jpg", 1000, "aaa"),
            FileHash("match2.jpg", 2000, "DIFFERENT"),
            FileHash("mismatch.jpg", 2999),
            FileHash("only_remote.jpg", 5000, "eee"),  # Only remote
        ]

        result = verifier.compare_hashes(local_files, remote_files)

        assert sorted(result.matched_files) == ["match1.jpg", "match2.jpg"]
        assert [m.path for m in result.mismatched_files] == ["mismatch.jpg"]
        assert result.mismatched_files[0].mismatch_type == "size"
        assert [f.path for f in result.missing_remote] == ["only_local.jpg"]
        assert [f.path for f in result.missing_local] == ["only_remote.jpg"]
        assert result.has_issues is True
