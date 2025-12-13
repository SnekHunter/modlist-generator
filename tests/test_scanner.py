"""Tests for mod scanner."""
import pytest
from pathlib import Path
from src.scanner import ModScanner
from src.models import ScanResult


class TestModScanner:
    """Tests for ModScanner class."""
    
    def test_scan_single_fabric_mod(self, mock_fabric_jar):
        """Test scanning a single Fabric mod."""
        scanner = ModScanner(workers=1)
        folder = mock_fabric_jar.parent
        
        result = scanner.scan_folder(folder)
        
        assert isinstance(result, ScanResult)
        assert len(result.mods) == 1
        assert result.mods[0].name == "Test Fabric Mod"
        assert result.mods[0].loader == "fabric"
    
    def test_scan_multiple_mods(self, mock_mods_folder):
        """Test scanning folder with multiple mods."""
        scanner = ModScanner(workers=2)
        result = scanner.scan_folder(mock_mods_folder)
        
        # Should find 3 active mods (fabric, forge, quilt)
        active_mods = [m for m in result.mods if not m.disabled]
        assert len(active_mods) == 3
        
        # Check loaders are detected correctly
        loaders = {m.loader for m in active_mods}
        assert "fabric" in loaders
        assert "quilt" in loaders
        assert any(loader in ["forge", "neoforge"] for loader in loaders)
    
    def test_scan_with_disabled_mods(self, mock_mods_folder):
        """Test scanning with disabled mods included."""
        scanner = ModScanner(workers=1)
        result = scanner.scan_folder(mock_mods_folder, include_disabled=True)
        
        # Should find 1 disabled mod
        disabled_mods = [m for m in result.mods if m.disabled]
        assert len(disabled_mods) == 1
        assert disabled_mods[0].disabled is True
    
    def test_scan_exclude_disabled_mods(self, mock_mods_folder):
        """Test scanning excluding disabled mods."""
        scanner = ModScanner(workers=1)
        result = scanner.scan_folder(mock_mods_folder, include_disabled=False)
        
        # Should not include disabled mods
        disabled_mods = [m for m in result.mods if m.disabled]
        assert len(disabled_mods) == 0
    
    def test_scan_with_corrupted_jar(self, temp_dir, mock_corrupted_jar, mock_fabric_jar):
        """Test scanning folder with corrupted JAR."""
        # Copy valid mod to same folder as corrupted
        import shutil
        shutil.copy(mock_fabric_jar, temp_dir / "valid.jar")
        
        scanner = ModScanner(workers=1)
        result = scanner.scan_folder(temp_dir)
        
        # Should successfully scan valid mod
        assert len(result.mods) >= 1
        
        # Should record error for corrupted file
        assert len(result.errors) >= 1
        assert any("corrupted" in err.lower() for err in result.errors)
    
    def test_parallel_scanning(self, mock_mods_folder):
        """Test parallel scanning with multiple workers."""
        scanner = ModScanner(workers=4)
        result = scanner.scan_folder(mock_mods_folder)
        
        # Results should be same as single-threaded
        assert len(result.mods) >= 3
        assert result.scan_duration > 0
    
    def test_progress_callback(self, mock_mods_folder):
        """Test progress callback during scanning."""
        progress_updates = []
        
        def callback(current: int, total: int, filename: str):
            progress_updates.append((current, total, filename))
        
        scanner = ModScanner(workers=1)
        result = scanner.scan_folder(mock_mods_folder, progress_callback=callback)
        
        # Should have received progress updates
        assert len(progress_updates) > 0
        
        # Last update should be total count
        final_update = progress_updates[-1]
        assert final_update[0] == final_update[1]  # current == total
    
    def test_exclude_patterns(self, mock_mods_folder):
        """Test excluding files by pattern."""
        scanner = ModScanner(workers=1)
        
        # Exclude all fabric mods
        result = scanner.scan_folder(
            mock_mods_folder, 
            exclude_patterns=["*fabric*"]
        )
        
        # Should not find any Fabric mods
        fabric_mods = [m for m in result.mods if m.loader == "fabric"]
        assert len(fabric_mods) == 0
    
    def test_recursive_scanning(self, temp_dir):
        """Test recursive folder scanning."""
        # Create nested structure
        subfolder = temp_dir / "mods" / "subfolder"
        subfolder.mkdir(parents=True)
        
        # Create mock mod in subfolder
        from tests.conftest import mock_fabric_jar
        import shutil
        import zipfile
        import json
        
        jar_path = subfolder / "nested-mod.jar"
        metadata = {
            "schemaVersion": 1,
            "id": "nested_mod",
            "version": "1.0.0",
            "name": "Nested Mod"
        }
        with zipfile.ZipFile(jar_path, 'w') as jar:
            jar.writestr("fabric.mod.json", json.dumps(metadata))
        
        scanner = ModScanner(workers=1)
        
        # Non-recursive should find nothing in parent
        result_no_recursive = scanner.scan_folder(temp_dir / "mods", recursive=False)
        assert len(result_no_recursive.mods) == 0
        
        # Recursive should find mod in subfolder
        result_recursive = scanner.scan_folder(temp_dir / "mods", recursive=True)
        assert len(result_recursive.mods) == 1
        assert result_recursive.mods[0].name == "Nested Mod"


class TestScanResult:
    """Tests for ScanResult class."""
    
    def test_filter_by_loader(self, mock_mods_folder):
        """Test filtering results by loader type."""
        scanner = ModScanner(workers=1)
        result = scanner.scan_folder(mock_mods_folder)
        
        # Filter for only Fabric mods
        fabric_result = result.filter_by_loader("fabric")
        assert all(m.loader == "fabric" for m in fabric_result.mods)
        assert len(fabric_result.mods) >= 1
    
    def test_sort_by_name(self, mock_mods_folder):
        """Test sorting results by name."""
        scanner = ModScanner(workers=1)
        result = scanner.scan_folder(mock_mods_folder)
        
        result.sort_mods(by="name")
        
        # Check if sorted
        names = [m.name for m in result.mods]
        assert names == sorted(names)
    
    def test_to_dict(self, mock_mods_folder):
        """Test converting result to dictionary."""
        scanner = ModScanner(workers=1)
        result = scanner.scan_folder(mock_mods_folder)
        
        data = result.to_dict()
        
        assert "total_mods" in data
        assert "mods" in data
        assert isinstance(data["mods"], list)
        assert data["total_mods"] == len(result.mods)
