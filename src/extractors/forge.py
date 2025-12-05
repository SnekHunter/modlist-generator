"""
Forge and NeoForge mod metadata extractors.
"""

import json
import zipfile
import logging
from pathlib import Path
from typing import Optional, List, Tuple

from .base import BaseExtractor
from ..models import ModInfo

logger = logging.getLogger(__name__)

# Try to import tomllib (Python 3.11+), fallback to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None
        logger.warning("TOML parsing not available. Install 'tomli' for full Forge/NeoForge support.")


class ForgeTomlExtractor(BaseExtractor):
    """Extractor for modern Forge/NeoForge mods (META-INF/mods.toml or neoforge.mods.toml)."""
    
    TOML_FILES = ['META-INF/neoforge.mods.toml', 'META-INF/mods.toml']
    
    @property
    def name(self) -> str:
        return "Forge/NeoForge TOML"
    
    @property
    def priority(self) -> int:
        return 3
    
    def can_extract(self, jar: zipfile.ZipFile, files: List[str]) -> bool:
        if tomllib is None:
            return False
        return any(toml_file in files for toml_file in self.TOML_FILES)
    
    def _find_toml_file(self, files: List[str]) -> Optional[str]:
        """Find the TOML metadata file, preferring neoforge.mods.toml."""
        for toml_file in self.TOML_FILES:
            if toml_file in files:
                return toml_file
        return None
    
    def _detect_loader(self, toml_file: str, data: dict, jar_path: Path) -> str:
        """
        Detect loader type with improved heuristics.
        
        Priority:
        1. File is neoforge.mods.toml -> neoforge
        2. modLoader field contains 'neoforge' -> neoforge
        3. Dependencies contain 'neoforge' -> neoforge
        4. Filename contains 'neoforge' -> neoforge
        5. loaderVersion contains 'neoforge' -> neoforge
        6. Default to forge
        """
        # Check filename of TOML file
        if 'neoforge.mods.toml' in toml_file:
            return 'neoforge'
        
        # Check modLoader field
        mod_loader = data.get('modLoader', '').lower()
        if 'neoforge' in mod_loader:
            return 'neoforge'
        
        # Check dependencies for neoforge
        dependencies = data.get('dependencies', {})
        if isinstance(dependencies, dict):
            for mod_deps in dependencies.values():
                if isinstance(mod_deps, list):
                    for dep in mod_deps:
                        if isinstance(dep, dict):
                            mod_id = dep.get('modId', '').lower()
                            if mod_id == 'neoforge':
                                return 'neoforge'
        
        # Check mods array for neoforge dependency declarations
        mods = data.get('mods', [])
        if mods:
            mod_id = mods[0].get('modId', '').lower()
            if mod_id in dependencies:
                mod_deps = dependencies[mod_id]
                if isinstance(mod_deps, list):
                    for dep in mod_deps:
                        if isinstance(dep, dict) and dep.get('modId', '').lower() == 'neoforge':
                            return 'neoforge'
        
        # Check JAR filename for hints
        jar_name = jar_path.name.lower()
        if 'neoforge' in jar_name:
            return 'neoforge'
        
        # Check loaderVersion
        loader_version = data.get('loaderVersion', '').lower()
        if 'neoforge' in loader_version:
            return 'neoforge'
        
        # Default to forge
        return 'forge'
    
    def _extract_dependencies_from_toml(self, data: dict, mod_id: str) -> List[str]:
        """Extract dependencies from TOML structure."""
        dependencies = []
        deps_section = data.get('dependencies', {})
        
        # Dependencies can be keyed by mod_id or in a list
        if isinstance(deps_section, dict):
            # Check for dependencies under the mod's ID
            mod_deps = deps_section.get(mod_id, [])
            if isinstance(mod_deps, list):
                for dep in mod_deps:
                    if isinstance(dep, dict):
                        dep_id = dep.get('modId', '')
                        # Skip minecraft, forge, neoforge as they're implicit
                        if dep_id and dep_id not in ['minecraft', 'forge', 'neoforge']:
                            dependencies.append(dep_id)
        
        return dependencies
    
    def _extract_mc_versions_from_toml(self, data: dict, mod_id: str) -> List[str]:
        """Extract Minecraft version constraint from TOML dependencies."""
        deps_section = data.get('dependencies', {})
        
        if isinstance(deps_section, dict):
            # Check for minecraft dependency under the mod's ID
            mod_deps = deps_section.get(mod_id, [])
            if isinstance(mod_deps, list):
                for dep in mod_deps:
                    if isinstance(dep, dict) and dep.get('modId', '').lower() == 'minecraft':
                        version_range = dep.get('versionRange', '')
                        return self._parse_mc_versions(version_range)
        
        return []
    
    def extract(self, jar: zipfile.ZipFile, jar_path: Path, files: List[str]) -> Optional[ModInfo]:
        toml_file = self._find_toml_file(files)
        if not toml_file:
            return None
        
        try:
            with jar.open(toml_file) as f:
                content = self._safe_decode(f.read())
                data = tomllib.loads(content)
                
                # Get the first mod entry
                mods = data.get('mods', [])
                if not mods:
                    logger.warning(f"No mods array found in {toml_file} for {jar_path.name}")
                    return None
                
                mod = mods[0]
                mod_id = mod.get('modId', '')
                name = mod.get('displayName', mod.get('modId', jar_path.stem))
                version = mod.get('version', 'Unknown')
                
                # Handle version placeholders
                if version.startswith('${') and version.endswith('}'):
                    # Try to find version in JAR manifest
                    version = self._get_version_from_manifest(jar, files) or version
                
                # Detect loader type
                loader = self._detect_loader(toml_file, data, jar_path)
                
                # Extract dependencies
                dependencies = self._extract_dependencies_from_toml(data, mod_id)
                
                # Extract author (string field in TOML)
                author = mod.get('authors')
                if isinstance(author, str):
                    author = author.strip() or None
                else:
                    author = None
                
                # Extract description
                description = mod.get('description')
                if isinstance(description, str):
                    description = description.strip() or None
                else:
                    description = None
                
                # Extract Minecraft versions
                mc_versions = self._extract_mc_versions_from_toml(data, mod_id)
                
                logger.debug(f"Extracted {loader.capitalize()} mod: {name} v{version}")
                return ModInfo(
                    name=name,
                    loader=loader,
                    version=version,
                    filename=jar_path.name,
                    mod_id=mod_id,
                    dependencies=dependencies,
                    author=author,
                    description=description,
                    mc_versions=mc_versions
                )
                
        except Exception as e:
            logger.error(f"Error extracting Forge/NeoForge mod info from {jar_path.name}: {e}")
        
        return None
    
    def _get_version_from_manifest(self, jar: zipfile.ZipFile, files: List[str]) -> Optional[str]:
        """Try to extract version from JAR manifest."""
        if 'META-INF/MANIFEST.MF' not in files:
            return None
        
        try:
            with jar.open('META-INF/MANIFEST.MF') as f:
                content = self._safe_decode(f.read())
                for line in content.split('\n'):
                    line = line.strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        if key.strip() == 'Implementation-Version':
                            return value.strip()
        except Exception:
            pass
        
        return None


class LegacyForgeExtractor(BaseExtractor):
    """Extractor for legacy Forge mods (mcmod.info)."""
    
    METADATA_FILE = 'mcmod.info'
    
    @property
    def name(self) -> str:
        return "Legacy Forge"
    
    @property
    def priority(self) -> int:
        return 4
    
    def can_extract(self, jar: zipfile.ZipFile, files: List[str]) -> bool:
        return self.METADATA_FILE in files
    
    def extract(self, jar: zipfile.ZipFile, jar_path: Path, files: List[str]) -> Optional[ModInfo]:
        try:
            with jar.open(self.METADATA_FILE) as f:
                content = self._safe_decode(f.read())
                data = json.loads(content)
                
                # mcmod.info can be an array or object
                if isinstance(data, list) and data:
                    mod = data[0]
                elif isinstance(data, dict):
                    # Sometimes wrapped in 'modList' key
                    if 'modList' in data and isinstance(data['modList'], list):
                        mod = data['modList'][0] if data['modList'] else {}
                    else:
                        mod = data
                else:
                    logger.warning(f"Invalid mcmod.info format in {jar_path.name}")
                    return None
                
                mod_id = mod.get('modid', '')
                name = mod.get('name', mod.get('modid', jar_path.stem))
                version = mod.get('version', 'Unknown')
                
                # Extract dependencies
                dependencies = []
                deps = mod.get('dependencies', []) or mod.get('requiredMods', [])
                if isinstance(deps, list):
                    dependencies = [d for d in deps if isinstance(d, str)]
                
                # Extract author (can be string or list)
                author = self._normalize_authors(mod.get('authorList') or mod.get('authors'))
                
                # Extract description
                description = mod.get('description')
                if isinstance(description, str):
                    description = description.strip() or None
                else:
                    description = None
                
                # Extract Minecraft version
                mc_versions = []
                mc_version = mod.get('mcversion')
                if mc_version and isinstance(mc_version, str):
                    mc_versions = self._parse_mc_versions(mc_version)
                
                logger.debug(f"Extracted Legacy Forge mod: {name} v{version}")
                return ModInfo(
                    name=name,
                    loader='forge',
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
            logger.error(f"Error extracting Legacy Forge mod info from {jar_path.name}: {e}")
        
        return None
