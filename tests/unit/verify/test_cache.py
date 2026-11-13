#!/usr/bin/env python3
"""
Unit tests for hash cache functionality.

Implement Cache System - Unit tests.
"""

import json
import tempfile
import time

from pathlib import Path

from photo_backup.verify.cache import (
    CacheEntry,
    CacheStats,
    HashCache,
    get_default_cache_path,
)


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            path="photo1.jpg",
            hash_md5="abc123",
            size=1000,
            mtime=1234567890.0,
            cached_at=time.time(),
        )

        assert entry.path == "photo1.jpg"
        assert entry.hash_md5 == "abc123"
        assert entry.size == 1000
        assert entry.mtime == 1234567890.0
        assert entry.verified_at is None

    def test_cache_entry_is_valid(self):
        """Test cache entry validation."""
        entry = CacheEntry(
            path="photo1.jpg",
            hash_md5="abc123",
            size=1000,
            mtime=1234567890.0,
            cached_at=time.time(),
        )

        # Same mtime and size - should be valid
        assert entry.is_valid(1234567890.0, 1000) is True

        # Different mtime - should be invalid
        assert entry.is_valid(1234567891.0, 1000) is False

        # Different size - should be invalid
        assert entry.is_valid(1234567890.0, 2000) is False

        # Both different - should be invalid
        assert entry.is_valid(1234567891.0, 2000) is False

    def test_cache_entry_to_dict(self):
        """Test cache entry serialization."""
        now = time.time()
        entry = CacheEntry(
            path="photo1.jpg",
            hash_md5="abc123",
            size=1000,
            mtime=1234567890.0,
            cached_at=now,
            verified_at=now + 100,
        )

        data = entry.to_dict()
        assert data["path"] == "photo1.jpg"
        assert data["hash_md5"] == "abc123"
        assert data["size"] == 1000
        assert data["mtime"] == 1234567890.0
        assert data["cached_at"] == now
        assert data["verified_at"] == now + 100

    def test_cache_entry_from_dict(self):
        """Test cache entry deserialization."""
        data = {
            "path": "photo1.jpg",
            "hash_md5": "abc123",
            "size": 1000,
            "mtime": 1234567890.0,
            "cached_at": time.time(),
            "verified_at": None,
        }

        entry = CacheEntry.from_dict(data)
        assert entry.path == "photo1.jpg"
        assert entry.hash_md5 == "abc123"
        assert entry.size == 1000


class TestCacheStats:
    """Test CacheStats dataclass."""

    def test_cache_stats_initial(self):
        """Test initial cache stats."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.invalidations == 0
        assert stats.total_lookups == 0
        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate(self):
        """Test cache hit rate calculation."""
        stats = CacheStats(hits=7, misses=3, total_lookups=10)
        assert stats.hit_rate == 0.7

    def test_cache_stats_summary(self):
        """Test cache stats summary."""
        stats = CacheStats(hits=7, misses=3, invalidations=2, total_lookups=10)
        summary = stats.get_summary()
        assert "7 hits" in summary
        assert "3 misses" in summary
        assert "2 invalidations" in summary
        assert "70.0%" in summary


class TestHashCache:
    """Test HashCache class."""

    def test_hash_cache_create(self):
        """Test creating a hash cache."""
        cache = HashCache.create(source_path="/tmp/photos")
        assert cache.source_path == "/tmp/photos"
        assert len(cache) == 0

    def test_hash_cache_set_and_get(self):
        """Test setting and getting cache entries."""
        cache = HashCache.create(auto_save=False)

        # Set a cache entry
        cache.set(
            file_path="photo1.jpg",
            hash_md5="abc123",
            size=1000,
            mtime=1234567890.0,
        )

        assert len(cache) == 1
        assert "photo1.jpg" in cache

        # Get with matching metadata
        result = cache.get("photo1.jpg", 1234567890.0, 1000)
        assert result == "abc123"
        assert cache.stats.hits == 1

    def test_hash_cache_get_miss(self):
        """Test cache miss on get."""
        cache = HashCache.create(auto_save=False)

        # Miss - entry doesn't exist
        result = cache.get("nonexistent.jpg", 0.0, 0)
        assert result is None
        assert cache.stats.misses == 1

    def test_hash_cache_get_invalidated(self):
        """Test cache miss due to invalidation."""
        cache = HashCache.create(auto_save=False)

        cache.set(
            file_path="photo1.jpg",
            hash_md5="abc123",
            size=1000,
            mtime=1234567890.0,
        )

        # Get with different mtime - should invalidate
        result = cache.get("photo1.jpg", 1234567891.0, 1000)
        assert result is None
        assert cache.stats.misses == 1
        assert cache.stats.invalidations == 1
        assert "photo1.jpg" not in cache

    def test_hash_cache_invalidate(self):
        """Test manual invalidation."""
        cache = HashCache.create(auto_save=False)

        cache.set("photo1.jpg", "abc123", 1000, 1234567890.0)
        assert len(cache) == 1

        result = cache.invalidate("photo1.jpg")
        assert result is True
        assert len(cache) == 0
        assert cache.stats.invalidations == 1

        # Invalidating non-existent entry returns False
        result = cache.invalidate("nonexistent.jpg")
        assert result is False

    def test_hash_cache_invalidate_all(self):
        """Test invalidating all entries."""
        cache = HashCache.create(auto_save=False)

        cache.set("photo1.jpg", "abc123", 1000, 1234567890.0)
        cache.set("photo2.jpg", "def456", 2000, 1234567891.0)
        assert len(cache) == 2

        count = cache.invalidate_all()
        assert count == 2
        assert len(cache) == 0
        assert cache.stats.invalidations == 2

    def test_hash_cache_save_and_load(self):
        """Test saving and loading cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "cache.json"

            # Create and populate cache
            cache1 = HashCache.create(cache_file=cache_path, auto_save=False)
            cache1.set("photo1.jpg", "abc123", 1000, 1234567890.0)
            cache1.set("photo2.jpg", "def456", 2000, 1234567891.0)

            # Save
            result = cache1.save()
            assert result is True
            assert cache_path.exists()

            # Load into new cache
            cache2 = HashCache.create(cache_file=cache_path, auto_save=False)
            result = cache2.load()
            assert result is True
            assert len(cache2) == 2
            assert cache2.get("photo1.jpg", 1234567890.0, 1000) == "abc123"
            assert cache2.get("photo2.jpg", 1234567891.0, 2000) == "def456"

    def test_hash_cache_load_nonexistent(self):
        """Test loading non-existent cache file."""
        cache = HashCache.create(cache_file="/nonexistent/path.json")
        result = cache.load()
        assert result is False

    def test_hash_cache_load_invalid_json(self):
        """Test loading invalid JSON cache file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json {{{")
            cache_path = f.name

        try:
            cache = HashCache.create(cache_file=cache_path)
            result = cache.load()
            assert result is False
        finally:
            Path(cache_path).unlink()

    def test_hash_cache_validate(self):
        """Test cache validation against filesystem."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "existing.jpg").write_text("content")
            stat = (temp_path / "existing.jpg").stat()

            # Create cache with entries
            cache = HashCache.create(auto_save=False)
            cache.set("existing.jpg", "abc123", stat.st_size, stat.st_mtime)
            cache.set("deleted.jpg", "def456", 1000, 1234567890.0)

            # Validate
            valid, removed = cache.validate(temp_path)
            assert valid == 1
            assert removed == 1
            assert "existing.jpg" in cache
            assert "deleted.jpg" not in cache

    def test_hash_cache_mark_verified(self):
        """Test marking a file as verified."""
        cache = HashCache.create(auto_save=False)
        cache.set("photo1.jpg", "abc123", 1000, 1234567890.0)

        # Entry should not have verified_at initially
        assert cache.entries["photo1.jpg"].verified_at is None

        cache.mark_verified("photo1.jpg")

        # Entry should now have verified_at
        assert cache.entries["photo1.jpg"].verified_at is not None

    def test_hash_cache_get_info(self):
        """Test getting cache info."""
        cache = HashCache.create(source_path="/tmp/photos", auto_save=False)
        cache.set("photo1.jpg", "abc123", 1000, 1234567890.0)

        # Simulate some cache usage
        cache.get("photo1.jpg", 1234567890.0, 1000)  # hit
        cache.get("nonexistent.jpg", 0.0, 0)  # miss

        info = cache.get_info()
        assert info["source_path"] == "/tmp/photos"
        assert info["entry_count"] == 1
        assert info["stats"]["hits"] == 1
        assert info["stats"]["misses"] == 1

    def test_hash_cache_auto_save(self):
        """Test auto-save functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "cache.json"

            # Create cache with auto-save
            cache = HashCache.create(cache_file=cache_path, auto_save=True)

            # Setting should trigger save
            cache.set("photo1.jpg", "abc123", 1000, 1234567890.0)
            assert cache_path.exists()

            # Verify file content
            with open(cache_path) as f:
                data = json.load(f)
            assert len(data["entries"]) == 1


class TestGetDefaultCachePath:
    """Test get_default_cache_path function."""

    def test_production_mode(self):
        """Test default cache path in production mode."""
        path = get_default_cache_path(test_mode=False)
        assert ".photo-backup" in str(path)
        assert "test" not in str(path)
        assert path.name == "hash_cache.json"

    def test_test_mode(self):
        """Test default cache path in test mode."""
        path = get_default_cache_path(test_mode=True)
        assert ".photo-backup" in str(path)
        assert "test" in str(path)
        assert path.name == "hash_cache.json"


class TestHashCacheIntegration:
    """Integration tests for hash cache with filesystem."""

    def test_full_workflow(self):
        """Test complete cache workflow with files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cache_path = temp_path / "cache" / "hash_cache.json"

            # Create test files
            (temp_path / "photos").mkdir()
            photo1 = temp_path / "photos" / "photo1.jpg"
            photo1.write_text("photo content 1")
            stat1 = photo1.stat()

            # Create cache
            cache = HashCache.create(
                cache_file=cache_path,
                source_path=str(temp_path / "photos"),
                auto_save=True,
            )

            # First access - miss
            result = cache.get("photo1.jpg", stat1.st_mtime, stat1.st_size)
            assert result is None
            assert cache.stats.misses == 1

            # Set hash
            cache.set("photo1.jpg", "calculated_hash", stat1.st_size, stat1.st_mtime)

            # Second access - hit
            result = cache.get("photo1.jpg", stat1.st_mtime, stat1.st_size)
            assert result == "calculated_hash"
            assert cache.stats.hits == 1

            # Modify file
            photo1.write_text("modified content")
            new_stat = photo1.stat()

            # Third access - miss (file changed)
            result = cache.get("photo1.jpg", new_stat.st_mtime, new_stat.st_size)
            assert result is None
            assert cache.stats.misses == 2
            assert cache.stats.invalidations == 1

            # Verify cache was saved
            assert cache_path.exists()

            # Load into new cache instance
            new_cache = HashCache.create(cache_file=cache_path)
            new_cache.load()

            # Entry should have been invalidated and removed
            assert "photo1.jpg" not in new_cache
