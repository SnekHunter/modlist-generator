"""Tests for data models."""
import pytest
from src.models import ModInfo, ScanResult


class TestModInfo:
    """Tests for ModInfo dataclass."""
    
    def test_create_mod_info(self):
        """Test creating ModInfo instance."""
        mod = ModInfo(
            name="Test Mod",
            loader="fabric",
            version="1.0.0",
            filename="test.jar",
            mod_id="test_mod",
            dependencies=["dep1", "dep2"],
            author="TestAuthor",
            description="Test description",
            mc_versions=["1.20.1"],
            disabled=False
        )
        
        assert mod.name == "Test Mod"
        assert mod.loader == "fabric"
        assert len(mod.dependencies) == 2
    
    def test_mod_info_immutable(self):
        """Test that ModInfo is immutable (frozen)."""
        mod = ModInfo(
            name="Test",
            loader="fabric",
            version="1.0.0",
            filename="test.jar"
        )
        
        # Should raise error when trying to modify
        with pytest.raises(AttributeError):
            mod.name = "Modified"
    
    def test_to_dict(self):
        """Test converting ModInfo to dictionary."""
        mod = ModInfo(
            name="Test Mod",
            loader="fabric",
            version="1.0.0",
            filename="test.jar",
            mod_id="test_mod"
        )
        
        data = mod.to_dict()
        
        assert data["name"] == "Test Mod"
        assert data["loader"] == "fabric"
        assert data["mod_id"] == "test_mod"
    
    def test_to_dict_excludes_none(self):
        """Test that to_dict excludes None values."""
        mod = ModInfo(
            name="Test Mod",
            loader="fabric",
            version="1.0.0",
            filename="test.jar",
            mod_id=None,  # None value
            author=None,  # None value
        )
        
        data = mod.to_dict()
        
        # None values should be excluded
        assert "mod_id" not in data
        assert "author" not in data


class TestScanResult:
    """Tests for ScanResult dataclass."""
    
    def test_create_scan_result(self):
        """Test creating ScanResult instance."""
        mods = [
            ModInfo(name="Mod1", loader="fabric", version="1.0", filename="m1.jar"),
            ModInfo(name="Mod2", loader="forge", version="2.0", filename="m2.jar"),
        ]
        
        result = ScanResult(
            mods=mods,
            total_mods=2,
            scan_duration=1.5,
            errors=[]
        )
        
        assert len(result.mods) == 2
        assert result.total_mods == 2
        assert result.scan_duration == 1.5
    
    def test_filter_by_loader(self):
        """Test filtering by loader type."""
        mods = [
            ModInfo(name="Fabric1", loader="fabric", version="1.0", filename="f1.jar"),
            ModInfo(name="Forge1", loader="forge", version="1.0", filename="fo1.jar"),
            ModInfo(name="Fabric2", loader="fabric", version="2.0", filename="f2.jar"),
        ]
        
        result = ScanResult(mods=mods, total_mods=3, scan_duration=1.0, errors=[])
        filtered = result.filter_by_loader("fabric")
        
        assert len(filtered.mods) == 2
        assert all(m.loader == "fabric" for m in filtered.mods)
    
    def test_sort_mods_by_name(self):
        """Test sorting mods by name."""
        mods = [
            ModInfo(name="Zebra", loader="fabric", version="1.0", filename="z.jar"),
            ModInfo(name="Apple", loader="forge", version="1.0", filename="a.jar"),
            ModInfo(name="Banana", loader="quilt", version="1.0", filename="b.jar"),
        ]
        
        result = ScanResult(mods=mods, total_mods=3, scan_duration=1.0, errors=[])
        result.sort_mods(by="name")
        
        assert result.mods[0].name == "Apple"
        assert result.mods[1].name == "Banana"
        assert result.mods[2].name == "Zebra"
    
    def test_sort_mods_by_loader(self):
        """Test sorting mods by loader."""
        mods = [
            ModInfo(name="Mod1", loader="quilt", version="1.0", filename="m1.jar"),
            ModInfo(name="Mod2", loader="fabric", version="1.0", filename="m2.jar"),
            ModInfo(name="Mod3", loader="forge", version="1.0", filename="m3.jar"),
        ]
        
        result = ScanResult(mods=mods, total_mods=3, scan_duration=1.0, errors=[])
        result.sort_mods(by="loader")
        
        loaders = [m.loader for m in result.mods]
        assert loaders == sorted(loaders)
    
    def test_to_dict(self):
        """Test converting ScanResult to dictionary."""
        mods = [
            ModInfo(name="Mod1", loader="fabric", version="1.0", filename="m1.jar"),
        ]
        
        result = ScanResult(
            mods=mods,
            total_mods=1,
            scan_duration=1.5,
            errors=["Error 1"]
        )
        
        data = result.to_dict()
        
        assert data["total_mods"] == 1
        assert len(data["mods"]) == 1
        assert data["scan_duration"] == 1.5
        assert "Error 1" in data["errors"]
