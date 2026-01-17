"""
Hash cache for verification speedup.

Implement Cache System.

This module provides a caching mechanism for file hashes to speed up
repeated verification runs by avoiding re-hashing unchanged files.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from pathlib import Path


@dataclass
class CacheEntry:
    """Represents a cached hash entry for a file."""

    path: str
    hash_md5: str
    size: int
    mtime: float  # File modification time
    cached_at: float  # When this entry was cached
    verified_at: float | None = None  # Last time this hash was verified against remote

    def is_valid(self, current_mtime: float, current_size: int) -> bool:
        """Check if this cache entry is still valid.

        A cache entry is valid if:
        - The file modification time hasn't changed
        - The file size hasn't changed

        Args:
            current_mtime: Current modification time of the file
            current_size: Current size of the file

        Returns:
            True if the cache entry is still valid
        """
        return self.mtime == current_mtime and self.size == current_size

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create entry from dictionary."""
        return cls(
            path=data["path"],
            hash_md5=data["hash_md5"],
            size=data["size"],
            mtime=data["mtime"],
            cached_at=data["cached_at"],
            verified_at=data.get("verified_at"),
        )


@dataclass
class CacheMetadata:
    """Metadata for the hash cache."""

    version: str = "1.0"
    created_at: str = ""
    last_modified: str = ""
    source_path: str = ""
    entry_count: int = 0

    def __post_init__(self) -> None:
        """Initialize timestamps if not set."""
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.last_modified:
            self.last_modified = now


@dataclass
class CacheStats:
    """Statistics about cache usage."""

    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    total_lookups: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_lookups == 0:
            return 0.0
        return self.hits / self.total_lookups

    def get_summary(self) -> str:
        """Get human-readable summary."""
        return (
            f"Cache Stats: {self.hits} hits, {self.misses} misses, "
            f"{self.invalidations} invalidations, {self.hit_rate:.1%} hit rate"
        )


@dataclass
class HashCache:
    """Cache for file hashes to speed up verification.

    Hash cache implementation.

    The cache stores MD5 hashes keyed by relative file path, along with
    file metadata (size, mtime) to detect when files have changed.
    """

    cache_file: Path | None = None
    source_path: str = ""
    entries: dict[str, CacheEntry] = field(default_factory=dict)
    metadata: CacheMetadata = field(default_factory=CacheMetadata)
    stats: CacheStats = field(default_factory=CacheStats)
    auto_save: bool = True
    _dirty: bool = False
    _logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))

    def __post_init__(self) -> None:
        """Initialize the cache."""
        self._logger = logging.getLogger(__name__)
        if self.source_path:
            self.metadata.source_path = self.source_path

    @classmethod
    def create(
        cls,
        cache_file: str | Path | None = None,
        source_path: str = "",
        auto_save: bool = True,
    ) -> "HashCache":
        """Create a new HashCache instance.

        Args:
            cache_file: Path to the cache file
            source_path: Path to the source directory being cached
            auto_save: Whether to auto-save on updates

        Returns:
            New HashCache instance
        """
        cache = cls(
            cache_file=Path(cache_file) if cache_file else None,
            source_path=source_path,
            auto_save=auto_save,
        )
        return cache

    def get(self, file_path: str, current_mtime: float, current_size: int) -> str | None:
        """Get cached hash for a file if valid.

        Args:
            file_path: Relative path to the file
            current_mtime: Current modification time of the file
            current_size: Current size of the file

        Returns:
            The cached MD5 hash if valid, None otherwise
        """
        self.stats.total_lookups += 1

        entry = self.entries.get(file_path)
        if entry is None:
            self.stats.misses += 1
            self._logger.debug(f"Cache miss (not found): {file_path}")
            return None

        if entry.is_valid(current_mtime, current_size):
            self.stats.hits += 1
            self._logger.debug(f"Cache hit: {file_path}")
            return entry.hash_md5
        else:
            self.stats.misses += 1
            self.stats.invalidations += 1
            self._logger.debug(f"Cache miss (invalidated): {file_path}")
            # Remove invalid entry
            del self.entries[file_path]
            self._dirty = True

            # Save if auto_save enabled
            if self.auto_save and self.cache_file:
                self.save()

            return None

    def set(
        self,
        file_path: str,
        hash_md5: str,
        size: int,
        mtime: float,
    ) -> None:
        """Set cached hash for a file.

        Args:
            file_path: Relative path to the file
            hash_md5: MD5 hash of the file
            size: File size in bytes
            mtime: File modification time
        """
        entry = CacheEntry(
            path=file_path,
            hash_md5=hash_md5,
            size=size,
            mtime=mtime,
            cached_at=time.time(),
        )
        self.entries[file_path] = entry
        self._dirty = True
        self._logger.debug(f"Cache set: {file_path}")

        if self.auto_save and self.cache_file:
            self.save()

    def invalidate(self, file_path: str) -> bool:
        """Invalidate a cached entry.

        Args:
            file_path: Relative path to the file

        Returns:
            True if an entry was removed, False if not found
        """
        if file_path in self.entries:
            del self.entries[file_path]
            self.stats.invalidations += 1
            self._dirty = True
            self._logger.debug(f"Cache invalidated: {file_path}")

            if self.auto_save and self.cache_file:
                self.save()
            return True
        return False

    def invalidate_all(self) -> int:
        """Invalidate all cached entries.

        Returns:
            Number of entries invalidated
        """
        count = len(self.entries)
        self.entries.clear()
        self.stats.invalidations += count
        self._dirty = True
        self._logger.info(f"Cache cleared: {count} entries invalidated")

        if self.auto_save and self.cache_file:
            self.save()
        return count

    def mark_verified(self, file_path: str) -> None:
        """Mark a file as verified against remote.

        Args:
            file_path: Relative path to the file
        """
        if file_path in self.entries:
            self.entries[file_path].verified_at = time.time()
            self._dirty = True

    def load(self, cache_file: str | Path | None = None) -> bool:
        """Load cache from file.

        Args:
            cache_file: Path to cache file (uses self.cache_file if None)

        Returns:
            True if loaded successfully, False otherwise
        """
        if cache_file:
            self.cache_file = Path(cache_file)

        if not self.cache_file or not self.cache_file.exists():
            self._logger.debug("No cache file to load")
            return False

        try:
            with open(self.cache_file) as f:
                data = json.load(f)

            # Load metadata
            if "metadata" in data:
                meta = data["metadata"]
                self.metadata = CacheMetadata(
                    version=meta.get("version", "1.0"),
                    created_at=meta.get("created_at", ""),
                    last_modified=meta.get("last_modified", ""),
                    source_path=meta.get("source_path", ""),
                    entry_count=meta.get("entry_count", 0),
                )

            # Load entries
            self.entries.clear()
            for entry_data in data.get("entries", []):
                entry = CacheEntry.from_dict(entry_data)
                self.entries[entry.path] = entry

            self._dirty = False
            self._logger.info(f"Loaded cache with {len(self.entries)} entries from {self.cache_file}")
            return True

        except json.JSONDecodeError as e:
            self._logger.warning(f"Failed to parse cache file: {e}")
            return False
        except Exception as e:
            self._logger.warning(f"Failed to load cache: {e}")
            return False

    def save(self, cache_file: str | Path | None = None) -> bool:
        """Save cache to file.

        Args:
            cache_file: Path to cache file (uses self.cache_file if None)

        Returns:
            True if saved successfully, False otherwise
        """
        if cache_file:
            self.cache_file = Path(cache_file)

        if not self.cache_file:
            self._logger.debug("No cache file specified")
            return False

        try:
            # Ensure parent directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)

            # Update metadata
            self.metadata.last_modified = datetime.now().isoformat()
            self.metadata.entry_count = len(self.entries)

            # Build cache data
            data = {
                "metadata": {
                    "version": self.metadata.version,
                    "created_at": self.metadata.created_at,
                    "last_modified": self.metadata.last_modified,
                    "source_path": self.metadata.source_path,
                    "entry_count": self.metadata.entry_count,
                },
                "entries": [entry.to_dict() for entry in self.entries.values()],
            }

            with open(self.cache_file, "w") as f:
                json.dump(data, f, indent=2)

            self._dirty = False
            self._logger.debug(f"Saved cache with {len(self.entries)} entries to {self.cache_file}")
            return True

        except Exception as e:
            self._logger.warning(f"Failed to save cache: {e}")
            return False

    def validate(self, source_path: str | Path) -> tuple[int, int]:
        """Validate cache entries against the filesystem.

        Removes entries for files that no longer exist or have changed.

        Args:
            source_path: Base path to validate against

        Returns:
            Tuple of (valid_count, removed_count)
        """
        source_path = Path(source_path)
        to_remove: list[str] = []
        valid_count = 0

        for file_path, entry in self.entries.items():
            full_path = source_path / file_path

            if not full_path.exists():
                to_remove.append(file_path)
                continue

            try:
                stat = full_path.stat()
                if not entry.is_valid(stat.st_mtime, stat.st_size):
                    to_remove.append(file_path)
                else:
                    valid_count += 1
            except OSError:
                to_remove.append(file_path)

        # Remove invalid entries
        for file_path in to_remove:
            del self.entries[file_path]
            self.stats.invalidations += 1

        if to_remove:
            self._dirty = True
            if self.auto_save and self.cache_file:
                self.save()

        self._logger.info(f"Cache validation: {valid_count} valid, {len(to_remove)} removed")
        return valid_count, len(to_remove)

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats object with usage statistics
        """
        return self.stats

    def get_info(self) -> dict[str, Any]:
        """Get cache information.

        Returns:
            Dictionary with cache metadata and statistics
        """
        return {
            "cache_file": str(self.cache_file) if self.cache_file else None,
            "source_path": self.source_path,
            "entry_count": len(self.entries),
            "metadata": {
                "version": self.metadata.version,
                "created_at": self.metadata.created_at,
                "last_modified": self.metadata.last_modified,
            },
            "stats": {
                "hits": self.stats.hits,
                "misses": self.stats.misses,
                "invalidations": self.stats.invalidations,
                "hit_rate": f"{self.stats.hit_rate:.1%}",
            },
            "dirty": self._dirty,
        }

    def __len__(self) -> int:
        """Return number of cached entries."""
        return len(self.entries)

    def __contains__(self, file_path: str) -> bool:
        """Check if a file path is in the cache."""
        return file_path in self.entries


def get_default_cache_path(test_mode: bool = False, state_directory: str | None = None) -> Path:
    """Get the default cache file path.

    Args:
        test_mode: Whether in test mode
        state_directory: Optional state directory path from config. If provided, cache
                        will be stored in a 'cache' subdirectory of this path.

    Returns:
        Path to the default cache file
    """
    if state_directory:
        # Use the configured state directory
        import os

        expanded_dir = os.path.expanduser(state_directory)
        base_dir = Path(expanded_dir)
        # Create cache subdirectory in state directory
        cache_dir = base_dir / "cache"
        return cache_dir / "hash_cache.json"
    else:
        # Fallback to old hardcoded path for backward compatibility
        base_dir = Path.home() / ".photo-backup"
        if test_mode:
            base_dir = base_dir / "test"
        return base_dir / "cache" / "hash_cache.json"
