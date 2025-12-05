#!/usr/bin/env python3
"""
Modlist Generator v2.0 - Extract mod details from a folder of JAR files
Supports Fabric, Forge, NeoForge, and Quilt mods
Output: JSON, CSV, Markdown, or YAML file with mod information
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Try to import rich for better output
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src import __version__
from src.scanner import ModScanner
from src.models import ScanResult
from src.formatters import FORMATTERS, get_formatter

# Set up console
console = Console() if RICH_AVAILABLE else None


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """Configure logging with optional rich handler."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    handlers = []
    
    if RICH_AVAILABLE:
        handlers.append(RichHandler(
            console=console,
            show_time=False,
            show_path=False,
            rich_tracebacks=True
        ))
    else:
        handlers.append(logging.StreamHandler())
    
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=log_level,
        format="%(message)s" if RICH_AVAILABLE else "%(levelname)s: %(message)s",
        handlers=handlers
    )


def print_summary(result: ScanResult, show_duplicates: bool = True) -> None:
    """Print a summary of the scan results."""
    if RICH_AVAILABLE and console:
        # Create summary table
        table = Table(title="Scan Summary", show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Mods", str(len(result.mods)))
        table.add_row("Files Scanned", str(result.total_files))
        table.add_row("Scan Duration", f"{result.scan_duration:.2f}s")
        table.add_row("Errors", str(len(result.errors)))
        
        # Count by loader
        loaders = {}
        for mod in result.mods:
            loaders[mod.loader] = loaders.get(mod.loader, 0) + 1
        
        for loader, count in sorted(loaders.items()):
            table.add_row(f"  {loader.capitalize()}", str(count))
        
        console.print(table)
        
        # Show duplicates if any
        if show_duplicates:
            duplicates = result.get_duplicates()
            if duplicates:
                console.print(f"\n[yellow]⚠ Found {len(duplicates)} potential duplicate mod(s):[/yellow]")
                for mod_id, mods in duplicates.items():
                    versions = [f"{m.name} v{m.version}" for m in mods]
                    console.print(f"  • {mod_id}: {', '.join(versions)}")
        
        # Show errors summary
        if result.errors:
            console.print(f"\n[red]✗ {len(result.errors)} error(s) encountered[/red]")
    else:
        print(f"\n{'='*50}")
        print(f"Scan Summary")
        print(f"{'='*50}")
        print(f"Total Mods: {len(result.mods)}")
        print(f"Files Scanned: {result.total_files}")
        print(f"Scan Duration: {result.scan_duration:.2f}s")
        print(f"Errors: {len(result.errors)}")
        
        loaders = {}
        for mod in result.mods:
            loaders[mod.loader] = loaders.get(mod.loader, 0) + 1
        
        print("\nBy Loader:")
        for loader, count in sorted(loaders.items()):
            print(f"  {loader.capitalize()}: {count}")
        
        if result.errors:
            print(f"\n⚠ {len(result.errors)} error(s) encountered")


def scan_with_progress(scanner: ModScanner, folder_path: Path, recursive: bool, exclude: list, include_disabled: bool = False) -> ScanResult:
    """Scan with progress bar if rich is available."""
    if RICH_AVAILABLE and console:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Scanning mods...", total=None)
            
            def update_progress(current: int, total: int, filename: str):
                if progress.tasks[task].total != total:
                    progress.update(task, total=total)
                progress.update(task, completed=current, description=f"[cyan]{filename[:40]}...")
            
            result = scanner.scan_folder(
                folder_path,
                recursive=recursive,
                exclude_patterns=exclude,
                include_disabled=include_disabled,
                progress_callback=update_progress
            )
            
            progress.update(task, completed=result.total_files, description="[green]Done!")
        
        return result
    else:
        def simple_progress(current: int, total: int, filename: str):
            print(f"Processing [{current}/{total}]: {filename}")
        
        return scanner.scan_folder(
            folder_path,
            recursive=recursive,
            exclude_patterns=exclude,
            include_disabled=include_disabled,
            progress_callback=simple_progress
        )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract mod details from JAR files and generate output in various formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                              # Current directory, output to modlist.json
  python main.py ./mods                       # Scan ./mods folder
  python main.py ./mods -o modlist.csv -f csv # Output as CSV
  python main.py ./mods -f markdown           # Output as Markdown
  python main.py ./mods -r                    # Recursive scan
  python main.py ./mods --workers 8           # Use 8 parallel workers
  python main.py ./mods --sort-by name        # Sort output by mod name
  python main.py ./mods --filter-loader forge # Only show Forge mods
        """
    )
    
    parser.add_argument(
        'input_folder',
        nargs='?',
        default='.',
        help='Folder containing mod JAR files (default: current directory)'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='modlist.json',
        help='Output file path (default: modlist.json)'
    )
    
    parser.add_argument(
        '-f', '--format',
        choices=['json', 'csv', 'markdown', 'md', 'yaml', 'yml'],
        default='json',
        help='Output format (default: json)'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Scan subdirectories recursively'
    )
    
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )
    
    parser.add_argument(
        '--exclude',
        nargs='*',
        default=[],
        help='Glob patterns to exclude (e.g., "*-sources.jar")'
    )
    
    parser.add_argument(
        '--include-disabled',
        action='store_true',
        help='Include .jar.disabled files (marked with disabled: true)'
    )
    
    parser.add_argument(
        '--compact',
        action='store_true',
        help='Output compact JSON (no indentation)'
    )
    
    parser.add_argument(
        '--sort-by',
        choices=['name', 'loader', 'version', 'filename'],
        help='Sort mods by field'
    )
    
    parser.add_argument(
        '--filter-loader',
        choices=['fabric', 'forge', 'neoforge', 'quilt', 'unknown'],
        help='Only include mods for specific loader'
    )
    
    parser.add_argument(
        '--exclude-unknown',
        action='store_true',
        help='Exclude mods with unknown loader'
    )
    
    parser.add_argument(
        '--no-duplicates',
        action='store_true',
        help='Exclude duplicate mods (keeps first occurrence)'
    )
    
    parser.add_argument(
        '--no-errors',
        action='store_true',
        help='Exclude errors from output'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--log-file',
        type=Path,
        help='Log to file instead of console'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress non-error output'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'Modlist Generator {__version__}'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = 'ERROR' if args.quiet else args.log_level
    setup_logging(log_level, args.log_file)
    
    logger = logging.getLogger(__name__)
    
    try:
        input_path = Path(args.input_folder).resolve()
        output_path = Path(args.output).resolve()
        
        # Ensure output has correct extension for format
        formatter = get_formatter(args.format)
        if not formatter:
            print(f"Error: Unknown format '{args.format}'", file=sys.stderr)
            sys.exit(1)
        
        if not output_path.suffix:
            output_path = output_path.with_suffix(formatter.extension)
        
        if not args.quiet:
            if RICH_AVAILABLE and console:
                console.print(f"[bold]Modlist Generator v{__version__}[/bold]")
                console.print(f"Scanning: [cyan]{input_path}[/cyan]")
                console.print(f"Output: [cyan]{output_path}[/cyan] ({formatter.name})")
                console.print()
            else:
                print(f"Modlist Generator v{__version__}")
                print(f"Scanning: {input_path}")
                print(f"Output: {output_path} ({formatter.name})")
                print()
        
        # Create scanner and run
        scanner = ModScanner(workers=args.workers)
        result = scan_with_progress(scanner, input_path, args.recursive, args.exclude, args.include_disabled)
        
        # Apply filters
        if args.filter_loader:
            result.mods = result.filter_by_loader(args.filter_loader)
        
        if args.exclude_unknown:
            result.mods = [m for m in result.mods if m.loader != 'unknown']
        
        if args.no_duplicates:
            seen = set()
            unique_mods = []
            for mod in result.mods:
                key = mod.mod_id or mod.name.lower()
                if key not in seen:
                    seen.add(key)
                    unique_mods.append(mod)
            result.mods = unique_mods
        
        # Apply sorting
        if args.sort_by:
            result.sort_mods(by=args.sort_by)
        
        # Save output
        formatter.save(result, output_path, include_errors=not args.no_errors, compact=getattr(args, 'compact', False))
        
        # Print summary
        if not args.quiet:
            print_summary(result)
            
            if RICH_AVAILABLE and console:
                console.print(f"\n[green]✓ Output saved to {output_path}[/green]")
            else:
                print(f"\n✓ Output saved to {output_path}")
        
        # Exit with error code if there were errors
        if result.errors and not args.quiet:
            sys.exit(0)  # Warnings but completed successfully
        
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
