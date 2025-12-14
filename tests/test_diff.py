"""Tests for diff module."""

import pytest
from pathlib import Path
from datetime import datetime
import json
import tempfile

from src.diff import (
    ModChange,
    DiffResult,
    compare_scan_results,
    load_scan_result_from_json,
    _get_mod_key,
    _compare_mods,
)
from src.models import ModInfo, ScanResult


class TestModChange:
    """Test ModChange dataclass."""

    def test_create_mod_change(self):
        """Test creating a ModChange."""
        change = ModChange(
            mod_id="test-mod",
            name="Test Mod",
            change_type="added",
            new_version="1.0.0",
            new_loader="fabric",
        )
        
        assert change.mod_id == "test-mod"
        assert change.name == "Test Mod"
        assert change.change_type == "added"
        assert change.new_version == "1.0.0"

    def test_to_dict(self):
        """Test converting ModChange to dict."""
        change = ModChange(
            mod_id="test-mod",
            name="Test Mod",
            change_type="updated",
            old_version="1.0.0",
            new_version="2.0.0",
            details=["version changed"],
        )
        
        d = change.to_dict()
        
        assert d["mod_id"] == "test-mod"
        assert d["change_type"] == "updated"
        assert d["old_version"] == "1.0.0"
        assert d["new_version"] == "2.0.0"
        assert "version changed" in d["details"]


class TestDiffResult:
    """Test DiffResult dataclass."""

    def test_has_changes_true(self):
        """Test has_changes when there are changes."""
        diff = DiffResult(
            added=[ModChange("mod1", "Mod 1", "added")],
        )
        
        assert diff.has_changes is True

    def test_has_changes_false(self):
        """Test has_changes when no changes."""
        diff = DiffResult()
        
        assert diff.has_changes is False

    def test_total_changes(self):
        """Test total_changes count."""
        diff = DiffResult(
            added=[ModChange("mod1", "Mod 1", "added")],
            removed=[ModChange("mod2", "Mod 2", "removed"), ModChange("mod3", "Mod 3", "removed")],
            updated=[ModChange("mod4", "Mod 4", "updated")],
        )
        
        assert diff.total_changes == 4

    def test_to_dict(self):
        """Test converting DiffResult to dict."""
        diff = DiffResult(
            added=[ModChange("mod1", "Mod 1", "added", new_version="1.0.0")],
            old_total_mods=5,
            new_total_mods=6,
        )
        
        d = diff.to_dict()
        
        assert d["summary"]["added_count"] == 1
        assert d["summary"]["old_total_mods"] == 5
        assert d["summary"]["new_total_mods"] == 6
        assert len(d["added"]) == 1

    def test_to_markdown(self):
        """Test generating markdown report."""
        diff = DiffResult(
            added=[ModChange("mod1", "New Mod", "added", new_version="1.0.0", new_loader="fabric")],
            removed=[ModChange("mod2", "Old Mod", "removed", old_version="0.5.0", old_loader="forge")],
        )
        
        md = diff.to_markdown()
        
        assert "# Modlist Diff Report" in md
        assert "➕ Added Mods" in md
        assert "New Mod" in md
        assert "➖ Removed Mods" in md
        assert "Old Mod" in md


class TestCompareMods:
    """Test mod comparison logic."""

    def test_compare_identical_mods(self):
        """Test comparing identical mods."""
        mod = ModInfo(
            name="Test Mod",
            loader="fabric",
            version="1.0.0",
            filename="test.jar",
        )
        
        has_changes, details = _compare_mods(mod, mod)
        
        assert has_changes is False
        assert len(details) == 0

    def test_compare_version_change(self):
        """Test detecting version change."""
        old_mod = ModInfo(name="Test", loader="fabric", version="1.0.0", filename="test.jar")
        new_mod = ModInfo(name="Test", loader="fabric", version="2.0.0", filename="test.jar")
        
        has_changes, details = _compare_mods(old_mod, new_mod)
        
        assert has_changes is True
        assert any("version" in d for d in details)

    def test_compare_loader_change(self):
        """Test detecting loader change."""
        old_mod = ModInfo(name="Test", loader="fabric", version="1.0.0", filename="test.jar")
        new_mod = ModInfo(name="Test", loader="forge", version="1.0.0", filename="test.jar")
        
        has_changes, details = _compare_mods(old_mod, new_mod)
        
        assert has_changes is True
        assert any("loader" in d for d in details)

    def test_compare_dependency_added(self):
        """Test detecting added dependency."""
        old_mod = ModInfo(name="Test", loader="fabric", version="1.0.0", filename="test.jar", dependencies=[])
        new_mod = ModInfo(name="Test", loader="fabric", version="1.0.0", filename="test.jar", dependencies=["dep1"])
        
        has_changes, details = _compare_mods(old_mod, new_mod)
        
        assert has_changes is True
        assert any("deps" in d for d in details)


class TestCompareScanResults:
    """Test comparing scan results."""

    def test_detect_added_mod(self):
        """Test detecting added mods."""
        old_result = ScanResult(mods=[
            ModInfo(name="Mod A", loader="fabric", version="1.0.0", filename="a.jar", mod_id="mod-a"),
        ])
        
        new_result = ScanResult(mods=[
            ModInfo(name="Mod A", loader="fabric", version="1.0.0", filename="a.jar", mod_id="mod-a"),
            ModInfo(name="Mod B", loader="fabric", version="1.0.0", filename="b.jar", mod_id="mod-b"),
        ])
        
        diff = compare_scan_results(old_result, new_result)
        
        assert len(diff.added) == 1
        assert diff.added[0].name == "Mod B"
        assert len(diff.removed) == 0

    def test_detect_removed_mod(self):
        """Test detecting removed mods."""
        old_result = ScanResult(mods=[
            ModInfo(name="Mod A", loader="fabric", version="1.0.0", filename="a.jar", mod_id="mod-a"),
            ModInfo(name="Mod B", loader="fabric", version="1.0.0", filename="b.jar", mod_id="mod-b"),
        ])
        
        new_result = ScanResult(mods=[
            ModInfo(name="Mod A", loader="fabric", version="1.0.0", filename="a.jar", mod_id="mod-a"),
        ])
        
        diff = compare_scan_results(old_result, new_result)
        
        assert len(diff.removed) == 1
        assert diff.removed[0].name == "Mod B"
        assert len(diff.added) == 0

    def test_detect_updated_mod(self):
        """Test detecting updated mods."""
        old_result = ScanResult(mods=[
            ModInfo(name="Mod A", loader="fabric", version="1.0.0", filename="a.jar", mod_id="mod-a"),
        ])
        
        new_result = ScanResult(mods=[
            ModInfo(name="Mod A", loader="fabric", version="2.0.0", filename="a.jar", mod_id="mod-a"),
        ])
        
        diff = compare_scan_results(old_result, new_result)
        
        assert len(diff.updated) == 1
        assert diff.updated[0].old_version == "1.0.0"
        assert diff.updated[0].new_version == "2.0.0"

    def test_include_unchanged(self):
        """Test including unchanged mods."""
        mod = ModInfo(name="Mod A", loader="fabric", version="1.0.0", filename="a.jar", mod_id="mod-a")
        old_result = ScanResult(mods=[mod])
        new_result = ScanResult(mods=[mod])
        
        diff = compare_scan_results(old_result, new_result, include_unchanged=True)
        
        assert len(diff.unchanged) == 1
        assert diff.unchanged[0].name == "Mod A"


class TestLoadScanResultFromJson:
    """Test loading scan results from JSON."""

    def test_load_standard_format(self, tmp_path):
        """Test loading standard JSON format."""
        json_file = tmp_path / "modlist.json"
        data = {
            "mods": [
                {"name": "Test Mod", "loader": "fabric", "version": "1.0.0", "filename": "test.jar"},
            ],
            "total_mods": 1,
            "total_files_scanned": 1,
            "generated_at": "2024-01-01T00:00:00",
        }
        json_file.write_text(json.dumps(data))
        
        result = load_scan_result_from_json(json_file)
        
        assert len(result.mods) == 1
        assert result.mods[0].name == "Test Mod"

    def test_load_list_format(self, tmp_path):
        """Test loading plain list format."""
        json_file = tmp_path / "modlist.json"
        data = [
            {"name": "Mod A", "loader": "fabric", "version": "1.0.0", "filename": "a.jar"},
            {"name": "Mod B", "loader": "forge", "version": "2.0.0", "filename": "b.jar"},
        ]
        json_file.write_text(json.dumps(data))
        
        result = load_scan_result_from_json(json_file)
        
        assert len(result.mods) == 2

    def test_load_with_all_fields(self, tmp_path):
        """Test loading mod with all fields."""
        json_file = tmp_path / "modlist.json"
        data = {
            "mods": [{
                "name": "Full Mod",
                "loader": "fabric",
                "version": "1.0.0",
                "filename": "full.jar",
                "mod_id": "full-mod",
                "author": "Test Author",
                "description": "A test mod",
                "dependencies": ["dep1", "dep2"],
                "mc_versions": ["1.20.1"],
                "disabled": True,
            }],
        }
        json_file.write_text(json.dumps(data))
        
        result = load_scan_result_from_json(json_file)
        
        mod = result.mods[0]
        assert mod.mod_id == "full-mod"
        assert mod.author == "Test Author"
        assert mod.dependencies == ["dep1", "dep2"]
        assert mod.disabled is True
