"""Security utilities for safe JAR file processing."""
import os
import zipfile
from pathlib import Path
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

# Security limits
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB per file
MAX_DECOMPRESSED_SIZE = 500 * 1024 * 1024  # 500MB total decompressed
MAX_FILES_IN_JAR = 10000  # Maximum files in a JAR
MAX_PATH_LENGTH = 1000  # Maximum path length

# Forbidden system directories
FORBIDDEN_DIRS = [
    Path("/etc"),
    Path("/sys"),
    Path("/proc"),
    Path("/dev"),
    Path("C:\\Windows"),
    Path("C:\\System32"),
    Path("/System"),
    Path("/Library/System"),
]


class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass


class PathTraversalError(SecurityError):
    """Exception raised when path traversal is detected."""
    pass


class ZipBombError(SecurityError):
    """Exception raised when a ZIP bomb is detected."""
    pass


class ResourceLimitError(SecurityError):
    """Exception raised when resource limits are exceeded."""
    pass


def validate_path(path: Path) -> Path:
    """Validate that a path is safe to access.
    
    Args:
        path: Path to validate
        
    Returns:
        Resolved absolute path
        
    Raises:
        PathTraversalError: If path is unsafe
        FileNotFoundError: If path doesn't exist
    """
    try:
        # Resolve to absolute path
        resolved = path.resolve()
        
        # Check if path exists
        if not resolved.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        
        # Check path length
        if len(str(resolved)) > MAX_PATH_LENGTH:
            raise PathTraversalError(f"Path too long: {len(str(resolved))} > {MAX_PATH_LENGTH}")
        
        # Check if it's in a forbidden directory
        for forbidden in FORBIDDEN_DIRS:
            if forbidden.exists():
                try:
                    resolved.relative_to(forbidden)
                    raise PathTraversalError(f"Access to system directory forbidden: {forbidden}")
                except ValueError:
                    # Not a subdirectory, continue checking
                    pass
        
        return resolved
        
    except (OSError, RuntimeError) as e:
        raise PathTraversalError(f"Path validation failed: {e}")


def validate_zip_entry(entry_path: str) -> bool:
    """Validate that a ZIP entry path is safe.
    
    Args:
        entry_path: Path within ZIP file
        
    Returns:
        True if safe, False otherwise
    """
    # Normalize path
    normalized = os.path.normpath(entry_path)
    
    # Check for parent directory references
    if normalized.startswith("..") or "/.." in normalized or "\\.." in normalized:
        logger.warning(f"Path traversal attempt detected: {entry_path}")
        return False
    
    # Check for absolute paths
    if os.path.isabs(normalized):
        logger.warning(f"Absolute path in ZIP detected: {entry_path}")
        return False
    
    # Check path length
    if len(normalized) > MAX_PATH_LENGTH:
        logger.warning(f"Path too long in ZIP: {len(normalized)} > {MAX_PATH_LENGTH}")
        return False
    
    return True


def validate_jar_file(jar_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate that a JAR file is safe to process.
    
    Args:
        jar_path: Path to JAR file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file size
    try:
        file_size = jar_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return (False, f"File too large: {file_size / (1024*1024):.1f}MB > {MAX_FILE_SIZE / (1024*1024):.1f}MB")
        
        if file_size == 0:
            return (False, "File is empty")
    
    except OSError as e:
        return (False, f"Cannot access file: {e}")
    
    # Try to open as ZIP and check contents
    try:
        with zipfile.ZipFile(jar_path, 'r') as jar:
            # Check number of files
            file_list = jar.namelist()
            if len(file_list) > MAX_FILES_IN_JAR:
                return (False, f"Too many files in JAR: {len(file_list)} > {MAX_FILES_IN_JAR}")
            
            # Check for path traversal in file names
            for entry_name in file_list:
                if not validate_zip_entry(entry_name):
                    return (False, f"Unsafe path in JAR: {entry_name}")
            
            # Check decompressed sizes
            total_size = 0
            for info in jar.infolist():
                if info.file_size > MAX_FILE_SIZE:
                    return (False, f"Decompressed file too large: {info.filename} ({info.file_size / (1024*1024):.1f}MB)")
                
                total_size += info.file_size
                if total_size > MAX_DECOMPRESSED_SIZE:
                    return (False, f"Total decompressed size too large: {total_size / (1024*1024):.1f}MB > {MAX_DECOMPRESSED_SIZE / (1024*1024):.1f}MB")
        
        return (True, None)
    
    except zipfile.BadZipFile:
        return (False, "Not a valid ZIP/JAR file")
    except Exception as e:
        return (False, f"Error validating JAR: {e}")


def safe_extract_file(jar: zipfile.ZipFile, entry_name: str, max_size: int = MAX_FILE_SIZE) -> Optional[bytes]:
    """Safely extract a file from a JAR with size limits.
    
    Args:
        jar: Open ZipFile object
        entry_name: Name of entry to extract
        max_size: Maximum size to read
        
    Returns:
        File contents as bytes, or None if unsafe
        
    Raises:
        ResourceLimitError: If file exceeds size limit
    """
    # Validate entry name
    if not validate_zip_entry(entry_name):
        logger.warning(f"Refusing to extract unsafe entry: {entry_name}")
        return None
    
    try:
        info = jar.getinfo(entry_name)
        
        # Check decompressed size
        if info.file_size > max_size:
            raise ResourceLimitError(f"File too large to extract: {info.file_size} > {max_size}")
        
        # Extract with size limit
        with jar.open(entry_name) as f:
            # Read in chunks to avoid memory exhaustion
            chunks = []
            total_read = 0
            chunk_size = 8192
            
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                total_read += len(chunk)
                if total_read > max_size:
                    raise ResourceLimitError(f"File exceeded size limit during extraction: {total_read} > {max_size}")
                
                chunks.append(chunk)
            
            return b''.join(chunks)
    
    except KeyError:
        logger.warning(f"Entry not found in JAR: {entry_name}")
        return None
    except Exception as e:
        logger.error(f"Error extracting {entry_name}: {e}")
        raise


def validate_folder_path(folder_path: Path) -> Path:
    """Validate that a folder path is safe for scanning.
    
    Args:
        folder_path: Path to folder
        
    Returns:
        Validated path
        
    Raises:
        ValueError: If path is invalid
        PathTraversalError: If path is unsafe
    """
    # Validate path
    resolved = validate_path(folder_path)
    
    # Check it's a directory
    if not resolved.is_dir():
        raise ValueError(f"Not a directory: {folder_path}")
    
    return resolved


def get_safe_jar_files(folder_path: Path, recursive: bool = False) -> List[Path]:
    """Get list of JAR files with security validation.
    
    Args:
        folder_path: Folder to scan
        recursive: Whether to scan recursively
        
    Returns:
        List of validated JAR file paths
    """
    validated_path = validate_folder_path(folder_path)
    
    pattern = "**/*.jar" if recursive else "*.jar"
    jar_files = []
    
    for jar_path in validated_path.glob(pattern):
        # Skip if path is too long
        if len(str(jar_path)) > MAX_PATH_LENGTH:
            logger.warning(f"Skipping file with path too long: {jar_path}")
            continue
        
        # Basic validation
        is_valid, error = validate_jar_file(jar_path)
        if not is_valid:
            logger.warning(f"Skipping invalid JAR {jar_path.name}: {error}")
            continue
        
        jar_files.append(jar_path)
    
    return jar_files
