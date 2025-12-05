"""
Base extractor class and utilities for mod metadata extraction.
"""

import re
import zipfile
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List

from ..models import ModInfo

logger = logging.getLogger(__name__)


# Regex patterns for parsing Minecraft version constraints
MC_VERSION_PATTERNS = [
    # Exact version: 1.20.1
    re.compile(r'^(\d+\.\d+(?:\.\d+)?)$'),
    # Semver range: >=1.20 <1.21, >=1.20.1
    re.compile(r'[><=~^]*\s*(\d+\.\d+(?:\.\d+)?)'),
    # Maven range: [1.20,1.21), [1.20.1,)
    re.compile(r'[\[\(](\d+\.\d+(?:\.\d+)?)\s*,'),
    re.compile(r',\s*(\d+\.\d+(?:\.\d+)?)[\]\)]'),
    # Wildcard: 1.20.x, 1.20.*
    re.compile(r'(\d+\.\d+)(?:\.[x*])?'),
]


class BaseExtractor(ABC):
    """Abstract base class for mod metadata extractors."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the extractor."""
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """Priority for extraction order (lower = higher priority)."""
        pass
    
    @abstractmethod
    def can_extract(self, jar: zipfile.ZipFile, files: List[str]) -> bool:
        """Check if this extractor can handle the given JAR file."""
        pass
    
    @abstractmethod
    def extract(self, jar: zipfile.ZipFile, jar_path: Path, files: List[str]) -> Optional[ModInfo]:
        """Extract mod information from the JAR file."""
        pass
    
    def _safe_decode(self, content: bytes, encoding: str = 'utf-8') -> str:
        """Safely decode bytes to string."""
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            return content.decode('latin-1')
    
    def _extract_dependencies(self, data: dict, dep_fields: List[str]) -> List[str]:
        """Extract dependency list from metadata."""
        dependencies = []
        for field in dep_fields:
            if field in data:
                deps = data[field]
                if isinstance(deps, dict):
                    dependencies.extend(deps.keys())
                elif isinstance(deps, list):
                    for dep in deps:
                        if isinstance(dep, str):
                            dependencies.append(dep)
                        elif isinstance(dep, dict):
                            dep_id = dep.get('modId') or dep.get('id') or dep.get('mod_id')
                            if dep_id:
                                dependencies.append(dep_id)
        return dependencies
    
    def _normalize_authors(self, authors) -> Optional[str]:
        """
        Normalize authors to a comma-separated string.
        
        Handles:
        - String: "Author Name"
        - List of strings: ["Author1", "Author2"]
        - List of objects: [{"name": "Author1"}, {"name": "Author2"}]
        """
        if not authors:
            return None
        
        if isinstance(authors, str):
            return authors.strip() if authors.strip() else None
        
        if isinstance(authors, list):
            names = []
            for author in authors:
                if isinstance(author, str):
                    if author.strip():
                        names.append(author.strip())
                elif isinstance(author, dict):
                    # Extract name from object format
                    name = author.get('name') or author.get('username') or author.get('id')
                    if name and isinstance(name, str) and name.strip():
                        names.append(name.strip())
            return ', '.join(names) if names else None
        
        return None
    
    def _parse_mc_versions(self, version_constraint) -> List[str]:
        """
        Parse Minecraft version constraint into list of versions.
        
        Handles common formats:
        - Exact: "1.20.1"
        - Semver: ">=1.20 <1.21", "~1.20.1", "^1.20"
        - Maven: "[1.20,1.21)", "[1.20.1,)"
        - Wildcard: "1.20.x", "1.20.*"
        """
        if not version_constraint:
            return []
        
        if isinstance(version_constraint, list):
            # Recursively parse list items
            versions = []
            for item in version_constraint:
                versions.extend(self._parse_mc_versions(item))
            return list(set(versions))
        
        if not isinstance(version_constraint, str):
            return []
        
        versions = set()
        constraint = version_constraint.strip()
        
        # Extract all version numbers from the constraint
        for pattern in MC_VERSION_PATTERNS:
            for match in pattern.finditer(constraint):
                version = match.group(1)
                if version:
                    # Normalize: ensure at least major.minor format
                    parts = version.split('.')
                    if len(parts) >= 2:
                        versions.add(version)
        
        return sorted(versions)
        return dependencies
