"""
Output formatters for different export formats.
"""

import csv
import json
import io
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .models import ScanResult

logger = logging.getLogger(__name__)


class BaseFormatter(ABC):
    """Abstract base class for output formatters."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Format name."""
        pass
    
    @property
    @abstractmethod
    def extension(self) -> str:
        """Default file extension."""
        pass
    
    @abstractmethod
    def format(self, result: ScanResult, include_errors: bool = True, **kwargs) -> str:
        """Format the scan result as a string."""
        pass
    
    def save(self, result: ScanResult, output_path: Path, include_errors: bool = True, **kwargs) -> None:
        """Save formatted output to file."""
        content = self.format(result, include_errors, **kwargs)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Saved {self.name} output to {output_path}")


class JsonFormatter(BaseFormatter):
    """JSON output formatter."""
    
    @property
    def name(self) -> str:
        return "JSON"
    
    @property
    def extension(self) -> str:
        return ".json"
    
    def format(self, result: ScanResult, include_errors: bool = True, **kwargs) -> str:
        compact = kwargs.get('compact', False)
        indent = None if compact else 2
        return json.dumps(result.to_dict(include_errors), indent=indent, ensure_ascii=False)


class CsvFormatter(BaseFormatter):
    """CSV output formatter."""
    
    @property
    def name(self) -> str:
        return "CSV"
    
    @property
    def extension(self) -> str:
        return ".csv"
    
    def format(self, result: ScanResult, include_errors: bool = True, **kwargs) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header - now includes new fields
        writer.writerow(['Name', 'Loader', 'Version', 'Filename', 'Mod ID', 'Author', 'MC Versions', 'Disabled', 'Dependencies'])
        
        # Data rows
        for mod in result.mods:
            writer.writerow([
                mod.name,
                mod.loader,
                mod.version,
                mod.filename,
                mod.mod_id or '',
                mod.author or '',
                '; '.join(mod.mc_versions) if mod.mc_versions else '',
                'Yes' if mod.disabled else '',
                '; '.join(mod.dependencies) if mod.dependencies else ''
            ])
        
        return output.getvalue()


class MarkdownFormatter(BaseFormatter):
    """Markdown table output formatter."""
    
    @property
    def name(self) -> str:
        return "Markdown"
    
    @property
    def extension(self) -> str:
        return ".md"
    
    def format(self, result: ScanResult, include_errors: bool = True, **kwargs) -> str:
        lines = [
            f"# Modlist",
            f"",
            f"**Total Mods:** {len(result.mods)}  ",
            f"**Generated:** {result.generated_at or 'N/A'}  ",
            f"**Scan Duration:** {result.scan_duration:.2f}s  ",
            f"",
        ]
        
        # Count disabled mods
        disabled_count = sum(1 for mod in result.mods if mod.disabled)
        if disabled_count > 0:
            lines.append(f"**Disabled Mods:** {disabled_count}  ")
            lines.append(f"")
        
        # Count by MC version
        mc_version_counts = {}
        for mod in result.mods:
            for v in mod.mc_versions:
                mc_version_counts[v] = mc_version_counts.get(v, 0) + 1
        if mc_version_counts:
            mc_summary = ', '.join(f"{v} ({c})" for v, c in sorted(mc_version_counts.items()))
            lines.append(f"**MC Versions:** {mc_summary}  ")
            lines.append(f"")
        
        lines.extend([
            f"## Mods",
            f"",
            f"| Name | Loader | Version | Author | MC Version | Status |",
            f"|------|--------|---------|--------|------------|--------|",
        ])
        
        for mod in result.mods:
            # Escape pipe characters in values
            name = mod.name.replace('|', '\\|')
            author = (mod.author or '').replace('|', '\\|')[:30]  # Truncate long authors
            mc_ver = ', '.join(mod.mc_versions[:2]) if mod.mc_versions else '-'  # Show first 2
            status = '🔴 Disabled' if mod.disabled else '✅'
            lines.append(f"| {name} | {mod.loader} | {mod.version} | {author} | {mc_ver} | {status} |")
        
        if include_errors and result.errors:
            lines.extend([
                f"",
                f"## Errors ({len(result.errors)})",
                f"",
            ])
            for error in result.errors:
                lines.append(f"- {error}")
        
        return '\n'.join(lines)


class YamlFormatter(BaseFormatter):
    """YAML output formatter."""
    
    @property
    def name(self) -> str:
        return "YAML"
    
    @property
    def extension(self) -> str:
        return ".yaml"
    
    def format(self, result: ScanResult, include_errors: bool = True, **kwargs) -> str:
        # Simple YAML output without external dependency
        lines = [
            f"# Modlist Generator Output",
            f"total_mods: {len(result.mods)}",
            f"total_files_scanned: {result.total_files}",
            f"scan_duration_seconds: {result.scan_duration:.2f}",
            f"generated_at: \"{result.generated_at.isoformat() if result.generated_at else 'N/A'}\"",
            f"",
            f"mods:",
        ]
        
        for mod in result.mods:
            lines.extend([
                f"  - name: \"{mod.name}\"",
                f"    loader: {mod.loader}",
                f"    version: \"{mod.version}\"",
                f"    filename: \"{mod.filename}\"",
            ])
            if mod.mod_id:
                lines.append(f"    mod_id: \"{mod.mod_id}\"")
            if mod.author:
                # Escape quotes in author string
                author_escaped = mod.author.replace('"', '\\"')
                lines.append(f"    author: \"{author_escaped}\"")
            if mod.description:
                # Truncate long descriptions and escape quotes
                desc = mod.description[:200].replace('"', '\\"').replace('\n', ' ')
                lines.append(f"    description: \"{desc}\"")
            if mod.mc_versions:
                lines.append(f"    mc_versions: [{', '.join(f'\"{v}\"' for v in mod.mc_versions)}]")
            if mod.disabled:
                lines.append(f"    disabled: true")
            if mod.dependencies:
                lines.append(f"    dependencies: [{', '.join(f'\"{d}\"' for d in mod.dependencies)}]")
        
        if include_errors and result.errors:
            lines.extend([
                f"",
                f"errors:",
            ])
            for error in result.errors:
                error_escaped = error.replace('"', '\\"')
                lines.append(f"  - \"{error_escaped}\"")
        
        return '\n'.join(lines)


# Registry of available formatters
FORMATTERS = {
    'json': JsonFormatter(),
    'csv': CsvFormatter(),
    'markdown': MarkdownFormatter(),
    'md': MarkdownFormatter(),
    'yaml': YamlFormatter(),
    'yml': YamlFormatter(),
}


def get_formatter(format_name: str) -> Optional[BaseFormatter]:
    """Get formatter by name."""
    return FORMATTERS.get(format_name.lower())
