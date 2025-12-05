"""
Data models for the Modlist Generator.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass(frozen=True)
class ModInfo:
    """Immutable data class to hold mod information."""
    name: str
    loader: str
    version: str
    filename: str
    mod_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    author: Optional[str] = None
    description: Optional[str] = None
    mc_versions: List[str] = field(default_factory=list)
    disabled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values and empty lists."""
        result = {
            "name": self.name,
            "loader": self.loader,
            "version": self.version,
            "filename": self.filename,
        }
        if self.mod_id:
            result["mod_id"] = self.mod_id
        if self.dependencies:
            result["dependencies"] = list(self.dependencies)
        if self.author:
            result["author"] = self.author
        if self.description:
            result["description"] = self.description
        if self.mc_versions:
            result["mc_versions"] = list(self.mc_versions)
        if self.disabled:
            result["disabled"] = True
        return result


@dataclass
class ScanResult:
    """Container for scan results."""
    mods: List[ModInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_files: int = 0
    scan_duration: float = 0.0
    generated_at: Optional[datetime] = None
    
    def to_dict(self, include_errors: bool = True) -> Dict[str, Any]:
        """Convert scan result to dictionary for JSON output."""
        result = {
            "mods": [mod.to_dict() for mod in self.mods],
            "total_mods": len(self.mods),
            "total_files_scanned": self.total_files,
            "scan_duration_seconds": round(self.scan_duration, 2),
            "generated_at": self.generated_at.isoformat() if self.generated_at else datetime.now().isoformat(),
        }
        if include_errors and self.errors:
            result["errors"] = self.errors
            result["error_count"] = len(self.errors)
        return result
    
    def get_duplicates(self) -> Dict[str, List[ModInfo]]:
        """Find duplicate mods by mod_id."""
        duplicates: Dict[str, List[ModInfo]] = {}
        seen: Dict[str, List[ModInfo]] = {}
        
        for mod in self.mods:
            key = mod.mod_id or mod.name.lower()
            if key in seen:
                seen[key].append(mod)
                duplicates[key] = seen[key]
            else:
                seen[key] = [mod]
        
        return duplicates
    
    def filter_by_loader(self, loader: str) -> List[ModInfo]:
        """Filter mods by loader type."""
        return [mod for mod in self.mods if mod.loader.lower() == loader.lower()]
    
    def sort_mods(self, by: str = "name", reverse: bool = False) -> None:
        """Sort mods by specified field."""
        sort_keys = {
            "name": lambda m: m.name.lower(),
            "loader": lambda m: m.loader.lower(),
            "version": lambda m: m.version.lower(),
            "filename": lambda m: m.filename.lower(),
        }
        if by in sort_keys:
            self.mods.sort(key=sort_keys[by], reverse=reverse)
