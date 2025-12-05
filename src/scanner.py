"""
Core scanner module with parallel processing support.
"""

import zipfile
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

from .models import ModInfo, ScanResult
from .extractors import ALL_EXTRACTORS

logger = logging.getLogger(__name__)


class ModScanner:
    """Scanner for extracting mod information from JAR files."""
    
    def __init__(self, workers: int = 4, extractors: Optional[List] = None):
        """
        Initialize the scanner.
        
        Args:
            workers: Number of parallel workers for processing
            extractors: List of extractors to use (defaults to all)
        """
        self.workers = workers
        self.extractors = extractors or ALL_EXTRACTORS
        # Sort by priority
        self.extractors = sorted(self.extractors, key=lambda e: e.priority)
    
    def _extract_single_mod(self, jar_path: Path, disabled: bool = False) -> Tuple[Optional[ModInfo], Optional[str]]:
        """
        Extract mod info from a single JAR file.
        
        Args:
            jar_path: Path to the JAR file
            disabled: Whether this is a .jar.disabled file
        
        Returns:
            Tuple of (ModInfo or None, error message or None)
        """
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                files = jar.namelist()
                
                # Try each extractor in priority order
                for extractor in self.extractors:
                    if extractor.can_extract(jar, files):
                        logger.debug(f"Using {extractor.name} extractor for {jar_path.name}")
                        mod_info = extractor.extract(jar, jar_path, files)
                        if mod_info:
                            # Add disabled flag if needed
                            if disabled:
                                mod_info = ModInfo(
                                    name=mod_info.name,
                                    loader=mod_info.loader,
                                    version=mod_info.version,
                                    filename=mod_info.filename,
                                    mod_id=mod_info.mod_id,
                                    dependencies=mod_info.dependencies,
                                    author=mod_info.author,
                                    description=mod_info.description,
                                    mc_versions=mod_info.mc_versions,
                                    disabled=True
                                )
                            return (mod_info, None)
                
                # Fallback: try alternative extraction methods
                mod_info = self._fallback_extraction(jar, jar_path, files)
                if mod_info:
                    if disabled:
                        mod_info = ModInfo(
                            name=mod_info.name,
                            loader=mod_info.loader,
                            version=mod_info.version,
                            filename=mod_info.filename,
                            mod_id=mod_info.mod_id,
                            dependencies=mod_info.dependencies,
                            author=mod_info.author,
                            description=mod_info.description,
                            mc_versions=mod_info.mc_versions,
                            disabled=True
                        )
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
        progress_callback=None
    ) -> ScanResult:
        """
        Scan a folder for mod JAR files.
        
        Args:
            folder_path: Path to the folder to scan
            recursive: Whether to scan subdirectories
            exclude_patterns: List of glob patterns to exclude
            include_disabled: Whether to include .jar.disabled files
            progress_callback: Optional callback for progress updates (current, total, filename)
        
        Returns:
            ScanResult containing all extracted mod information
        """
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
        
        # Process files in parallel
        completed = 0
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
                
                if progress_callback:
                    progress_callback(completed, len(all_files), jar_path.name)
                
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
