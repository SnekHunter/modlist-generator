"""
Fabric mod metadata extractor.
"""

import json
import zipfile
import logging
from pathlib import Path
from typing import Optional, List, Tuple

from .base import BaseExtractor
from ..models import ModInfo
from .. import security

logger = logging.getLogger(__name__)


class FabricExtractor(BaseExtractor):
    """Extractor for Fabric mods (fabric.mod.json)."""
    
    METADATA_FILE = 'fabric.mod.json'
    
    @property
    def name(self) -> str:
        return "Fabric"
    
    @property
    def priority(self) -> int:
        return 1
    
    def can_extract(self, jar: zipfile.ZipFile, files: List[str]) -> bool:
        return self.METADATA_FILE in files
    
    def extract(self, jar: zipfile.ZipFile, jar_path: Path, files: List[str]) -> Tuple[Optional[ModInfo], Optional[str]]:
        try:
            # Safely extract with 1MB size limit for metadata files
            content_bytes = security.safe_extract_file(jar, self.METADATA_FILE, max_size=1024*1024)
            if content_bytes is None:
                return (None, f"Failed to safely extract {self.METADATA_FILE}")
            
            content = self._safe_decode(content_bytes)
            data = json.loads(content)
                
                mod_id = data.get('id', '')
                name = data.get('name', data.get('id', jar_path.stem))
                version = data.get('version', 'Unknown')
                
                # Extract dependencies
                dependencies = self._extract_dependencies(data, ['depends', 'recommends'])
                
                # Extract author (can be list of strings or objects)
                author = self._normalize_authors(data.get('authors'))
                
                # Extract description
                description = data.get('description')
                if isinstance(description, str):
                    description = description.strip() or None
                else:
                    description = None
                
                # Extract Minecraft version from depends.minecraft
                mc_versions = []
                depends = data.get('depends', {})
                if isinstance(depends, dict) and 'minecraft' in depends:
                    mc_versions = self._parse_mc_versions(depends['minecraft'])
                
                logger.debug(f"Extracted Fabric mod: {name} v{version}")
                return (ModInfo(
                    name=name,
                    loader='fabric',
                    version=version,
                    filename=jar_path.name,
                    mod_id=mod_id,
                    dependencies=dependencies,
                    author=author,
                    description=description,
                    mc_versions=mc_versions
                ), None)
                
        except json.JSONDecodeError as e:
            error = f"Invalid JSON in {self.METADATA_FILE} for {jar_path.name}: {e}"
            logger.warning(error)
            return (None, error)
        except Exception as e:
            error = f"Error extracting Fabric mod info from {jar_path.name}: {e}"
            logger.error(error)
            return (None, error)
