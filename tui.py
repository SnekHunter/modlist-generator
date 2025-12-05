#!/usr/bin/env python3
"""
Modlist Generator TUI - Interactive Terminal User Interface
A beautiful terminal app for extracting mod details from Minecraft JAR files.
"""

import asyncio
import os
import platform
import string
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    Input,
    Select,
    Checkbox,
    ProgressBar,
    Label,
    DataTable,
    DirectoryTree,
    RichLog,
    Collapsible,
)
from textual.screen import ModalScreen

from src import __version__
from src.scanner import ModScanner
from src.models import ScanResult, ModInfo
from src.formatters import FORMATTERS, get_formatter


def get_available_drives() -> list[tuple[str, str]]:
    """Get list of available drives on Windows, or root on Unix."""
    if platform.system() == "Windows":
        drives = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append((f"💾 {letter}:", drive))
        return drives
    else:
        return [("/ (root)", "/")]


class FolderSelectScreen(ModalScreen[Optional[Path]]):
    """Modal screen for selecting a folder."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select"),
    ]
    
    CSS = """
    FolderSelectScreen {
        align: center middle;
    }
    
    FolderSelectScreen > Container {
        width: 80%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1;
    }
    
    FolderSelectScreen DirectoryTree {
        height: 1fr;
        border: solid $primary;
    }
    
    FolderSelectScreen .buttons {
        height: auto;
        align: center middle;
        padding-top: 1;
    }
    
    FolderSelectScreen .nav-row {
        height: auto;
        padding-bottom: 1;
    }
    
    FolderSelectScreen #drive-select {
        width: 12;
    }
    
    FolderSelectScreen #current-path {
        width: 1fr;
        padding: 0 1;
    }
    
    FolderSelectScreen #go-up-btn {
        width: auto;
        min-width: 8;
    }
    """
    
    def __init__(self, start_path: Path = Path.cwd()):
        super().__init__()
        self.start_path = start_path
        self.selected_path: Optional[Path] = None
        self.current_root = start_path
    
    def compose(self) -> ComposeResult:
        drives = get_available_drives()
        current_drive = str(self.start_path.anchor) if self.start_path.anchor else drives[0][1]
        
        with Container():
            yield Label("Select Mods Folder", id="title")
            # Navigation row with drive selector and Go Up button
            with Horizontal(classes="nav-row"):
                yield Select(drives, value=current_drive, id="drive-select")
                yield Static(str(self.start_path), id="current-path")
                yield Button("⬆️ Up", id="go-up-btn", variant="default")
            yield DirectoryTree(str(self.start_path), id="folder-tree")
            with Horizontal(classes="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Select", variant="primary", id="select")
    
    @on(Select.Changed, "#drive-select")
    def on_drive_changed(self, event: Select.Changed) -> None:
        """Switch to a different drive."""
        if event.value:
            new_path = Path(event.value)
            self.current_root = new_path
            self.selected_path = new_path
            # Update the directory tree
            tree = self.query_one("#folder-tree", DirectoryTree)
            tree.path = new_path
            tree.reload()
            # Update path display
            self.query_one("#current-path", Static).update(str(new_path))
    
    @on(Button.Pressed, "#go-up-btn")
    def on_go_up(self) -> None:
        """Navigate to parent directory."""
        parent = self.current_root.parent
        if parent != self.current_root:  # Not at root
            self.current_root = parent
            self.selected_path = parent
            # Update the directory tree
            tree = self.query_one("#folder-tree", DirectoryTree)
            tree.path = parent
            tree.reload()
            # Update path display
            self.query_one("#current-path", Static).update(str(parent))
    
    @on(DirectoryTree.DirectorySelected)
    def on_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.selected_path = event.path
        self.current_root = event.path
        self.query_one("#current-path", Static).update(str(event.path))
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
    
    @on(Button.Pressed, "#select")
    def on_select(self) -> None:
        self.dismiss(self.selected_path or self.start_path)
    
    def action_cancel(self) -> None:
        self.dismiss(None)
    
    def action_select(self) -> None:
        self.dismiss(self.selected_path or self.start_path)


class ModlistGeneratorApp(App):
    """Main TUI Application for Modlist Generator."""
    
    TITLE = f"Modlist Generator v{__version__}"
    SUB_TITLE = "Extract mod details from Minecraft JAR files"
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "browse", "Browse"),
        Binding("s", "scan", "Scan"),
        Binding("e", "export", "Export"),
        Binding("d", "toggle_dark", "Toggle Dark Mode"),
    ]
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: auto 1fr auto;
    }
    
    #main-container {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 2fr;
        padding: 1;
    }
    
    #settings-panel {
        border: solid $primary;
        padding: 1;
        height: 100%;
    }
    
    #results-panel {
        border: solid $accent;
        padding: 1;
        height: 100%;
    }
    
    .section-title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
    }
    
    .setting-row {
        height: auto;
        margin-bottom: 1;
    }
    
    .setting-label {
        width: 100%;
        padding-bottom: 0;
    }
    
    Input {
        width: 100%;
    }
    
    Select {
        width: 100%;
    }
    
    #folder-input {
        width: 1fr;
    }
    
    #browse-btn {
        width: auto;
        min-width: 10;
    }
    
    #scan-btn {
        width: 100%;
        margin-top: 1;
    }
    
    #export-btn {
        width: 100%;
        margin-top: 1;
    }
    
    #progress-container {
        height: auto;
        padding: 1;
        width: 100%;
    }
    
    ProgressBar {
        width: 100%;
        padding: 0 1;
    }
    
    ProgressBar > .bar--bar {
        width: 100%;
    }
    
    #status-label {
        text-align: center;
        padding: 1;
    }
    
    #summary-panel {
        height: auto;
        padding: 1;
        border: solid $success;
        margin-bottom: 1;
        box-sizing: border-box;
    }
    
    DataTable {
        height: 1fr;
    }
    
    #mod-detail {
        height: auto;
        max-height: 15;
        border: solid $primary;
        margin-bottom: 1;
        padding: 0 1;
    }
    
    #mod-detail-content {
        padding: 1;
    }
    
    #log-panel {
        height: 10;
        border: solid $warning;
        box-sizing: border-box;
    }
    """
    
    def __init__(self):
        super().__init__()
        self.scan_result: Optional[ScanResult] = None
        self.input_folder: Path = Path.cwd()
        self.is_scanning = False
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="main-container"):
            # Left panel - Settings
            with Vertical(id="settings-panel"):
                yield Static("⚙️ Settings", classes="section-title")
                
                # Folder selection
                yield Static("Mods Folder:", classes="setting-label")
                with Horizontal(classes="setting-row"):
                    yield Input(
                        placeholder="Select folder...",
                        value=str(self.input_folder),
                        id="folder-input"
                    )
                    yield Button("📁", id="browse-btn", variant="primary")
                
                # Output format
                yield Static("Output Format:", classes="setting-label")
                yield Select(
                    [(f.upper(), f) for f in ["json", "csv", "markdown", "yaml"]],
                    value="json",
                    id="format-select"
                )
                
                # Options
                yield Static("Options:", classes="setting-label")
                yield Checkbox("Recursive scan", id="recursive-check")
                yield Checkbox("Include disabled mods", id="disabled-check")
                yield Checkbox("Exclude unknown loaders", id="exclude-unknown-check")
                yield Checkbox("Remove duplicates", id="no-duplicates-check")
                yield Checkbox("Compact JSON output", id="compact-check")
                
                # Workers
                yield Static("Parallel Workers:", classes="setting-label")
                yield Select(
                    [(str(n), n) for n in [1, 2, 4, 8, 16]],
                    value=4,
                    id="workers-select"
                )
                
                # Action buttons
                yield Button("🔍 Scan Mods", id="scan-btn", variant="success")
                yield Button("💾 Export Results", id="export-btn", variant="primary", disabled=True)
                
                # Progress
                with Vertical(id="progress-container"):
                    yield ProgressBar(id="progress-bar", show_eta=False)
                    yield Static("Ready", id="status-label")
            
            # Right panel - Results
            with Vertical(id="results-panel"):
                yield Static("📋 Results", classes="section-title")
                
                # Summary
                with Vertical(id="summary-panel"):
                    yield Static("No scan results yet. Click 'Scan Mods' to begin.", id="summary-text")
                
                # Collapsible mod detail panel
                with Collapsible(title="📄 Mod Details (select a row)", collapsed=True, id="mod-detail"):
                    yield Static("Select a mod from the table to view its details and dependencies.", id="mod-detail-content")
                
                # Results table
                yield DataTable(id="results-table")
                
                # Log with Rich markup support
                yield RichLog(id="log-panel", highlight=True, markup=True)
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Set up the data table when app mounts."""
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Name", "Loader", "Version", "Author", "Deps", "MC Version", "Status")
        table.cursor_type = "row"
        
        # Log welcome message
        log = self.query_one("#log-panel", RichLog)
        log.write(f"[bold green]Modlist Generator v{__version__}[/]")
        log.write("Select a mods folder and click 'Scan Mods' to begin.")
    
    @on(Button.Pressed, "#browse-btn")
    def on_browse(self) -> None:
        """Open folder selection dialog."""
        self.action_browse()
    
    def action_browse(self) -> None:
        """Show folder selection screen."""
        def handle_folder(path: Optional[Path]) -> None:
            if path:
                self.input_folder = path
                self.query_one("#folder-input", Input).value = str(path)
                log = self.query_one("#log-panel", RichLog)
                log.write(f"Selected folder: [cyan]{path}[/]")
        
        self.push_screen(FolderSelectScreen(self.input_folder), handle_folder)
    
    @on(Input.Changed, "#folder-input")
    def on_folder_input_changed(self, event: Input.Changed) -> None:
        """Update input folder when text changes."""
        try:
            self.input_folder = Path(event.value)
        except Exception:
            pass
    
    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show mod details when a row is selected."""
        if not self.scan_result:
            return
        
        row_index = event.cursor_row
        if 0 <= row_index < len(self.scan_result.mods):
            mod = self.scan_result.mods[row_index]
            
            # Build detail content
            lines = [
                f"[bold]{mod.name}[/] v{mod.version}",
                f"[dim]Loader:[/] {mod.loader.capitalize()}",
                f"[dim]File:[/] {mod.filename}",
            ]
            
            if mod.author:
                lines.append(f"[dim]Author:[/] {mod.author}")
            
            if mod.mc_versions:
                lines.append(f"[dim]MC Versions:[/] {', '.join(mod.mc_versions)}")
            
            if mod.dependencies:
                lines.append("")
                lines.append("[bold cyan]Dependencies:[/]")
                for dep in mod.dependencies:
                    lines.append(f"  • {dep}")
            else:
                lines.append("")
                lines.append("[dim]No dependencies[/]")
            
            if mod.description:
                lines.append("")
                lines.append(f"[dim]{mod.description[:300]}[/]")
            
            # Update the detail panel
            detail = self.query_one("#mod-detail", Collapsible)
            detail.title = f"📄 {mod.name}"
            detail.collapsed = False
            self.query_one("#mod-detail-content", Static).update("\n".join(lines))
    
    @on(Button.Pressed, "#scan-btn")
    def on_scan_pressed(self) -> None:
        """Start scanning when button pressed."""
        self.action_scan()
    
    def action_scan(self) -> None:
        """Start the mod scanning process."""
        if self.is_scanning:
            return
        
        if not self.input_folder.exists():
            log = self.query_one("#log-panel", RichLog)
            log.write(f"[bold red]Error:[/] Folder not found: {self.input_folder}")
            return
        
        self.run_scan()
    
    @work(exclusive=True, thread=True)
    def run_scan(self) -> None:
        """Run the scan in a background thread."""
        self.is_scanning = True
        
        # Get settings
        recursive = self.query_one("#recursive-check", Checkbox).value
        include_disabled = self.query_one("#disabled-check", Checkbox).value
        workers = self.query_one("#workers-select", Select).value or 4
        
        # Update UI
        self.call_from_thread(self._update_status, "Scanning...", 0)
        log = self.query_one("#log-panel", RichLog)
        self.call_from_thread(log.write, f"Starting scan of [cyan]{self.input_folder}[/]...")
        
        try:
            scanner = ModScanner(workers=workers)
            
            def progress_callback(current: int, total: int, filename: str):
                progress = current / total if total > 0 else 0
                self.call_from_thread(self._update_status, f"Processing: {filename[:30]}...", progress)
            
            result = scanner.scan_folder(
                self.input_folder,
                recursive=recursive,
                include_disabled=include_disabled,
                progress_callback=progress_callback
            )
            
            # Apply filters
            if self.query_one("#exclude-unknown-check", Checkbox).value:
                result.mods = [m for m in result.mods if m.loader != 'unknown']
            
            if self.query_one("#no-duplicates-check", Checkbox).value:
                seen = set()
                unique_mods = []
                for mod in result.mods:
                    key = mod.mod_id or mod.name.lower()
                    if key not in seen:
                        seen.add(key)
                        unique_mods.append(mod)
                result.mods = unique_mods
            
            self.scan_result = result
            self.call_from_thread(self._display_results)
            self.call_from_thread(log.write, f"[bold green]Scan complete![/] Found {len(result.mods)} mods in {result.scan_duration:.2f}s")
            
        except Exception as e:
            self.call_from_thread(log.write, f"[bold red]Error:[/] {str(e)}")
            self.call_from_thread(self._update_status, f"Error: {str(e)}", 0)
        
        finally:
            self.is_scanning = False
            self.call_from_thread(self._update_status, "Ready", 1.0)
    
    def _update_status(self, message: str, progress: float) -> None:
        """Update status label and progress bar."""
        self.query_one("#status-label", Static).update(message)
        self.query_one("#progress-bar", ProgressBar).update(progress=progress)
    
    def _display_results(self) -> None:
        """Display scan results in the table."""
        if not self.scan_result:
            return
        
        # Update summary
        result = self.scan_result
        loaders = {}
        for mod in result.mods:
            loaders[mod.loader] = loaders.get(mod.loader, 0) + 1
        
        loader_summary = ", ".join(f"{k.capitalize()}: {v}" for k, v in sorted(loaders.items()))
        disabled_count = sum(1 for m in result.mods if m.disabled)
        
        summary_lines = [
            f"📦 Total Mods: {len(result.mods)}",
            f"📁 Files Scanned: {result.total_files}",
            f"⏱️ Duration: {result.scan_duration:.2f}s",
            f"🔧 Loaders: {loader_summary}",
        ]
        if disabled_count > 0:
            summary_lines.append(f"🔴 Disabled: {disabled_count}")
        if result.errors:
            summary_lines.append(f"⚠️ Errors: {len(result.errors)}")
        
        self.query_one("#summary-text", Static).update("\n".join(summary_lines))
        
        # Update table
        table = self.query_one("#results-table", DataTable)
        table.clear()
        
        for mod in result.mods:
            status = "🔴 Disabled" if mod.disabled else "✅"
            mc_ver = ", ".join(mod.mc_versions[:2]) if mod.mc_versions else "-"
            author = (mod.author or "-")[:20]
            # Format dependencies with truncation
            if mod.dependencies:
                deps_str = ", ".join(mod.dependencies[:3])
                if len(mod.dependencies) > 3:
                    deps_str += f" (+{len(mod.dependencies) - 3})"
            else:
                deps_str = "-"
            table.add_row(
                mod.name[:40],
                mod.loader.capitalize(),
                mod.version[:15],
                author,
                deps_str[:25],
                mc_ver,
                status
            )
        
        # Enable export button
        self.query_one("#export-btn", Button).disabled = False
    
    @on(Button.Pressed, "#export-btn")
    def on_export_pressed(self) -> None:
        """Export results when button pressed."""
        self.action_export()
    
    def action_export(self) -> None:
        """Export scan results to file."""
        if not self.scan_result:
            return
        
        format_name = self.query_one("#format-select", Select).value or "json"
        compact = self.query_one("#compact-check", Checkbox).value
        
        formatter = get_formatter(format_name)
        if not formatter:
            return
        
        output_path = self.input_folder / f"modlist{formatter.extension}"
        
        try:
            formatter.save(self.scan_result, output_path, include_errors=True, compact=compact)
            
            log = self.query_one("#log-panel", RichLog)
            log.write(f"[bold green]Exported:[/] {output_path}")
            
            self._update_status(f"Saved to {output_path.name}", 1.0)
            
        except Exception as e:
            log = self.query_one("#log-panel", RichLog)
            log.write(f"[bold red]Export error:[/] {str(e)}")
    
    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark


def main():
    """Entry point for the TUI application."""
    app = ModlistGeneratorApp()
    app.run()


if __name__ == "__main__":
    main()
