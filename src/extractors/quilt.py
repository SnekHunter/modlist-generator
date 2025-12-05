"""
Quilt mod metadata extractor.
"""

import json
import zipfile
import logging
from pathlib import Path
from typing import Optional, List

from .base import BaseExtractor
from ..models import ModInfo

logger = logging.getLogger(__name__)


class QuiltExtractor(BaseExtractor):
    """Extractor for Quilt mods (quilt.mod.json)."""
    
    METADATA_FILE = 'quilt.mod.json'
    
    @property
    def name(self) -> str:
        return "Quilt"
    
    @property
    def priority(self) -> int:
        return 2
    
    def can_extract(self, jar: zipfile.ZipFile, files: List[str]) -> bool:
        return self.METADATA_FILE in files
    
    def extract(self, jar: zipfile.ZipFile, jar_path: Path, files: List[str]) -> Optional[ModInfo]:
        try:
            with jar.open(self.METADATA_FILE) as f:
                content = self._safe_decode(f.read())
                data = json.loads(content)
                
                # Quilt uses a nested structure under 'quilt_loader'
                quilt_loader = data.get('quilt_loader', {})
                metadata = quilt_loader.get('metadata', {})
                
                mod_id = quilt_loader.get('id', '')
                name = metadata.get('name', mod_id or jar_path.stem)
                version = quilt_loader.get('version', 'Unknown')
                
                # Extract dependencies
                dependencies = []
                mc_versions = []
                depends = quilt_loader.get('depends', [])
                if isinstance(depends, list):
                    for dep in depends:
                        if isinstance(dep, dict):
                            dep_id = dep.get('id')
                            if dep_id:
                                # Check for minecraft version
                                if dep_id == 'minecraft':
                                    versions = dep.get('versions') or dep.get('version')
                                    mc_versions = self._parse_mc_versions(versions)
                                else:
                                    dependencies.append(dep_id)
                        elif isinstance(dep, str):
                            dependencies.append(dep)
                
                # Extract author from metadata.contributors or metadata.authors
                author = None
                contributors = metadata.get('contributors')
                if contributors:
                    # Contributors can be dict {name: role} or list
                    if isinstance(contributors, dict):
                        author = ', '.join(contributors.keys())
                    else:
                        author = self._normalize_authors(contributors)
                if not author:
                    author = self._normalize_authors(metadata.get('authors'))
                
                # Extract description
                description = metadata.get('description')
                if isinstance(description, str):
                    description = description.strip() or None
                else:
                    description = None
                
                logger.debug(f"Extracted Quilt mod: {name} v{version}")
                return ModInfo(
                    name=name,
                    loader='quilt',
                    version=version,
                    filename=jar_path.name,
                    mod_id=mod_id,
                    dependencies=dependencies,
                    author=author,
                    description=description,
                    mc_versions=mc_versions
                )
                
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {self.METADATA_FILE} for {jar_path.name}: {e}")
        except Exception as e:
            logger.error(f"Error extracting Quilt mod info from {jar_path.name}: {e}")
        
        return None
