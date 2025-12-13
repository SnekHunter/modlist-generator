"""Pytest configuration and shared fixtures."""
import json
import zipfile
from pathlib import Path
from typing import Dict, Any
import pytest
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def mock_fabric_jar(temp_dir: Path) -> Path:
    """Create a mock Fabric mod JAR file."""
    jar_path = temp_dir / "test-fabric-mod.jar"

    fabric_metadata = {
        "schemaVersion": 1,
        "id": "test_mod",
        "version": "1.0.0",
        "name": "Test Fabric Mod",
        "description": "A test mod for unit testing",
        "authors": ["TestAuthor"],
        "contact": {"homepage": "https://example.com"},
        "depends": {"fabricloader": ">=0.14.0", "minecraft": "1.20.x"},
    }

    with zipfile.ZipFile(jar_path, "w") as jar:
        jar.writestr("fabric.mod.json", json.dumps(fabric_metadata, indent=2))
        jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")

    return jar_path


@pytest.fixture
def mock_forge_jar(temp_dir: Path) -> Path:
    """Create a mock Forge mod JAR file."""
    jar_path = temp_dir / "test-forge-mod.jar"

    forge_metadata = """
[[mods]]
modId="test_forge_mod"
version="2.0.0"
displayName="Test Forge Mod"
description='''A test Forge mod'''
authors="ForgeAuthor"

[[dependencies.test_forge_mod]]
modId="forge"
mandatory=true
versionRange="[40,)"

[[dependencies.test_forge_mod]]
modId="minecraft"
mandatory=true
versionRange="[1.19.2,1.20)"
"""

    with zipfile.ZipFile(jar_path, "w") as jar:
        jar.writestr("META-INF/mods.toml", forge_metadata)
        jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")

    return jar_path


@pytest.fixture
def mock_quilt_jar(temp_dir: Path) -> Path:
    """Create a mock Quilt mod JAR file."""
    jar_path = temp_dir / "test-quilt-mod.jar"

    quilt_metadata = {
        "schema_version": 1,
        "quilt_loader": {
            "group": "com.example",
            "id": "test_quilt_mod",
            "version": "1.5.0",
            "metadata": {
                "name": "Test Quilt Mod",
                "description": "A test Quilt mod",
                "contributors": {"QuiltAuthor": "Owner"},
            },
            "depends": [
                {"id": "quilt_loader", "versions": ">=0.17.0"},
                {"id": "minecraft", "versions": "1.20.x"},
            ],
        },
    }

    with zipfile.ZipFile(jar_path, "w") as jar:
        jar.writestr("quilt.mod.json", json.dumps(quilt_metadata, indent=2))
        jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")

    return jar_path


@pytest.fixture
def mock_disabled_jar(mock_fabric_jar: Path) -> Path:
    """Create a disabled JAR file."""
    disabled_path = mock_fabric_jar.with_suffix(".jar.disabled")
    shutil.copy(mock_fabric_jar, disabled_path)
    return disabled_path


@pytest.fixture
def mock_corrupted_jar(temp_dir: Path) -> Path:
    """Create a corrupted JAR file."""
    jar_path = temp_dir / "corrupted.jar"
    jar_path.write_bytes(b"This is not a valid ZIP file")
    return jar_path


@pytest.fixture
def mock_empty_jar(temp_dir: Path) -> Path:
    """Create an empty JAR with no metadata."""
    jar_path = temp_dir / "empty.jar"

    with zipfile.ZipFile(jar_path, "w") as jar:
        jar.writestr("some_random_file.txt", "No metadata here")

    return jar_path


@pytest.fixture
def mock_mods_folder(
    temp_dir: Path,
    mock_fabric_jar: Path,
    mock_forge_jar: Path,
    mock_quilt_jar: Path,
    mock_disabled_jar: Path,
) -> Path:
    """Create a folder with multiple mock mods."""
    mods_folder = temp_dir / "mods"
    mods_folder.mkdir()

    # Copy mocks to mods folder
    shutil.copy(mock_fabric_jar, mods_folder / "fabric-mod.jar")
    shutil.copy(mock_forge_jar, mods_folder / "forge-mod.jar")
    shutil.copy(mock_quilt_jar, mods_folder / "quilt-mod.jar")
    shutil.copy(mock_disabled_jar, mods_folder / "disabled-mod.jar.disabled")

    return mods_folder
