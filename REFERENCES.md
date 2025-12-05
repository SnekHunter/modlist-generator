# MODLIST GENERATOR - REFERENCES

## Project Overview

A Python program that extracts mod details from a folder containing Minecraft mod files (.jar) and outputs the information to multiple formats (JSON, CSV, Markdown, YAML). Version 2.0 features a modular architecture, parallel processing, and support for all major mod loaders.

## Version History

- **v1.0.0**: Initial release with basic extraction for Fabric, Forge, NeoForge
- **v2.0.0**: Complete rewrite with modular architecture, parallel processing, multiple output formats

## Features (v2.0)

- ✅ **Multi-loader support**: Fabric, Forge, NeoForge, Quilt, Legacy Forge
- ✅ **Parallel processing**: Configurable worker threads for fast scanning
- ✅ **Multiple output formats**: JSON, CSV, Markdown, YAML
- ✅ **Progress bars**: Rich terminal UI (optional)
- ✅ **Filtering & sorting**: By loader type, name, version, or filename
- ✅ **Duplicate detection**: Identify mods with same ID but different versions
- ✅ **Recursive scanning**: Scan subdirectories
- ✅ **Mod ID extraction**: Unique identifier for each mod
- ✅ **Dependency tracking**: Extract mod dependencies where available

## Requirements

- **Python**: 3.10+ (3.11+ recommended for built-in tomllib)
- **Input**: Folder containing mod files (.jar format)
- **Output**: JSON, CSV, Markdown, or YAML file with mod details

### Output Data Fields

| Field          | Description                                               |
| -------------- | --------------------------------------------------------- |
| `name`         | Display name of the mod                                   |
| `mod_id`       | Unique mod identifier                                     |
| `loader`       | Mod loader type (fabric, forge, neoforge, quilt, unknown) |
| `version`      | Mod version string                                        |
| `filename`     | Original JAR filename                                     |
| `dependencies` | List of required mods (where available)                   |

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Setup

```bash
# Clone or download the project
cd modlist-generator

# Install dependencies
pip install -r requirements.txt

# Optional: Install rich for enhanced terminal output
pip install rich

# Optional: Install pyyaml for YAML export
pip install pyyaml
```

## Usage

### Basic Commands

```bash
# Scan current directory, output to modlist.json
python main.py

# Scan specific folder
python main.py ./mods

# Specify output file and format
python main.py ./mods -o modlist.csv -f csv

# Export as Markdown
python main.py ./mods -o modlist.md -f markdown

# Export as YAML
python main.py ./mods -o modlist.yaml -f yaml
```

### Advanced Options

```bash
# Recursive scan with 8 parallel workers
python main.py ./mods -r -w 8

# Filter only Forge mods, sorted by name
python main.py ./mods --filter-loader forge --sort-by name

# Exclude unknown mods and duplicates
python main.py ./mods --exclude-unknown --no-duplicates

# Quiet mode (errors only)
python main.py ./mods -q

# Debug logging to file
python main.py ./mods --log-level DEBUG --log-file scan.log

# Exclude certain files
python main.py ./mods --exclude "*-sources.jar" "*-dev.jar"
```

### Command Line Reference

| Argument            | Description                                  | Default                 |
| ------------------- | -------------------------------------------- | ----------------------- |
| `input_folder`      | Folder containing JAR files                  | `.` (current directory) |
| `-o, --output`      | Output file path                             | `modlist.json`          |
| `-f, --format`      | Output format (json, csv, markdown, yaml)    | `json`                  |
| `-r, --recursive`   | Scan subdirectories                          | `false`                 |
| `-w, --workers`     | Parallel processing workers                  | `4`                     |
| `--exclude`         | Glob patterns to exclude                     | `[]`                    |
| `--sort-by`         | Sort field (name, loader, version, filename) | none                    |
| `--filter-loader`   | Filter by loader type                        | none                    |
| `--exclude-unknown` | Exclude mods with unknown loader             | `false`                 |
| `--no-duplicates`   | Remove duplicate mods                        | `false`                 |
| `--no-errors`       | Exclude errors from output                   | `false`                 |
| `--log-level`       | Logging verbosity                            | `INFO`                  |
| `--log-file`        | Log to file                                  | none                    |
| `-q, --quiet`       | Suppress non-error output                    | `false`                 |
| `--version`         | Show version number                          | -                       |

## Project Structure

```
modlist-generator/
├── main.py                    # CLI entry point
├── requirements.txt           # Python dependencies
├── REFERENCES.md              # This documentation
└── src/
    ├── __init__.py            # Package version
    ├── models.py              # Data models (ModInfo, ScanResult)
    ├── scanner.py             # Core scanning logic with parallel processing
    ├── formatters.py          # Output formatters (JSON, CSV, MD, YAML)
    └── extractors/
        ├── __init__.py        # Extractor registry
        ├── base.py            # Abstract base class for extractors
        ├── fabric.py          # Fabric mod extractor
        ├── quilt.py           # Quilt mod extractor
        └── forge.py           # Forge/NeoForge/Legacy extractors
```

## Technical Details

### Mod Metadata Locations

| Mod Loader     | Metadata File                 | Format |
| -------------- | ----------------------------- | ------ |
| Fabric         | `fabric.mod.json`             | JSON   |
| Quilt          | `quilt.mod.json`              | JSON   |
| Forge (Modern) | `META-INF/mods.toml`          | TOML   |
| NeoForge       | `META-INF/neoforge.mods.toml` | TOML   |
| Forge (Legacy) | `mcmod.info`                  | JSON   |

### Extraction Priority

The scanner tries extractors in this order:

1. **FabricExtractor** - `fabric.mod.json`
2. **QuiltExtractor** - `quilt.mod.json`
3. **ForgeTomlExtractor** - `META-INF/mods.toml` or `META-INF/neoforge.mods.toml`
4. **LegacyForgeExtractor** - `mcmod.info`

### NeoForge Detection Heuristics

NeoForge mods are distinguished from Forge mods using multiple signals:

1. Filename `neoforge.mods.toml` → NeoForge
2. `modLoader = "neoforge"` field → NeoForge
3. Dependencies on `neoforge` mod → NeoForge
4. JAR filename contains "neoforge" → NeoForge
5. `loaderVersion` contains "neoforge" → NeoForge

### Dependencies

| Package  | Required      | Notes                |
| -------- | ------------- | -------------------- |
| `tomli`  | Python < 3.11 | TOML parsing         |
| `rich`   | Optional      | Enhanced terminal UI |
| `pyyaml` | Optional      | YAML export support  |

## Output Examples

### JSON Output

```json
{
  "metadata": {
    "version": "2.0.0",
    "generated_at": "2025-12-05T12:00:00.000000",
    "total_mods": 2,
    "scan_duration": 1.23
  },
  "mods": [
    {
      "name": "JEI - Just Enough Items",
      "mod_id": "jei",
      "loader": "fabric",
      "version": "11.6.0.1013",
      "filename": "jei-1.19.2-fabric-11.6.0.1013.jar",
      "dependencies": ["fabric", "minecraft"]
    }
  ]
}
```

### CSV Output

```csv
name,mod_id,loader,version,filename,dependencies
"JEI - Just Enough Items",jei,fabric,11.6.0.1013,jei-1.19.2-fabric-11.6.0.1013.jar,"fabric, minecraft"
```

### Markdown Output

```markdown
# Mod List

Generated: 2025-12-05T12:00:00

| Name                    | Mod ID | Loader | Version     | Filename                          |
| ----------------------- | ------ | ------ | ----------- | --------------------------------- |
| JEI - Just Enough Items | jei    | Fabric | 11.6.0.1013 | jei-1.19.2-fabric-11.6.0.1013.jar |
```

## Troubleshooting

### Common Issues

#### "No JAR files found"

- Check folder path is correct
- Ensure files have `.jar` extension
- Verify read permissions on the folder

#### Most mods show "Unknown" loader

- **ATM10/NeoForge Issue**: Fixed in v2.0 - now checks both `mods.toml` and `neoforge.mods.toml`
- **Missing TOML library**: Install `pip install tomli` for Python < 3.11
- Use `--log-level DEBUG` to see extraction details

#### ImportError: rich not found

- Rich is optional - install with `pip install rich` for progress bars
- The tool works fine without it

#### YAML export not working

- Install PyYAML: `pip install pyyaml`

### Performance Tips

- Use `-w 8` or higher for large modpacks (500+ mods)
- Use `--exclude "*-sources.jar"` to skip source JARs
- Use `--exclude-unknown` to reduce output size
- Parallel processing scales well with CPU cores

## Development

### Adding a New Extractor

1. Create new file in `src/extractors/`
2. Inherit from `BaseExtractor`
3. Implement `can_extract()` and `extract()` methods
4. Add to `ALL_EXTRACTORS` in `src/extractors/__init__.py`

```python
from .base import BaseExtractor
from src.models import ModInfo

class MyExtractor(BaseExtractor):
    def can_extract(self, jar: ZipFile) -> bool:
        return 'my-metadata.json' in jar.namelist()

    def extract(self, jar: ZipFile, filename: str) -> Optional[ModInfo]:
        # Parse metadata and return ModInfo
        pass
```

### Adding a New Output Format

1. Create formatter class in `src/formatters.py`
2. Implement `save()` method
3. Add to `FORMATTERS` registry

```python
class MyFormatter:
    name = "My Format"
    extension = ".myext"

    def save(self, result: ScanResult, output_path: Path, include_errors: bool = True) -> None:
        # Write output file
        pass

FORMATTERS['myformat'] = MyFormatter()
```

## License

This project is provided as-is for personal use in managing Minecraft modpacks.
