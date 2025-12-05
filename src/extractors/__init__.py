"""
Mod metadata extractors for various mod loaders.
"""

from .base import BaseExtractor
from .fabric import FabricExtractor
from .quilt import QuiltExtractor
from .forge import ForgeTomlExtractor, LegacyForgeExtractor

# All available extractors in priority order
ALL_EXTRACTORS = [
    FabricExtractor(),
    QuiltExtractor(),
    ForgeTomlExtractor(),
    LegacyForgeExtractor(),
]

__all__ = [
    'BaseExtractor',
    'FabricExtractor',
    'QuiltExtractor',
    'ForgeTomlExtractor',
    'LegacyForgeExtractor',
    'ALL_EXTRACTORS',
]
