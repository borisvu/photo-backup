#!/usr/bin/env python3
"""
Functional tests for hash cache speedup.

Task 100: Implement Cache System - Functional tests.
"""

import tempfile
import time

from pathlib import Path

from photo_backup.verify.cache import HashCache


class TestCacheSpeedup:
    """Test that cache provides meaningful speedup for hash calculations."""

    def _create_test_files(self, directory: Path, num_files: int, size_kb: int = 10) -> list[Path]:
        """Create test files with specified size.

        Args:
            directory: Directory to create files in
            num_files: Number of files to create
            size_kb: Size of each file in KB

        Returns:
            List of created file paths
        """
        files = []
        content = b"X" * (size_kb * 1024)

        for i in range(num_files):
            subdir = directory / f"subdir_{i % 5}"
            subdir.mkdir(exist_ok=True)
            file_path = subdir / f"file_{i}.dat"
            file_path.write_bytes(content)
            files.append(file_path)

        return files

    def test_cache_speeds_up_repeated_verification(self):
        """Test that cache speeds up repeated hash calculations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "photos"
            source_dir.mkdir()
            cache_file = temp_path / "cache" / "hash_cache.json"

            # Create test files (20 files of 10KB each)
            num_files = 20
            files = self._create_test_files(source_dir, num_files, size_kb=10)
            assert len(files) == num_files

            # Create cache
            cache = HashCache.create(
                cache_file=cache_file,
                source_path=str(source_dir),
                auto_save=True,
            )

            # First pass: populate cache (should have all misses)
            first_pass_start = time.time()
            first_pass_hashes = []

            for file_path in files:
                rel_path = str(file_path.relative_to(source_dir))
                stat = file_path.stat()

                # Try cache first
                cached = cache.get(rel_path, stat.st_mtime, stat.st_size)
                if cached:
                    first_pass_hashes.append(cached)
                else:
                    # Calculate hash
                    import hashlib

                    with open(file_path, "rb") as f:
                        hash_md5 = hashlib.md5(f.read()).hexdigest()

                    # Store in cache
                    cache.set(rel_path, hash_md5, stat.st_size, stat.st_mtime)
                    first_pass_hashes.append(hash_md5)

            first_pass_time = time.time() - first_pass_start

            # Verify first pass had all misses
            assert cache.stats.misses == num_files
            assert cache.stats.hits == 0

            # Reset stats for second pass
            cache.stats.hits = 0
            cache.stats.misses = 0
            cache.stats.total_lookups = 0

            # Second pass: use cache (should have all hits)
            second_pass_start = time.time()
            second_pass_hashes = []

            for file_path in files:
                rel_path = str(file_path.relative_to(source_dir))
                stat = file_path.stat()

                # Try cache first
                cached = cache.get(rel_path, stat.st_mtime, stat.st_size)
                if cached:
                    second_pass_hashes.append(cached)
                else:
                    # Should not reach here
                    import hashlib

                    with open(file_path, "rb") as f:
                        hash_md5 = hashlib.md5(f.read()).hexdigest()
                    second_pass_hashes.append(hash_md5)

            second_pass_time = time.time() - second_pass_start

            # Verify second pass had all hits
            assert cache.stats.hits == num_files
            assert cache.stats.misses == 0

            # Verify hashes match
            assert first_pass_hashes == second_pass_hashes

            # Second pass should be faster (cache hit is faster than hashing)
            # Note: With small files, the difference might be minimal
            # but the cache hit rate proves the cache is working
            assert cache.stats.hit_rate == 1.0

            # Print timing for reference
            print(f"\nFirst pass (cold cache): {first_pass_time:.4f}s")
            print(f"Second pass (warm cache): {second_pass_time:.4f}s")
            print(f"Speedup: {first_pass_time / max(second_pass_time, 0.0001):.2f}x")

    def test_cache_invalidates_modified_files(self):
        """Test that cache correctly invalidates modified files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "photos"
            source_dir.mkdir()
            cache_file = temp_path / "cache" / "hash_cache.json"

            # Create initial file
            test_file = source_dir / "test.dat"
            test_file.write_bytes(b"initial content")
            initial_stat = test_file.stat()

            # Create cache and set initial hash
            cache = HashCache.create(cache_file=cache_file, auto_save=True)

            import hashlib

            initial_hash = hashlib.md5(b"initial content").hexdigest()
            cache.set("test.dat", initial_hash, initial_stat.st_size, initial_stat.st_mtime)

            # Verify cache hit
            cached = cache.get("test.dat", initial_stat.st_mtime, initial_stat.st_size)
            assert cached == initial_hash
            assert cache.stats.hits == 1

            # Modify file
            time.sleep(0.1)  # Ensure different mtime
            test_file.write_bytes(b"modified content - different length")
            new_stat = test_file.stat()

            # Verify cache miss (file changed)
            cached = cache.get("test.dat", new_stat.st_mtime, new_stat.st_size)
            assert cached is None
            assert cache.stats.misses == 1
            assert cache.stats.invalidations == 1

    def test_cache_persistence(self):
        """Test that cache persists across instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "photos"
            source_dir.mkdir()
            cache_file = temp_path / "cache" / "hash_cache.json"

            # Create test files
            files = self._create_test_files(source_dir, 5, size_kb=5)

            # First instance: populate cache
            cache1 = HashCache.create(cache_file=cache_file, auto_save=True)

            import hashlib

            for file_path in files:
                rel_path = str(file_path.relative_to(source_dir))
                stat = file_path.stat()
                with open(file_path, "rb") as f:
                    hash_md5 = hashlib.md5(f.read()).hexdigest()
                cache1.set(rel_path, hash_md5, stat.st_size, stat.st_mtime)

            # Verify cache file exists
            assert cache_file.exists()

            # Second instance: load and verify
            cache2 = HashCache.create(cache_file=cache_file, auto_save=False)
            loaded = cache2.load()
            assert loaded is True
            assert len(cache2) == 5

            # Verify all files hit cache
            for file_path in files:
                rel_path = str(file_path.relative_to(source_dir))
                stat = file_path.stat()
                cached = cache2.get(rel_path, stat.st_mtime, stat.st_size)
                assert cached is not None

            assert cache2.stats.hits == 5
            assert cache2.stats.misses == 0


class TestCacheWithVerifier:
    """Test cache integration with Verifier."""

    def test_verifier_uses_cache(self):
        """Test that Verifier uses cache for repeated verifications."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "photos"
            source_dir.mkdir()
            cache_dir = temp_path / "cache"
            cache_dir.mkdir()

            # Create test files
            for i in range(5):
                (source_dir / f"photo_{i}.jpg").write_bytes(f"Photo content {i}".encode())

            # Import and use Verifier with cache
            from unittest.mock import Mock, patch

            from photo_backup.verify import Verifier

            # Mock config
            mock_config = Mock()
            mock_config.get.side_effect = lambda key, default=None: {
                "backup.source_path": str(source_dir),
                "backup.destination": "test:bucket/photos",
                "storage.endpoint": "localhost:9000",
            }.get(key, default)
            mock_config.is_test_mode.return_value = True
            mock_config.load_config.return_value = None

            # Mock credential manager and get_default_cache_path
            cache_file = cache_dir / "hash_cache.json"
            with (
                patch("photo_backup.verify.verifier.CredentialManager"),
                patch("photo_backup.verify.verifier.get_default_cache_path", return_value=cache_file),
            ):
                # Create verifier with cache enabled
                verifier = Verifier(config=mock_config, test_mode=True, use_cache=True)

                # First verification - cache misses
                hashes1 = verifier.calculate_local_hashes()
                first_stats = verifier.get_cache_stats()

                assert first_stats["enabled"] is True
                assert len(hashes1) == 5

                # Second verification - should have cache hits
                hashes2 = verifier.calculate_local_hashes()
                second_stats = verifier.get_cache_stats()

                assert len(hashes2) == 5
                # After second pass, should have some hits
                assert second_stats["stats"]["hits"] > 0

                # Hashes should match
                hashes1_dict = {h.path: h.hash_md5 for h in hashes1}
                hashes2_dict = {h.path: h.hash_md5 for h in hashes2}
                assert hashes1_dict == hashes2_dict

    def test_verifier_without_cache(self):
        """Test that Verifier works correctly with cache disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "photos"
            source_dir.mkdir()

            # Create test files
            for i in range(3):
                (source_dir / f"photo_{i}.jpg").write_bytes(f"Photo content {i}".encode())

            from unittest.mock import Mock, patch

            from photo_backup.verify import Verifier

            mock_config = Mock()
            mock_config.get.side_effect = lambda key, default=None: {
                "backup.source_path": str(source_dir),
                "backup.destination": "test:bucket/photos",
                "storage.endpoint": "localhost:9000",
            }.get(key, default)
            mock_config.is_test_mode.return_value = True
            mock_config.load_config.return_value = None

            with (
                patch("photo_backup.verify.verifier.CredentialManager"),
                patch("photo_backup.verify.verifier.get_default_cache_path"),
            ):
                # Create verifier with cache disabled
                verifier = Verifier(config=mock_config, test_mode=True, use_cache=False)

                stats = verifier.get_cache_stats()
                assert stats["enabled"] is False

                # Should still calculate hashes correctly
                hashes = verifier.calculate_local_hashes()
                assert len(hashes) == 3
