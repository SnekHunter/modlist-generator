"""
Diff module for comparing scan results.

Provides functionality to compare two modlists and identify:
- Added mods (new in current scan)
- Removed mods (missing from current scan)
- Updated mods (version or other changes)
- Unchanged mods
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import json
from datetime import datetime

from .models import ModInfo, ScanResult


@dataclass
class ModChange:
    """Represents a change in a single mod."""
    
    mod_id: str
    name: str
    change_type: str  # "added", "removed", "updated", "unchanged"
    old_version: Optional[str] = None
    new_version: Optional[str] = None
    old_loader: Optional[str] = None
    new_loader: Optional[str] = None
    details: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "mod_id": self.mod_id,
            "name": self.name,
            "change_type": self.change_type,
        }
        if self.old_version:
            result["old_version"] = self.old_version
        if self.new_version:
            result["new_version"] = self.new_version
        if self.old_loader:
            result["old_loader"] = self.old_loader
        if self.new_loader:
            result["new_loader"] = self.new_loader
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class DiffResult:
    """Result of comparing two scan results."""
    
    added: List[ModChange] = field(default_factory=list)
    removed: List[ModChange] = field(default_factory=list)
    updated: List[ModChange] = field(default_factory=list)
    unchanged: List[ModChange] = field(default_factory=list)
    
    old_scan_time: Optional[str] = None
    new_scan_time: Optional[str] = None
    old_total_mods: int = 0
    new_total_mods: int = 0
    
    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(self.added or self.removed or self.updated)
    
    @property
    def total_changes(self) -> int:
        """Total number of changes."""
        return len(self.added) + len(self.removed) + len(self.updated)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "summary": {
                "added_count": len(self.added),
                "removed_count": len(self.removed),
                "updated_count": len(self.updated),
                "unchanged_count": len(self.unchanged),
                "total_changes": self.total_changes,
                "old_total_mods": self.old_total_mods,
                "new_total_mods": self.new_total_mods,
                "old_scan_time": self.old_scan_time,
                "new_scan_time": self.new_scan_time,
            },
            "added": [m.to_dict() for m in self.added],
            "removed": [m.to_dict() for m in self.removed],
            "updated": [m.to_dict() for m in self.updated],
        }
    
    def to_markdown(self) -> str:
        """Generate markdown report of changes."""
        lines = [
            "# Modlist Diff Report",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Added | {len(self.added)} |",
            f"| Removed | {len(self.removed)} |",
            f"| Updated | {len(self.updated)} |",
            f"| Unchanged | {len(self.unchanged)} |",
            f"| Total Changes | {self.total_changes} |",
            "",
        ]
        
        if self.old_scan_time:
            lines.append(f"**Previous scan:** {self.old_scan_time}")
        if self.new_scan_time:
            lines.append(f"**Current scan:** {self.new_scan_time}")
        lines.append("")
        
        if self.added:
            lines.extend([
                "## ➕ Added Mods",
                "",
                "| Mod | Version | Loader |",
                "|-----|---------|--------|",
            ])
            for mod in sorted(self.added, key=lambda m: m.name.lower()):
                lines.append(f"| {mod.name} | {mod.new_version or '-'} | {mod.new_loader or '-'} |")
            lines.append("")
        
        if self.removed:
            lines.extend([
                "## ➖ Removed Mods",
                "",
                "| Mod | Version | Loader |",
                "|-----|---------|--------|",
            ])
            for mod in sorted(self.removed, key=lambda m: m.name.lower()):
                lines.append(f"| {mod.name} | {mod.old_version or '-'} | {mod.old_loader or '-'} |")
            lines.append("")
        
        if self.updated:
            lines.extend([
                "## 🔄 Updated Mods",
                "",
                "| Mod | Old Version | New Version | Changes |",
                "|-----|-------------|-------------|---------|",
            ])
            for mod in sorted(self.updated, key=lambda m: m.name.lower()):
                changes = ", ".join(mod.details) if mod.details else "version"
                lines.append(f"| {mod.name} | {mod.old_version or '-'} | {mod.new_version or '-'} | {changes} |")
            lines.append("")
        
        if not self.has_changes:
            lines.extend([
                "## No Changes Detected",
                "",
                "The modlists are identical.",
            ])
        
        return "\n".join(lines)


def _get_mod_key(mod: ModInfo) -> str:
    """Get a unique key for a mod (prefer mod_id, fallback to name)."""
    return mod.mod_id or mod.name.lower()


def _compare_mods(old_mod: ModInfo, new_mod: ModInfo) -> Tuple[bool, List[str]]:
    """
    Compare two mods and return (has_changes, list_of_changes).
    
    Returns:
        Tuple of (has_changes: bool, details: List[str])
    """
    changes = []
    
    if old_mod.version != new_mod.version:
        changes.append(f"version: {old_mod.version} → {new_mod.version}")
    
    if old_mod.loader != new_mod.loader:
        changes.append(f"loader: {old_mod.loader} → {new_mod.loader}")
    
    if old_mod.author != new_mod.author:
        changes.append(f"author changed")
    
    # Compare dependencies
    old_deps = set(old_mod.dependencies) if old_mod.dependencies else set()
    new_deps = set(new_mod.dependencies) if new_mod.dependencies else set()
    
    added_deps = new_deps - old_deps
    removed_deps = old_deps - new_deps
    
    if added_deps:
        changes.append(f"+{len(added_deps)} deps")
    if removed_deps:
        changes.append(f"-{len(removed_deps)} deps")
    
    # Compare MC versions
    old_mc = set(old_mod.mc_versions) if old_mod.mc_versions else set()
    new_mc = set(new_mod.mc_versions) if new_mod.mc_versions else set()
    
    if old_mc != new_mc:
        changes.append("MC versions changed")
    
    return bool(changes), changes


def compare_scan_results(
    old_result: ScanResult,
    new_result: ScanResult,
    include_unchanged: bool = False
) -> DiffResult:
    """
    Compare two scan results and identify changes.
    
    Args:
        old_result: Previous scan result
        new_result: Current scan result
        include_unchanged: Whether to include unchanged mods in result
    
    Returns:
        DiffResult with categorized changes
    """
    diff = DiffResult(
        old_total_mods=len(old_result.mods),
        new_total_mods=len(new_result.mods),
        old_scan_time=old_result.generated_at.isoformat() if old_result.generated_at else None,
        new_scan_time=new_result.generated_at.isoformat() if new_result.generated_at else None,
    )
    
    # Build lookup dictionaries
    old_mods: Dict[str, ModInfo] = {_get_mod_key(m): m for m in old_result.mods}
    new_mods: Dict[str, ModInfo] = {_get_mod_key(m): m for m in new_result.mods}
    
    old_keys = set(old_mods.keys())
    new_keys = set(new_mods.keys())
    
    # Find added mods
    for key in new_keys - old_keys:
        mod = new_mods[key]
        diff.added.append(ModChange(
            mod_id=key,
            name=mod.name,
            change_type="added",
            new_version=mod.version,
            new_loader=mod.loader,
        ))
    
    # Find removed mods
    for key in old_keys - new_keys:
        mod = old_mods[key]
        diff.removed.append(ModChange(
            mod_id=key,
            name=mod.name,
            change_type="removed",
            old_version=mod.version,
            old_loader=mod.loader,
        ))
    
    # Find updated and unchanged mods
    for key in old_keys & new_keys:
        old_mod = old_mods[key]
        new_mod = new_mods[key]
        
        has_changes, details = _compare_mods(old_mod, new_mod)
        
        if has_changes:
            diff.updated.append(ModChange(
                mod_id=key,
                name=new_mod.name,
                change_type="updated",
                old_version=old_mod.version,
                new_version=new_mod.version,
                old_loader=old_mod.loader,
                new_loader=new_mod.loader,
                details=details,
            ))
        elif include_unchanged:
            diff.unchanged.append(ModChange(
                mod_id=key,
                name=new_mod.name,
                change_type="unchanged",
                new_version=new_mod.version,
                new_loader=new_mod.loader,
            ))
    
    return diff


def load_scan_result_from_json(json_path: Path) -> ScanResult:
    """
    Load a ScanResult from a JSON file.
    
    Args:
        json_path: Path to JSON file (output from previous scan)
    
    Returns:
        ScanResult reconstructed from JSON
    
    Raises:
        ValueError: If JSON format is invalid
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Handle both direct mod list and wrapped format
    if "mods" in data:
        mods_data = data["mods"]
        generated_at = data.get("generated_at")
        total_files = data.get("total_files_scanned", 0)
        errors = data.get("errors", [])
    elif isinstance(data, list):
        # Plain list of mods
        mods_data = data
        generated_at = None
        total_files = len(data)
        errors = []
    else:
        raise ValueError(f"Invalid JSON format: expected 'mods' key or list of mods")
    
    # Reconstruct ModInfo objects
    mods = []
    for mod_data in mods_data:
        mod = ModInfo(
            name=mod_data.get("name", "Unknown"),
            loader=mod_data.get("loader", "unknown"),
            version=mod_data.get("version", "0.0.0"),
            filename=mod_data.get("filename", ""),
            mod_id=mod_data.get("mod_id"),
            dependencies=mod_data.get("dependencies", []),
            author=mod_data.get("author"),
            description=mod_data.get("description"),
            mc_versions=mod_data.get("mc_versions", []),
            disabled=mod_data.get("disabled", False),
        )
        mods.append(mod)
    
    # Parse generated_at
    parsed_time = None
    if generated_at:
        try:
            parsed_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    
    return ScanResult(
        mods=mods,
        errors=errors,
        total_files=total_files,
        generated_at=parsed_time,
    )
