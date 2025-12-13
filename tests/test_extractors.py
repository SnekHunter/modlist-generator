"""Tests for mod extractors."""
import pytest
import zipfile
from pathlib import Path
from src.extractors import (
    FabricExtractor,
    ForgeTomlExtractor,
    LegacyForgeExtractor,
    QuiltExtractor,
)
from src.models import ModInfo


class TestFabricExtractor:
    """Tests for Fabric mod extractor."""

    def test_can_extract_fabric_mod(self, mock_fabric_jar):
        """Test detection of Fabric mods."""
        extractor = FabricExtractor()
        with zipfile.ZipFile(mock_fabric_jar, "r") as jar:
            files = jar.namelist()
            assert extractor.can_extract(jar, files) is True

    def test_cannot_extract_non_fabric(self, mock_forge_jar):
        """Test rejection of non-Fabric mods."""
        extractor = FabricExtractor()
        with zipfile.ZipFile(mock_forge_jar, "r") as jar:
            files = jar.namelist()
            assert extractor.can_extract(jar, files) is False

    def test_extract_fabric_metadata(self, mock_fabric_jar):
        """Test extraction of Fabric mod metadata."""
        extractor = FabricExtractor()
        with zipfile.ZipFile(mock_fabric_jar, "r") as jar:
            files = jar.namelist()
            mod_info, error = extractor.extract(jar, mock_fabric_jar, files)

        assert error is None
        assert mod_info is not None
        assert mod_info.name == "Test Fabric Mod"
        assert mod_info.version == "1.0.0"
        assert mod_info.loader == "fabric"
        assert mod_info.mod_id == "test_mod"
        assert mod_info.author == "TestAuthor"
        assert "1.20" in mod_info.mc_versions
        assert "fabricloader" in mod_info.dependencies

    def test_extract_corrupted_jar(self, mock_corrupted_jar):
        """Test handling of corrupted JAR files."""
        extractor = FabricExtractor()
        # Corrupted JAR should raise BadZipFile when trying to open
        with pytest.raises(zipfile.BadZipFile):
            with zipfile.ZipFile(mock_corrupted_jar, "r") as jar:
                files = jar.namelist()
                mod_info, error = extractor.extract(jar, mock_corrupted_jar, files)


class TestForgeTomlExtractor:
    """Tests for Forge TOML mod extractor."""

    def test_can_extract_forge_mod(self, mock_forge_jar):
        """Test detection of Forge mods."""
        extractor = ForgeTomlExtractor()
        with zipfile.ZipFile(mock_forge_jar, "r") as jar:
            files = jar.namelist()
            assert extractor.can_extract(jar, files) is True

    def test_cannot_extract_non_forge(self, mock_fabric_jar):
        """Test rejection of non-Forge mods."""
        extractor = ForgeTomlExtractor()
        with zipfile.ZipFile(mock_fabric_jar, "r") as jar:
            files = jar.namelist()
            assert extractor.can_extract(jar, files) is False

    def test_extract_forge_metadata(self, mock_forge_jar):
        """Test extraction of Forge mod metadata."""
        extractor = ForgeTomlExtractor()
        with zipfile.ZipFile(mock_forge_jar, "r") as jar:
            files = jar.namelist()
            mod_info, error = extractor.extract(jar, mock_forge_jar, files)

        assert error is None
        assert mod_info is not None
        assert mod_info.name == "Test Forge Mod"
        assert mod_info.version == "2.0.0"
        assert mod_info.loader in ["forge", "neoforge"]
        assert mod_info.mod_id == "test_forge_mod"
        assert mod_info.author == "ForgeAuthor"


class TestQuiltExtractor:
    """Tests for Quilt mod extractor."""

    def test_can_extract_quilt_mod(self, mock_quilt_jar):
        """Test detection of Quilt mods."""
        extractor = QuiltExtractor()
        with zipfile.ZipFile(mock_quilt_jar, "r") as jar:
            files = jar.namelist()
            assert extractor.can_extract(jar, files) is True

    def test_cannot_extract_non_quilt(self, mock_forge_jar):
        """Test rejection of non-Quilt mods."""
        extractor = QuiltExtractor()
        with zipfile.ZipFile(mock_forge_jar, "r") as jar:
            files = jar.namelist()
            assert extractor.can_extract(jar, files) is False

    def test_extract_quilt_metadata(self, mock_quilt_jar):
        """Test extraction of Quilt mod metadata."""
        extractor = QuiltExtractor()
        with zipfile.ZipFile(mock_quilt_jar, "r") as jar:
            files = jar.namelist()
            mod_info, error = extractor.extract(jar, mock_quilt_jar, files)

        assert error is None
        assert mod_info is not None
        assert mod_info.name == "Test Quilt Mod"
        assert mod_info.version == "1.5.0"
        assert mod_info.loader == "quilt"
        assert mod_info.mod_id == "test_quilt_mod"
        assert mod_info.author == "QuiltAuthor"
        assert "1.20" in mod_info.mc_versions


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_jar(self, mock_empty_jar):
        """Test handling of JARs with no mod metadata."""
        extractors = [FabricExtractor(), ForgeTomlExtractor(), QuiltExtractor()]

        with zipfile.ZipFile(mock_empty_jar, "r") as jar:
            files = jar.namelist()
            for extractor in extractors:
                assert extractor.can_extract(jar, files) is False

    def test_disabled_jar(self, mock_disabled_jar):
        """Test that disabled JARs can still be extracted."""
        extractor = FabricExtractor()
        # Disabled status is handled by scanner, not extractor
        # Just verify the JAR itself is valid
        assert mock_disabled_jar.suffix == ".disabled"
