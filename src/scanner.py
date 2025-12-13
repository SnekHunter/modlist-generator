"""
Core scanner module with parallel processing support.
"""

import zipfile
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace, dataclass
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple, Protocol, Any

from .models import ModInfo, ScanResult
from .extractors import ALL_EXTRACTORS
from .cache import ScanCache
from . import security

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdate:
    """Progress update information."""
    current: int
    total: int
    filename: str
    percent: float
    
    def __post_init__(self) -> None:
        """Calculate percentage after initialization."""
        if self.total > 0:
            object.__setattr__(self, 'percent', (self.current / self.total) * 100)
        else:
            object.__setattr__(self, 'percent', 0.0)


class ProgressCallback(Protocol):
    """Protocol for progress callback functions."""
    def __call__(self, update: ProgressUpdate) -> None:
        """Called with progress updates.
        
        Args:
            update: ProgressUpdate with scan progress information
        """
        ...


class ModScanner:
    """Scanner for extracting mod information from JAR files."""
    
    def __init__(
        self,
        workers: int = 4,
        extractors: Optional[List[Any]] = None,
        cache: Optional[ScanCache] = None,
        use_cache: bool = False,
        progress_batch_size: int = 10,
        progress_batch_interval: float = 0.1
    ) -> None:
        """
        Initialize the scanner.
        
        Args:
            workers: Number of parallel workers for processing
            extractors: List of extractors to use (defaults to all)
            cache: Cache instance to use (optional)
            use_cache: Whether to use caching
            progress_batch_size: Update progress every N files
            progress_batch_interval: Update progress every N seconds (whichever comes first)
        """
        self.workers = workers
        self.extractors = extractors or ALL_EXTRACTORS
        # Sort by priority
        self.extractors = sorted(self.extractors, key=lambda e: e.priority)
        self.cache = cache
        self.use_cache = use_cache and cache is not None
        self.progress_batch_size = max(1, progress_batch_size)
        self.progress_batch_interval = max(0.01, progress_batch_interval)
    
    def _extract_single_mod(self, jar_path: Path, disabled: bool = False) -> Tuple[Optional[ModInfo], Optional[str]]:
        # Try cache first
        if self.use_cache and self.cache:
            cached = self.cache.get(jar_path)
            if cached:
                logger.debug(f"Cache hit: {jar_path.name}")
                # Apply disabled flag if needed
                if disabled and not cached.disabled:
                    cached = replace(cached, disabled=True)
                return (cached, None)
        
        # Validate JAR file for security
        is_valid, security_error = security.validate_jar_file(jar_path)
        if not is_valid:
            error_msg = f"Security validation failed: {security_error}"
            logger.warning(f"{jar_path.name}: {error_msg}")
            return (None, error_msg)
        
        # Extract normally
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                files = jar.namelist()
                
                # Try each extractor in priority order
                for extractor in self.extractors:
                    if extractor.can_extract(jar, files):
                        logger.debug(f"Using {extractor.name} extractor for {jar_path.name}")
                        mod_info, error = extractor.extract(jar, jar_path, files)
                        if mod_info:
                            # Add disabled flag if needed
                            if disabled:
                                mod_info = replace(mod_info, disabled=True)
                            
                            # Cache the result if extraction succeeded
                            if self.use_cache and self.cache:
                                self.cache.set(jar_path, mod_info)
                            
                            return (mod_info, error)
                
                # Fallback: try alternative extraction methods
                mod_info = self._fallback_extraction(jar, jar_path, files)
                if mod_info:
                    if disabled:
                        mod_info = replace(mod_info, disabled=True)
                    
                    # Cache the result if extraction succeeded
                    if self.use_cache and self.cache and mod_info:
                        self.cache.set(jar_path, mod_info)
                    
                    return (mod_info, None)
                
                # No metadata found - create basic info from filename
                logger.warning(f"No mod metadata found in {jar_path.name}")
                return (
                    ModInfo(
                        name=jar_path.stem,
                        loader='unknown',
                        version='Unknown',
                        filename=jar_path.name,
                        disabled=disabled
                    ),
                    f"No mod metadata found in {jar_path.name}"
                )
                
        except zipfile.BadZipFile:
            error = f"Invalid or corrupted JAR file: {jar_path.name}"
            logger.error(error)
            return (None, error)
        except security.SecurityError as e:
            error = f"Security error: {str(e)}"
            logger.error(f"{jar_path.name}: {error}")
            return (None, error)
        except Exception as e:
            error = f"Failed to process {jar_path.name}: {str(e)}"
            logger.error(error)
            return (None, error)
    
    def _fallback_extraction(self, jar: zipfile.ZipFile, jar_path: Path, files: List[str]) -> Optional[ModInfo]:
        """Fallback extraction using manifest or filename parsing."""
        # Try manifest
        if 'META-INF/MANIFEST.MF' in files:
            try:
                with jar.open('META-INF/MANIFEST.MF') as f:
                    content = f.read().decode('utf-8', errors='replace')
                    name = None
                    version = None
                    
                    for line in content.split('\n'):
                        line = line.strip()
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            
                            if key in ['Implementation-Title', 'Bundle-Name', 'Automatic-Module-Name']:
                                name = value
                            elif key in ['Implementation-Version', 'Bundle-Version']:
                                version = value
                    
                    if name and version:
                        # Try to detect loader from filename
                        loader = self._detect_loader_from_filename(jar_path.name)
                        return ModInfo(
                            name=name,
                            loader=loader,
                            version=version,
                            filename=jar_path.name
                        )
            except Exception as e:
                logger.debug(f"Manifest extraction failed for {jar_path.name}: {e}")
        
        return None
    
    def _detect_loader_from_filename(self, filename: str) -> str:
        """Detect loader type from filename hints."""
        filename_lower = filename.lower()
        
        if 'fabric' in filename_lower:
            return 'fabric'
        elif 'neoforge' in filename_lower:
            return 'neoforge'
        elif 'forge' in filename_lower:
            return 'forge'
        elif 'quilt' in filename_lower:
            return 'quilt'
        
        return 'unknown'
    
    def scan_folder(
        self,
        folder_path: Path,
        recursive: bool = False,
        exclude_patterns: Optional[List[str]] = None,
        include_disabled: bool = False,
        progress_callback: Optional[ProgressCallback] = None
    ) -> ScanResult:
        """
        Scan a folder for mod JAR files.
        
        Args:
            folder_path: Path to the folder to scan
            recursive: Whether to scan subdirectories
            exclude_patterns: List of glob patterns to exclude
            include_disabled: Whether to include .jar.disabled files
            progress_callback: Optional callback for progress updates
        
        Returns:
            ScanResult containing all extracted mod information
        """
        # Validate folder path for security
        try:
            folder_path = security.validate_folder_path(folder_path)
        except (ValueError, security.PathTraversalError) as e:
            logger.error(f"Invalid folder path: {e}")
            return ScanResult(total_files=0, errors=[str(e)])
        
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        if not folder_path.is_dir():
            raise ValueError(f"Path is not a directory: {folder_path}")
        
        # Find JAR files (both active and disabled)
        if recursive:
            jar_files = list(folder_path.rglob("*.jar"))
            if include_disabled:
                disabled_files = list(folder_path.rglob("*.jar.disabled"))
        else:
            jar_files = list(folder_path.glob("*.jar"))
            if include_disabled:
                disabled_files = list(folder_path.glob("*.jar.disabled"))
        
        # Track which files are disabled
        disabled_set = set(disabled_files) if include_disabled else set()
        all_files = jar_files + (disabled_files if include_disabled else [])
        
        # Apply exclusions
        if exclude_patterns:
            for pattern in exclude_patterns:
                excluded = set(folder_path.glob(pattern) if not recursive else folder_path.rglob(pattern))
                all_files = [f for f in all_files if f not in excluded]
        
        if not all_files:
            logger.warning(f"No JAR files found in {folder_path}")
            return ScanResult(total_files=0)
        
        logger.info(f"Found {len(all_files)} JAR file(s). Processing with {self.workers} workers...")
        
        result = ScanResult(total_files=len(all_files))
        start_time = time.time()
        
        # Process files in parallel with batched progress updates
        completed = 0
        last_progress_time = time.time()
        last_progress_count = 0
        current_filename = ""
        
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_jar = {
                executor.submit(
                    self._extract_single_mod, 
                    jar_path, 
                    jar_path in disabled_set
                ): jar_path
                for jar_path in all_files
            }
            
            for future in as_completed(future_to_jar):
                jar_path = future_to_jar[future]
                completed += 1
                current_filename = jar_path.name
                
                # Batched progress updates - only call callback if:
                # 1. Enough files processed since last update (batch_size), OR
                # 2. Enough time elapsed since last update (batch_interval), OR
                # 3. This is the last file
                should_update = (
                    (completed - last_progress_count) >= self.progress_batch_size or
                    (time.time() - last_progress_time) >= self.progress_batch_interval or
                    completed == len(all_files)
                )
                
                if progress_callback and should_update:
                    update = ProgressUpdate(
                        current=completed,
                        total=len(all_files),
                        filename=current_filename
                    )
                    progress_callback(update)
                    last_progress_time = time.time()
                    last_progress_count = completed
                
                try:
                    mod_info, error = future.result()
                    if mod_info:
                        result.mods.append(mod_info)
                    if error:
                        result.errors.append(error)
                except Exception as e:
                    error = f"Unexpected error processing {jar_path.name}: {str(e)}"
                    logger.error(error)
                    result.errors.append(error)
        
        result.scan_duration = time.time() - start_time
        result.generated_at = datetime.now()
        
        logger.info(f"Scan completed in {result.scan_duration:.2f}s. Found {len(result.mods)} mods.")
        
        return result
