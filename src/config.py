"""Configuration management for modlist-generator."""
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore

try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore


@dataclass
class Config:
    """Application configuration."""
    
    # Scanning settings
    default_workers: int = 4
    default_format: str = "json"
    include_disabled: bool = False
    recursive: bool = False
    
    # Output settings
    default_output_dir: Optional[str] = None
    compact_json: bool = False
    detailed_markdown: bool = False
    
    # Filtering
    exclude_patterns: List[str] = field(default_factory=list)
    default_loader_filter: Optional[str] = None
    exclude_unknown: bool = False
    
    # Performance
    max_workers: int = 16
    enable_cache: bool = False
    cache_dir: Optional[str] = None
    
    # UI/UX
    show_progress: bool = True
    use_rich: bool = True
    recent_folders: List[str] = field(default_factory=list)
    max_recent_folders: int = 10
    
    # Advanced
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """Load configuration from TOML file."""
        if not config_path.exists():
            return cls()
        
        if tomllib is None:
            raise ImportError(
                "TOML support not available. Install 'tomli' for Python < 3.11"
            )
        
        with open(config_path, 'rb') as f:
            data = tomllib.load(f)
        
        return cls(**data)
    
    def save(self, config_path: Path) -> None:
        """Save configuration to TOML file."""
        if tomli_w is None:
            raise ImportError(
                "TOML writing not available. Install 'tomli-w' to save config"
            )
        
        # Convert to dict
        data = {
            "default_workers": self.default_workers,
            "default_format": self.default_format,
            "include_disabled": self.include_disabled,
            "recursive": self.recursive,
            "compact_json": self.compact_json,
            "detailed_markdown": self.detailed_markdown,
            "exclude_patterns": self.exclude_patterns,
            "exclude_unknown": self.exclude_unknown,
            "max_workers": self.max_workers,
            "enable_cache": self.enable_cache,
            "show_progress": self.show_progress,
            "use_rich": self.use_rich,
            "recent_folders": self.recent_folders,
            "max_recent_folders": self.max_recent_folders,
            "log_level": self.log_level,
        }
        
        # Add optional fields
        if self.default_output_dir:
            data["default_output_dir"] = self.default_output_dir
        if self.default_loader_filter:
            data["default_loader_filter"] = self.default_loader_filter
        if self.cache_dir:
            data["cache_dir"] = self.cache_dir
        if self.log_file:
            data["log_file"] = self.log_file
        
        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'wb') as f:
            tomli_w.dump(data, f)
    
    def add_recent_folder(self, folder_path: str) -> None:
        """Add a folder to recent folders list."""
        # Remove if already exists
        if folder_path in self.recent_folders:
            self.recent_folders.remove(folder_path)
        
        # Add to front
        self.recent_folders.insert(0, folder_path)
        
        # Trim to max
        self.recent_folders = self.recent_folders[:self.max_recent_folders]
    
    def get_config_dir(self) -> Path:
        """Get platform-specific config directory."""
        try:
            from platformdirs import user_config_dir
            return Path(user_config_dir("modlist-generator", ensure_exists=True))
        except ImportError:
            # Fallback to home directory
            config_dir = Path.home() / ".config" / "modlist-generator"
            config_dir.mkdir(parents=True, exist_ok=True)
            return config_dir
    
    def get_cache_dir(self) -> Path:
        """Get platform-specific cache directory."""
        if self.cache_dir:
            return Path(self.cache_dir)
        
        try:
            from platformdirs import user_cache_dir
            cache_path = Path(user_cache_dir("modlist-generator", ensure_exists=True))
        except ImportError:
            # Fallback
            cache_path = Path.home() / ".cache" / "modlist-generator"
        
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path


def load_config() -> Config:
    """Load configuration from default location."""
    config = Config()
    config_dir = config.get_config_dir()
    config_file = config_dir / "config.toml"
    
    if config_file.exists():
        try:
            return Config.from_file(config_file)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_file}: {e}")
            print("Using default configuration")
    
    return config


def save_config(config: Config) -> None:
    """Save configuration to default location."""
    config_dir = config.get_config_dir()
    config_file = config_dir / "config.toml"
    config.save(config_file)
