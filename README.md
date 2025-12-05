# Modlist Generator

Interactive CLI + TUI tool to scan a folder of Minecraft mod JARs (Fabric, Forge, NeoForge, Quilt, Legacy Forge) and export a structured modlist (JSON/CSV/Markdown/YAML). Includes a Textual-based TUI, dependency display, and a one-file Windows build.

> Scan fast. Export clean. No more hand-editing mod lists.

## Features

- Detects loaders: Fabric, Forge, NeoForge, Quilt, Legacy Forge
- Extracts: name, loader, version, mod id, filename, authors, description, Minecraft versions, disabled (.jar.disabled), dependencies
- Outputs: JSON (compact option), CSV, Markdown, YAML
- CLI + Textual TUI (Rich-styled logs, progress bar, collapsible mod details with dependencies)
- Filtering & cleanup: exclude unknown loaders, remove duplicates, include disabled mods
- Parallel scanning with configurable workers

## Quickstart (Python 3.11+ recommended)

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

- Press `b` to browse, `s` to scan, `e` to export, `q` to quit.
- Click a row to expand the collapsible panel and see dependencies, author, MC versions.
- Toggle dark mode with `d` if your terminal prefers it.

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
  extractors/          # Loader-specific metadata extractors
requirements.txt       # Runtime deps
modlist-generator.spec # PyInstaller spec (generated)
```

## Notes

- On Python < 3.11, `tomli` is required; 3.11+ uses built-in `tomllib`.
- Rich is optional for the CLI but recommended for nicer output.
- Textual is required for the TUI.

## License

MIT
