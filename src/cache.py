"""Scan result caching with version management."""
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from .models import ModInfo
from . import __version__

logger = logging.getLogger(__name__)

CACHE_VERSION = "3.0.0"  # Cache format version


@dataclass
class CacheMetadata:
    """Metadata for cache validation."""

    cache_version: str
    app_version: str
    file_hash: str
    file_size: int
    file_mtime: float


class ScanCache:
    """Cache for mod scan results with version management."""

    def __init__(self, cache_dir: Path):
        """Initialize cache manager.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = cache_dir / f"v{CACHE_VERSION}"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "metadata.json"
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load cache metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    self.metadata: Dict[str, CacheMetadata] = {}
                    data = json.load(f)
                    for file_path, meta in data.items():
                        self.metadata[file_path] = CacheMetadata(**meta)
            except Exception as e:
                logger.warning(f"Failed to load cache metadata: {e}")
                self.metadata = {}
        else:
            self.metadata = {}

    def _save_metadata(self) -> None:
        """Save cache metadata."""
        try:
            data = {
                file_path: {
                    "cache_version": meta.cache_version,
                    "app_version": meta.app_version,
                    "file_hash": meta.file_hash,
                    "file_size": meta.file_size,
                    "file_mtime": meta.file_mtime,
                }
                for file_path, meta in self.metadata.items()
            }
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")

    def _compute_file_hash(self, jar_path: Path) -> str:
        """Compute quick hash based on file stats.

        Uses file size and modification time for fast comparison.
        For paranoid mode, could use actual content hash.

        Args:
            jar_path: Path to JAR file

        Returns:
            Hash string
        """
        try:
            stat = jar_path.stat()
            # Quick hash: combine size and mtime
            hash_input = f"{stat.st_size}:{stat.st_mtime_ns}".encode()
            return hashlib.sha256(hash_input).hexdigest()[:16]
        except Exception:
            return ""

    def _get_cache_key(self, jar_path: Path) -> str:
        """Get cache key for file.

        Args:
            jar_path: Path to JAR file

        Returns:
            Normalized path string for caching
        """
        return str(jar_path.resolve())

    def _get_cache_file(self, cache_key: str) -> Path:
        """Get cache file path for given key.

        Args:
            cache_key: Cache key

        Returns:
            Path to cache file
        """
        # Hash the key to get a safe filename
        key_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key_hash}.json"

    def get(self, jar_path: Path) -> Optional[ModInfo]:
        """Get cached mod info if valid.

        Args:
            jar_path: Path to JAR file

        Returns:
            Cached ModInfo if valid, None otherwise
        """
        if not jar_path.exists():
            return None

        cache_key = self._get_cache_key(jar_path)

        # Check if we have metadata for this file
        if cache_key not in self.metadata:
            return None

        meta = self.metadata[cache_key]

        # Validate cache version
        if meta.cache_version != CACHE_VERSION:
            logger.debug(
                f"Cache version mismatch for {jar_path.name}: {meta.cache_version} != {CACHE_VERSION}"
            )
            return None

        # Validate file hasn't changed
        current_hash = self._compute_file_hash(jar_path)
        if current_hash != meta.file_hash:
            logger.debug(f"File changed: {jar_path.name}")
            return None

        # Load cached data
        cache_file = self._get_cache_file(cache_key)
        if not cache_file.exists():
            logger.debug(f"Cache file missing: {jar_path.name}")
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Reconstruct ModInfo from dict
                return ModInfo(
                    name=data["name"],
                    loader=data["loader"],
                    version=data["version"],
                    filename=data["filename"],
                    mod_id=data.get("mod_id"),
                    dependencies=data.get("dependencies", []),
                    author=data.get("author"),
                    description=data.get("description"),
                    mc_versions=data.get("mc_versions", []),
                    disabled=data.get("disabled", False),
                )
        except Exception as e:
            logger.warning(f"Failed to load cache for {jar_path.name}: {e}")
            return None

    def set(self, jar_path: Path, mod_info: ModInfo) -> None:
        """Cache mod info.

        Args:
            jar_path: Path to JAR file
            mod_info: ModInfo to cache
        """
        if not jar_path.exists():
            return

        cache_key = self._get_cache_key(jar_path)
        cache_file = self._get_cache_file(cache_key)

        try:
            # Save mod info
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(mod_info.to_dict(), f, indent=2)

            # Update metadata
            stat = jar_path.stat()
            self.metadata[cache_key] = CacheMetadata(
                cache_version=CACHE_VERSION,
                app_version=__version__,
                file_hash=self._compute_file_hash(jar_path),
                file_size=stat.st_size,
                file_mtime=stat.st_mtime,
            )
            self._save_metadata()

            logger.debug(f"Cached: {jar_path.name}")
        except Exception as e:
            logger.warning(f"Failed to cache {jar_path.name}: {e}")

    def clear(self) -> None:
        """Clear all cached data."""
        try:
            # Remove all cache files
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()

            # Clear metadata
            self.metadata = {}
            if self.metadata_file.exists():
                self.metadata_file.unlink()

            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def invalidate(self, jar_path: Path) -> None:
        """Invalidate cache for specific file.

        Args:
            jar_path: Path to JAR file
        """
        cache_key = self._get_cache_key(jar_path)

        if cache_key in self.metadata:
            # Remove cache file
            cache_file = self._get_cache_file(cache_key)
            if cache_file.exists():
                cache_file.unlink()

            # Remove metadata
            del self.metadata[cache_key]
            self._save_metadata()

            logger.debug(f"Invalidated cache: {jar_path.name}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_entries = len(self.metadata)
        total_size = sum(
            self._get_cache_file(key).stat().st_size
            for key in self.metadata.keys()
            if self._get_cache_file(key).exists()
        )

        return {
            "cache_version": CACHE_VERSION,
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(self.cache_dir),
        }
