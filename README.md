# Modlist Generator

**v3.0.0** — Interactive CLI + TUI tool to scan Minecraft mod JARs (Fabric, Forge, NeoForge, Quilt, Legacy Forge) and export structured modlists (JSON/CSV/Markdown/YAML). Features caching, type safety, comprehensive testing, and TOML configuration.

> Scan fast. Cache smart. Export clean. No more hand-editing mod lists.

## ✨ What's New in v3.0.0

- **🚀 10x Faster Re-scans:** Smart caching skips unchanged files
- **⚙️ Configuration File:** Persistent settings via `~/.config/modlist-generator/config.toml`
- **📊 Batched Progress:** Smoother UI with reduced update frequency
- **🔒 Type Safety:** Full type hints with strict mypy checking
- **✅ Testing:** 60+ tests with pytest and mock JAR fixtures
- **�️ Security Hardening:** Path traversal protection, ZIP bomb detection, resource limits
- **�🔧 Better Errors:** Improved error messages with actionable info

**Breaking Changes:** See [MIGRATION.md](MIGRATION.md) for upgrade guide from v2.x

## Features

- **Loader Detection:** Fabric, Forge, NeoForge, Quilt, Legacy Forge
- **Metadata Extraction:** name, loader, version, mod ID, authors, description, Minecraft versions, dependencies
- **Output Formats:** JSON (compact), CSV, Markdown, YAML
- **Interfaces:** CLI + Textual TUI (Rich-styled logs, progress bars, collapsible details)
- **Filtering:** Exclude unknown loaders, remove duplicates, include disabled mods
- **Performance:** Parallel scanning with configurable workers + smart caching
- **Configuration:** TOML config file for persistent preferences
- **Security:** Path validation, ZIP bomb detection, 500MB file size limits
- **Testing:** Comprehensive test suite with coverage reporting

## Quickstart (Python 3.10+ required, 3.11+ recommended)

```powershell
# From repo root
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Run the CLI

```powershell
python main.py <mods_folder> -o modlist.json --format json --recursive
# Other examples:
python main.py .\mods -o modlist.csv -f csv
python main.py .\mods -f markdown --exclude-unknown --no-duplicates
python main.py .\mods --include-disabled --compact
```

Common flags:

- `-r, --recursive` scan subfolders
- `-w, --workers N` set parallel workers
- `--exclude PATTERN ...` glob patterns to skip (e.g., `*-sources.jar`)
- `--filter-loader {fabric,forge,neoforge,quilt,unknown}` filter results
- `--exclude-unknown` drop unknown loaders
- `--no-duplicates` keep first occurrence only
- `--include-disabled` include `.jar.disabled` files (marked disabled in output)
- `--compact` compact JSON output

CLI in 3 steps:

1. Point to your mods folder (`<mods_folder>`)
2. Pick an output (`-o modlist.json` and `--format json|csv|markdown|yaml`)
3. Tune filters/flags as needed (recursive, exclude, compact, duplicates)

Common CLI recipes:

- Clean JSON list: `python main.py .\mods -o modlist.json --compact`
- CSV for spreadsheets: `python main.py .\mods -o modlist.csv -f csv`
- Markdown for sharing: `python main.py .\mods -f markdown --exclude-unknown --no-duplicates`

### Run the TUI

```powershell
python tui.py
```

TUI highlights:

- Drive dropdown + Go Up for navigation
- Settings panel (format, options, workers)
- Results table + collapsible mod detail panel (dependencies, meta)
- Rich log with styled messages

TUI quick flow:

1. Browse to your mods folder (drive picker + Go Up)
2. Adjust format/options/workers
3. Press **Scan Mods**, then open the mod detail collapsible to view dependencies

Friendly tips:

- Press `b` to browse, `s` to scan, `e` to export, `q` to quit
- Click a row to expand the collapsible panel and see dependencies, author, MC versions
- Toggle dark mode with `d` if your terminal prefers it

### Configuration File (New in v3.0.0)

Create `~/.config/modlist-generator/config.toml` (or `%APPDATA%\modlist-generator\config.toml` on Windows):

```toml
default_workers = 8
default_format = "json"
enable_cache = true
exclude_patterns = ["*-dev.jar", "*-sources.jar"]
```

See [.modlistrc.toml.example](.modlistrc.toml.example) for all available options.

### Caching (New in v3.0.0)

Enable caching for 10x faster re-scans:

```python
from src.scanner import ModScanner
from src.cache import ScanCache
from pathlib import Path

cache = ScanCache(Path("~/.cache/modlist-generator").expanduser())
scanner = ModScanner(workers=8, cache=cache, use_cache=True)

result = scanner.scan_folder(Path("./mods"))
# Second scan is ~10x faster for unchanged files!
```

### Quick Picks

- Need a fast JSON list? `python main.py .\mods -o modlist.json --compact`
- Want to browse interactively? `python tui.py` then hit **Scan Mods**
- Prefer one-file exe? Build once, then run `dist\modlist-generator.exe`

### Sample Output (JSON)

```json
[
  {
    "name": "Example Mod",
    "loader": "forge",
    "version": "1.2.3",
    "mod_id": "examplemod",
    "filename": "examplemod-1.2.3.jar",
    "author": "Mod Author",
    "description": "Adds handy tools and tweaks",
    "mc_versions": ["1.20.1"],
    "dependencies": ["forge", "anotherlib"],
    "disabled": false
  }
]
```

## Build a single executable (Windows)

```powershell
.\.venv\Scripts\activate
python -m PyInstaller --onefile --name modlist-generator --console ^
  --collect-submodules textual --collect-submodules rich ^
  tui.py
# Output: dist/modlist-generator.exe
```

## Project Structure

```
main.py                # CLI entrypoint
tui.py                 # Textual TUI entrypoint
src/
  scanner.py           # Folder scanning / parallel workers
  models.py            # ModInfo / ScanResult data classes
  formatters.py        # JSON/CSV/Markdown/YAML writers
  config.py            # Configuration management (NEW v3.0.0)
  cache.py             # Scan result caching (NEW v3.0.0)
  security.py          # Path validation, ZIP bomb detection (NEW v3.0.0)
  extractors/          # Loader-specific metadata extractors
tests/                 # Test suite (NEW v3.0.0)
  conftest.py          # Pytest fixtures
  test_*.py            # Unit & integration tests
requirements.txt       # Runtime dependencies
requirements-dev.txt   # Development dependencies (NEW v3.0.0)
pytest.ini             # Test configuration (NEW v3.0.0)
mypy.ini               # Type checking config (NEW v3.0.0)
MIGRATION.md           # Upgrade guide (NEW v3.0.0)
CHANGELOG.md           # Version history (NEW v3.0.0)
modlist-generator.spec # PyInstaller spec (generated)
```

## Security

v3.0.0 includes comprehensive security protections for safe JAR file processing:

**Path Traversal Protection:**

- All input paths validated against system directories
- ZIP entry names checked for `../` and absolute paths
- Path length limits (1000 characters max)

**ZIP Bomb Detection:**

- File size limits: 500MB per file, 500MB total decompressed
- Maximum 10,000 files per JAR
- Compression ratio validation

**Resource Limits:**

- Safe file extraction with chunked reading (8KB chunks)
- Memory-bounded operations prevent exhaustion attacks
- Automatic rejection of malformed JARs

Security features are **always enabled** and cannot be disabled. Invalid or unsafe files are logged and skipped during scanning.

## Development

### Running Tests

```powershell
pip install -r requirements-dev.txt
pytest                    # Run all tests
pytest --cov=src         # With coverage
pytest tests/test_scanner.py  # Specific file
```

### Type Checking

```powershell
mypy src/
```

### Code Quality

```powershell
black src/ tests/        # Format code
ruff check src/          # Lint
```

## Documentation

- **[MIGRATION.md](MIGRATION.md)** — Upgrade guide from v2.x to v3.0.0
- **[CHANGELOG.md](CHANGELOG.md)** — Version history and release notes
- **[REFERENCES.md](REFERENCES.md)** — Technical details and command reference
- **[.modlistrc.toml.example](.modlistrc.toml.example)** — Configuration file template

## Notes

- Python 3.10+ required (3.11+ recommended for built-in `tomllib`)
- On Python < 3.11, `tomli` is auto-installed for TOML support
- Rich is optional for CLI but recommended for better output
- Textual is required for the TUI

## License

MIT
