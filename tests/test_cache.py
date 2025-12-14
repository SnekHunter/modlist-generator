"""Tests for cache module."""

import pytest
from pathlib import Path
import tempfile
import json

from src.cache import ScanCache, CacheMetadata, CACHE_VERSION
from src.models import ModInfo


class TestCacheMetadata:
    """Test CacheMetadata dataclass."""

    def test_create_metadata(self):
        """Test creating cache metadata."""
        meta = CacheMetadata(
            cache_version="3.0.0",
            app_version="3.0.0",
            file_hash="abc123",
            file_size=1024,
            file_mtime=12345.0,
        )
        
        assert meta.cache_version == "3.0.0"
        assert meta.file_hash == "abc123"
        assert meta.file_size == 1024


class TestScanCache:
    """Test ScanCache class."""

    def test_cache_init(self, tmp_path):
        """Test cache initialization creates directory."""
        cache = ScanCache(tmp_path)
        
        assert cache.cache_dir.exists()
        assert f"v{CACHE_VERSION}" in str(cache.cache_dir)

    def test_cache_put_and_get(self, tmp_path):
        """Test storing and retrieving from cache."""
        cache = ScanCache(tmp_path)
        
        # Create a test JAR file
        jar_path = tmp_path / "test.jar"
        jar_path.write_bytes(b"fake jar content")
        
        # Create a ModInfo
        mod_info = ModInfo(
            name="Test Mod",
            loader="fabric",
            version="1.0.0",
            filename="test.jar",
        )
        
        # Store in cache
        cache.set(jar_path, mod_info)
        
        # Retrieve from cache
        cached = cache.get(jar_path)
        
        assert cached is not None
        assert cached.name == "Test Mod"
        assert cached.loader == "fabric"

    def test_cache_miss_nonexistent(self, tmp_path):
        """Test cache miss for non-existent file."""
        cache = ScanCache(tmp_path)
        
        jar_path = tmp_path / "nonexistent.jar"
        
        cached = cache.get(jar_path)
        
        assert cached is None

    def test_cache_invalidation_on_modify(self, tmp_path):
        """Test cache is invalidated when file is modified."""
        cache = ScanCache(tmp_path)
        
        jar_path = tmp_path / "test.jar"
        jar_path.write_bytes(b"original content")
        
        mod_info = ModInfo(
            name="Test Mod",
            loader="fabric",
            version="1.0.0",
            filename="test.jar",
        )
        
        cache.set(jar_path, mod_info)
        
        # Modify file
        jar_path.write_bytes(b"modified content")
        
        # Cache should miss due to file change
        cached = cache.get(jar_path)
        
        assert cached is None

    def test_cache_clear(self, tmp_path):
        """Test clearing the cache."""
        cache = ScanCache(tmp_path)
        
        jar_path = tmp_path / "test.jar"
        jar_path.write_bytes(b"content")
        
        mod_info = ModInfo(
            name="Test Mod",
            loader="fabric",
            version="1.0.0",
            filename="test.jar",
        )
        
        cache.set(jar_path, mod_info)
        
        # Clear cache
        cache.clear()
        
        # Should no longer be in cache
        cached = cache.get(jar_path)
        assert cached is None

    def test_cache_stats(self, tmp_path):
        """Test getting cache statistics."""
        cache = ScanCache(tmp_path)
        
        jar_path = tmp_path / "test.jar"
        jar_path.write_bytes(b"content")
        
        mod_info = ModInfo(
            name="Test Mod",
            loader="fabric",
            version="1.0.0",
            filename="test.jar",
        )
        
        cache.set(jar_path, mod_info)
        
        stats = cache.get_stats()
        
        assert isinstance(stats, dict)
        assert "entries" in stats or "total_entries" in stats or "cache_version" in stats
