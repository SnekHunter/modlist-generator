"""Tests for configuration module."""

import pytest
from pathlib import Path
import tempfile
import os

from src.config import Config, load_config


class TestConfig:
    """Test Config dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        
        assert config.default_workers == 4
        assert config.default_format == "json"
        assert config.include_disabled is False
        assert config.recursive is False
        assert config.enable_cache is False
        assert config.show_progress is True
        assert config.log_level == "INFO"

    def test_config_custom_values(self):
        """Test configuration with custom values."""
        config = Config(
            default_workers=8,
            default_format="csv",
            include_disabled=True,
            enable_cache=True,
        )
        
        assert config.default_workers == 8
        assert config.default_format == "csv"
        assert config.include_disabled is True
        assert config.enable_cache is True

    def test_get_cache_dir_default(self):
        """Test default cache directory."""
        config = Config()
        cache_dir = config.get_cache_dir()
        
        assert isinstance(cache_dir, Path)
        assert "modlist-generator" in str(cache_dir).lower() or "cache" in str(cache_dir).lower()

    def test_get_cache_dir_custom(self):
        """Test custom cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(cache_dir=tmpdir)
            cache_dir = config.get_cache_dir()
            
            assert cache_dir == Path(tmpdir)


class TestLoadConfig:
    """Test config loading functions."""

    def test_load_config_no_file(self):
        """Test loading config when no file exists."""
        config = load_config()
        
        assert isinstance(config, Config)
        # Should return defaults
        assert config.default_workers == 4


class TestConfigFromFile:
    """Test loading config from TOML file."""

    def test_load_from_valid_toml(self, tmp_path):
        """Test loading from a valid TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
default_workers = 8
default_format = "markdown"
enable_cache = true
""")
        
        config = Config.from_file(config_file)
        
        assert config.default_workers == 8
        assert config.default_format == "markdown"
        assert config.enable_cache is True

    def test_load_from_nonexistent_file(self, tmp_path):
        """Test loading from non-existent file returns defaults."""
        config_file = tmp_path / "nonexistent.toml"
        
        config = Config.from_file(config_file)
        
        assert config.default_workers == 4  # Default value
