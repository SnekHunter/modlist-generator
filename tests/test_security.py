"""Tests for security module."""
import pytest
import zipfile
from pathlib import Path
import tempfile
import shutil

from src import security
from src.security import (
    SecurityError,
    PathTraversalError,
    ZipBombError,
    ResourceLimitError,
    validate_path,
    validate_zip_entry,
    validate_jar_file,
    safe_extract_file,
    validate_folder_path,
    get_safe_jar_files,
)


def test_validate_path_valid(temp_dir):
    """Test path validation with valid path."""
    test_path = temp_dir / "test.txt"
    test_path.touch()

    validated = validate_path(test_path)
    assert validated.exists()
    assert validated.is_absolute()


def test_validate_path_nonexistent():
    """Test path validation with nonexistent path."""
    with pytest.raises(PathTraversalError):
        validate_path(Path("/nonexistent/path/to/file.txt"))


def test_validate_zip_entry_safe():
    """Test ZIP entry validation with safe paths."""
    assert validate_zip_entry("fabric.mod.json") is True
    assert validate_zip_entry("META-INF/mods.toml") is True
    assert validate_zip_entry("com/example/MyMod.class") is True


def test_validate_zip_entry_path_traversal():
    """Test ZIP entry validation detects path traversal."""
    assert validate_zip_entry("../etc/passwd") is False
    assert validate_zip_entry("../../secrets.txt") is False
    assert validate_zip_entry("subdir/../../../evil.txt") is False
    assert validate_zip_entry("..\\windows\\system32\\config.sys") is False


def test_validate_zip_entry_absolute():
    """Test ZIP entry validation detects absolute paths."""
    assert validate_zip_entry("/etc/passwd") is False
    assert validate_zip_entry("C:\\Windows\\System32\\evil.dll") is False


def test_validate_jar_file_valid(mock_fabric_jar):
    """Test JAR validation with valid file."""
    is_valid, error = validate_jar_file(mock_fabric_jar)
    assert is_valid is True
    assert error is None


def test_validate_jar_file_empty(temp_dir):
    """Test JAR validation with empty file."""
    empty_jar = temp_dir / "empty.jar"
    empty_jar.touch()

    is_valid, error = validate_jar_file(empty_jar)
    assert is_valid is False
    assert "empty" in error.lower()


def test_validate_jar_file_not_zip(temp_dir):
    """Test JAR validation with non-ZIP file."""
    fake_jar = temp_dir / "fake.jar"
    fake_jar.write_text("This is not a ZIP file")

    is_valid, error = validate_jar_file(fake_jar)
    assert is_valid is False
    assert "zip" in error.lower() or "jar" in error.lower()


def test_validate_jar_file_too_large(temp_dir):
    """Test JAR validation with file exceeding size limit."""
    large_jar = temp_dir / "large.jar"

    # Create a JAR with total uncompressed size exceeding limit
    with zipfile.ZipFile(large_jar, "w", zipfile.ZIP_STORED) as jar:
        # Add a file with uncompressed size larger than limit
        large_content = b"X" * (security.MAX_DECOMPRESSED_SIZE + 1)
        jar.writestr("huge_file.bin", large_content)

    is_valid, error = validate_jar_file(large_jar)
    assert is_valid is False
    assert "too large" in error.lower() or "decompressed" in error.lower()


def test_validate_jar_file_too_many_files(temp_dir):
    """Test JAR validation with too many files."""
    # This would be slow to test with actual MAX_FILES_IN_JAR
    # So we'll temporarily mock it
    original_max = security.MAX_FILES_IN_JAR
    try:
        security.MAX_FILES_IN_JAR = 5

        many_files_jar = temp_dir / "many_files.jar"
        with zipfile.ZipFile(many_files_jar, "w") as jar:
            for i in range(10):
                jar.writestr(f"file_{i}.txt", f"content {i}")

        is_valid, error = validate_jar_file(many_files_jar)
        assert is_valid is False
        assert "too many" in error.lower()
    finally:
        security.MAX_FILES_IN_JAR = original_max


def test_validate_jar_file_path_traversal_in_entries(temp_dir):
    """Test JAR validation detects path traversal in entry names."""
    evil_jar = temp_dir / "evil.jar"

    with zipfile.ZipFile(evil_jar, "w") as jar:
        jar.writestr("normal.txt", "normal content")
        # This will write the file but validation should catch it
        info = zipfile.ZipInfo("../../../etc/passwd")
        jar.writestr(info, "evil content")

    is_valid, error = validate_jar_file(evil_jar)
    assert is_valid is False
    assert "unsafe path" in error.lower() or "path" in error.lower()


def test_safe_extract_file_valid(mock_fabric_jar):
    """Test safe extraction of valid file."""
    with zipfile.ZipFile(mock_fabric_jar, "r") as jar:
        content = safe_extract_file(jar, "fabric.mod.json")
        assert content is not None
        assert b"test_mod" in content or b"Test Fabric Mod" in content


def test_safe_extract_file_path_traversal():
    """Test safe extraction rejects path traversal."""
    temp_dir = tempfile.mkdtemp()
    try:
        evil_jar = Path(temp_dir) / "evil.jar"

        with zipfile.ZipFile(evil_jar, "w") as jar:
            info = zipfile.ZipInfo("../../evil.txt")
            jar.writestr(info, "evil content")

        with zipfile.ZipFile(evil_jar, "r") as jar:
            content = safe_extract_file(jar, "../../evil.txt")
            assert content is None
    finally:
        shutil.rmtree(temp_dir)


def test_safe_extract_file_too_large():
    """Test safe extraction rejects oversized files."""
    temp_dir = tempfile.mkdtemp()
    try:
        large_jar = Path(temp_dir) / "large.jar"

        # Create a file and test with small max_size
        large_content = b"X" * 2000
        with zipfile.ZipFile(large_jar, "w", zipfile.ZIP_STORED) as jar:
            jar.writestr("large_file.bin", large_content)

        with zipfile.ZipFile(large_jar, "r") as jar:
            # Use max_size smaller than file size
            with pytest.raises(ResourceLimitError):
                safe_extract_file(jar, "large_file.bin", max_size=1000)
    finally:
        shutil.rmtree(temp_dir)


def test_safe_extract_file_nonexistent(mock_fabric_jar):
    """Test safe extraction with nonexistent file."""
    with zipfile.ZipFile(mock_fabric_jar, "r") as jar:
        content = safe_extract_file(jar, "nonexistent.json")
        assert content is None


def test_validate_folder_path_valid(temp_dir):
    """Test folder path validation with valid directory."""
    validated = validate_folder_path(temp_dir)
    assert validated.exists()
    assert validated.is_dir()


def test_validate_folder_path_file(temp_dir):
    """Test folder path validation with file instead of directory."""
    file_path = temp_dir / "file.txt"
    file_path.touch()

    with pytest.raises(ValueError, match="Not a directory"):
        validate_folder_path(file_path)


def test_validate_folder_path_nonexistent():
    """Test folder path validation with nonexistent path."""
    with pytest.raises(PathTraversalError):
        validate_folder_path(Path("/nonexistent/directory"))


def test_get_safe_jar_files(mock_mods_folder):
    """Test getting safe JAR files from folder."""
    jar_files = get_safe_jar_files(mock_mods_folder, recursive=False)

    # Should find valid JAR files, exclude corrupted/invalid ones
    assert len(jar_files) > 0
    assert all(f.suffix == ".jar" for f in jar_files)
    assert all(f.exists() for f in jar_files)


def test_get_safe_jar_files_recursive(temp_dir):
    """Test recursive JAR file discovery."""
    # Create nested structure
    subdir = temp_dir / "mods" / "optional"
    subdir.mkdir(parents=True)

    # Create JARs at different levels
    jar1 = temp_dir / "mod1.jar"
    jar2 = subdir / "mod2.jar"

    with zipfile.ZipFile(jar1, "w") as jar:
        jar.writestr("fabric.mod.json", '{"id": "mod1"}')

    with zipfile.ZipFile(jar2, "w") as jar:
        jar.writestr("fabric.mod.json", '{"id": "mod2"}')

    jar_files = get_safe_jar_files(temp_dir, recursive=True)
    assert len(jar_files) == 2

    jar_files_non_recursive = get_safe_jar_files(temp_dir, recursive=False)
    assert len(jar_files_non_recursive) == 1


def test_get_safe_jar_files_excludes_invalid(temp_dir):
    """Test that invalid/unsafe JARs are excluded."""
    # Create valid JAR
    valid_jar = temp_dir / "valid.jar"
    with zipfile.ZipFile(valid_jar, "w") as jar:
        jar.writestr("fabric.mod.json", '{"id": "valid"}')

    # Create invalid JAR (not a ZIP)
    invalid_jar = temp_dir / "invalid.jar"
    invalid_jar.write_text("not a zip file")

    # Create empty JAR
    empty_jar = temp_dir / "empty.jar"
    empty_jar.touch()

    jar_files = get_safe_jar_files(temp_dir)

    # Should only include valid JAR
    assert len(jar_files) == 1
    assert jar_files[0].name == "valid.jar"


@pytest.mark.parametrize(
    "forbidden_path",
    [
        "/etc",
        "/sys",
        "/proc",
        "/dev",
    ],
)
def test_validate_path_forbidden_dirs(forbidden_path):
    """Test that forbidden system directories are rejected."""
    forbidden = Path(forbidden_path)

    # Only test if the directory actually exists on this system
    if forbidden.exists():
        with pytest.raises(PathTraversalError, match="forbidden"):
            validate_path(forbidden)
