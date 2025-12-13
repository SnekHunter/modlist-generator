#!/usr/bin/env python3
"""
Modlist Generator TUI - Interactive Terminal User Interface
A beautiful terminal app for extracting mod details from Minecraft JAR files.
"""

import asyncio
import json
import os
import platform
import string
from pathlib import Path
from threading import Event
from typing import Optional, List, Tuple, Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.message import Message
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
from src.scanner import ModScanner, ProgressUpdate
from src.models import ScanResult, ModInfo
from src.formatters import FORMATTERS, get_formatter
from src.config import load_config
from src.cache import ScanCache


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


class ConfirmScreen(ModalScreen[bool]):
    """Modal confirmation dialog."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]
    
    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    
    ConfirmScreen > Container {
        width: 60;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 2;
    }
    
    ConfirmScreen #confirm-title {
        text-style: bold;
        text-align: center;
        padding-bottom: 1;
    }
    
    ConfirmScreen .message {
        text-align: center;
        padding: 1;
    }
    
    ConfirmScreen .buttons {
        height: auto;
        align: center middle;
        padding-top: 1;
    }
    """
    
    def __init__(self, message: str, title: str = "Confirm"):
        super().__init__()
        self.message_text = message
        self.title_text = title
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self.title_text, id="confirm-title")
            yield Static(self.message_text, classes="message")
            with Horizontal(classes="buttons"):
                yield Button("Cancel", variant="default", id="cancel-confirm")
                yield Button("Confirm", variant="warning", id="do-confirm")
    
    @on(Button.Pressed, "#cancel-confirm")
    def on_cancel(self) -> None:
        self.dismiss(False)
    
    @on(Button.Pressed, "#do-confirm")
    def on_confirm_btn(self) -> None:
        self.dismiss(True)
    
    def action_cancel(self) -> None:
        self.dismiss(False)
    
    def action_confirm(self) -> None:
        self.dismiss(True)


class SettingsManager:
    """Manage persistent TUI settings."""
    
    def __init__(self):
        self.config_path = self._get_config_path()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = self._load()
    
    def _get_config_path(self) -> Path:
        """Get platform-appropriate config path."""
        try:
            from platformdirs import user_config_dir
            return Path(user_config_dir("modlist-generator")) / "tui-settings.json"
        except ImportError:
            if platform.system() == "Windows":
                base = Path(os.environ.get("APPDATA", Path.home()))
            else:
                base = Path.home() / ".config"
            return base / "modlist-generator" / "tui-settings.json"
    
    def _load(self) -> dict:
        """Load settings from disk."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return {**self._defaults(), **json.load(f)}
            except Exception:
                pass
        return self._defaults()
    
    def _defaults(self) -> dict:
        """Default settings."""
        return {
            "last_folder": str(Path.cwd()),
            "format": "json",
            "recursive": False,
            "include_disabled": False,
            "exclude_unknown": False,
            "no_duplicates": False,
            "compact": False,
            "workers": 4,
            "dark_mode": True,
        }
    
    def save(self) -> None:
        """Save settings to disk."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass  # Fail silently
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self.save()


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
        Binding("escape", "cancel_scan", "Cancel Scan"),
        Binding("/", "focus_search", "Search"),
    ]
    
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.settings_mgr = SettingsManager()
        self.scan_result: Optional[ScanResult] = None
        self.input_folder: Path = Path(self.settings_mgr.get("last_folder", str(Path.cwd())))
        self.is_scanning = False
        self._cancel_event = Event()
        self._full_mod_list: List[ModInfo] = []  # Unfiltered list for search
        self._current_sort_column: Optional[str] = None
        self._sort_reverse = False
        self.dark = self.settings_mgr.get("dark_mode", True)
    
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
    
    #search-container {
        height: auto;
        padding: 0 0 1 0;
    }
    
    #search-input {
        width: 1fr;
    }
    
    #errors-panel {
        height: auto;
        max-height: 10;
        border: solid $error;
        margin-bottom: 1;
    }
    
    #error-log {
        height: auto;
        max-height: 8;
    }
    
    #cancel-btn {
        width: 100%;
        margin-top: 1;
    }
    
    .action-buttons {
        height: auto;
    }
    """
    
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
                with Horizontal(classes="action-buttons"):
                    yield Button("🔍 Scan Mods", id="scan-btn", variant="success")
                    yield Button("⏹ Cancel", id="cancel-btn", variant="error", disabled=True)
                yield Button("💾 Export Results", id="export-btn", variant="primary", disabled=True)
                
                # Progress
                with Vertical(id="progress-container"):
                    yield ProgressBar(id="progress-bar", show_eta=False)
                    yield Static("Ready", id="status-label")
            
            # Right panel - Results
            with Vertical(id="results-panel"):
                yield Static("📋 Results", classes="section-title")
                
                # Search bar
                with Horizontal(id="search-container"):
                    yield Input(placeholder="🔍 Search mods...", id="search-input")
                
                # Summary
                with Vertical(id="summary-panel"):
                    yield Static("No scan results yet. Click 'Scan Mods' to begin.", id="summary-text")
                
                # Collapsible mod detail panel
                with Collapsible(title="📄 Mod Details (select a row)", collapsed=True, id="mod-detail"):
                    yield Static("Select a mod from the table to view its details and dependencies.", id="mod-detail-content")
                
                # Collapsible errors panel
                with Collapsible(title="⚠️ Errors (0)", collapsed=True, id="errors-panel"):
                    yield RichLog(id="error-log", highlight=True, markup=True)
                
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
                # Save last folder
                self.settings_mgr.save_settings({"last_folder": str(path)})
        
        self.push_screen(FolderSelectScreen(self.input_folder), handle_folder)
    
    @on(Input.Changed, "#folder-input")
    def on_folder_input_changed(self, event: Input.Changed) -> None:
        """Update input folder when text changes."""
        try:
            self.input_folder = Path(event.value)
            # Save last folder
            if self.input_folder.exists():
                self.settings_mgr.save_settings({"last_folder": str(self.input_folder)})
        except Exception:
            pass
    
    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Filter the results table based on search text."""
        if not self._full_mod_list:
            return
        
        search_text = event.value.lower().strip()
        table = self.query_one("#results-table", DataTable)
        
        # Clear and repopulate table
        table.clear()
        
        for mod in self._full_mod_list:
            # Check if search text matches any field
            if search_text:
                searchable = f"{mod.name} {mod.loader} {mod.author or ''} {mod.version}".lower()
                if search_text not in searchable:
                    continue
            
            # Add row (same format as original population)
            status = "✅" if mod.is_enabled else "❌"
            deps_count = str(len(mod.dependencies)) if mod.dependencies else "0"
            mc_vers = ", ".join(mod.mc_versions[:2]) if mod.mc_versions else "-"
            if mod.mc_versions and len(mod.mc_versions) > 2:
                mc_vers += "..."
            
            table.add_row(
                mod.name,
                mod.loader.capitalize(),
                mod.version,
                mod.author or "-",
                deps_count,
                mc_vers,
                status
            )
    
    @on(DataTable.HeaderSelected)
    def on_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Sort table when a column header is clicked."""
        if not self._full_mod_list:
            return
        
        column_key = event.column_key
        column_index = event.column_index
        
        # Toggle sort direction if same column
        if self._current_sort_column == column_index:
            self._sort_reverse = not self._sort_reverse
        else:
            self._current_sort_column = column_index
            self._sort_reverse = False
        
        # Define sort key functions for each column
        sort_keys = {
            0: lambda m: m.name.lower(),  # Name
            1: lambda m: m.loader.lower(),  # Loader
            2: lambda m: m.version,  # Version
            3: lambda m: (m.author or "").lower(),  # Author
            4: lambda m: len(m.dependencies) if m.dependencies else 0,  # Deps
            5: lambda m: m.mc_versions[0] if m.mc_versions else "",  # MC Version
            6: lambda m: m.is_enabled,  # Status
        }
        
        if column_index in sort_keys:
            self._full_mod_list.sort(key=sort_keys[column_index], reverse=self._sort_reverse)
            
            # Clear search and refresh table
            search_input = self.query_one("#search-input", Input)
            search_input.value = ""
            self._refresh_table()
            
            # Log sort action
            log = self.query_one("#log-panel", RichLog)
            direction = "↓" if self._sort_reverse else "↑"
            log.write(f"[dim]Sorted by column {column_index + 1} {direction}[/]")
    
    def _refresh_table(self) -> None:
        """Refresh the table with current mod list."""
        table = self.query_one("#results-table", DataTable)
        table.clear()
        
        for mod in self._full_mod_list:
            status = "✅" if mod.is_enabled else "❌"
            deps_count = str(len(mod.dependencies)) if mod.dependencies else "0"
            mc_vers = ", ".join(mod.mc_versions[:2]) if mod.mc_versions else "-"
            if mod.mc_versions and len(mod.mc_versions) > 2:
                mc_vers += "..."
            
            table.add_row(
                mod.name,
                mod.loader.capitalize(),
                mod.version,
                mod.author or "-",
                deps_count,
                mc_vers,
                status
            )
    
    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_pressed(self) -> None:
        """Cancel the running scan."""
        self._cancel_event.set()
        log = self.query_one("#log-panel", RichLog)
        log.write("[yellow]⏹ Cancellation requested...[/]")
        self.query_one("#status-label", Static).update("Cancelling...")
    
    def action_cancel_scan(self) -> None:
        """Cancel scan action (bound to Escape key)."""
        if not self.query_one("#cancel-btn", Button).disabled:
            self.on_cancel_pressed()
    
    def action_focus_search(self) -> None:
        """Focus the search input (bound to / key)."""
        self.query_one("#search-input", Input).focus()
    
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
        self._cancel_event.clear()  # Reset cancel event
        
        # Enable cancel button, disable scan button
        self.call_from_thread(self._set_scanning_ui, True)
        
        # Get settings
        recursive = self.query_one("#recursive-check", Checkbox).value
        include_disabled = self.query_one("#disabled-check", Checkbox).value
        workers = self.query_one("#workers-select", Select).value or 4
        
        # Update UI
        self.call_from_thread(self._update_status, "Scanning...", 0)
        log = self.query_one("#log-panel", RichLog)
        self.call_from_thread(log.write, f"Starting scan of [cyan]{self.input_folder}[/]...")
        
        try:
            # Create scanner with cache support
            cache = None
            if self.config.enable_cache:
                cache = ScanCache(self.config.get_cache_dir())
                self.call_from_thread(log.write, "[dim]Cache: enabled[/dim]")
            
            scanner = ModScanner(
                workers=workers,
                progress_batch_size=10,
                progress_batch_interval=0.1,
                cache=cache,
                use_cache=(cache is not None)
            )
            
            def progress_callback(update: ProgressUpdate) -> None:
                # Check for cancellation
                if self._cancel_event.is_set():
                    raise InterruptedError("Scan cancelled by user")
                    
                self.call_from_thread(
                    self._update_status, 
                    f"Processing: {update.filename[:30]}...", 
                    update.current / update.total
                )
            
            result = scanner.scan_folder(
                self.input_folder,
                recursive=recursive,
                include_disabled=include_disabled,
                progress_callback=progress_callback
            )
            
            # Check cancellation after scan
            if self._cancel_event.is_set():
                raise InterruptedError("Scan cancelled by user")
            
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
            # Store full mod list for search/sort
            self._full_mod_list = list(result.mods)
            
            self.call_from_thread(self._display_results)
            self.call_from_thread(log.write, f"[bold green]Scan complete![/] Found {len(result.mods)} mods in {result.scan_duration:.2f}s")
            
        except InterruptedError as e:
            self.call_from_thread(log.write, f"[yellow]⏹ {str(e)}[/]")
            self.call_from_thread(self._update_status, "Cancelled", 0)
            
        except Exception as e:
            self.call_from_thread(log.write, f"[bold red]Error:[/] {str(e)}")
            self.call_from_thread(self._update_status, f"Error: {str(e)}", 0)
        
        finally:
            self.is_scanning = False
            self._cancel_event.clear()
            self.call_from_thread(self._set_scanning_ui, False)
            if self.scan_result:
                self.call_from_thread(self._update_status, "Ready", 1.0)
    
    def _set_scanning_ui(self, scanning: bool) -> None:
        """Update UI elements based on scanning state."""
        self.query_one("#scan-btn", Button).disabled = scanning
        self.query_one("#cancel-btn", Button).disabled = not scanning
    
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
        
        # Update errors panel
        errors_panel = self.query_one("#errors-panel", Collapsible)
        error_log = self.query_one("#error-log", RichLog)
        error_log.clear()
        
        if result.errors:
            errors_panel.title = f"⚠️ Errors ({len(result.errors)})"
            for error in result.errors:
                error_log.write(f"[red]• {error}[/]")
            errors_panel.collapsed = False
        else:
            errors_panel.title = "⚠️ Errors (0)"
            error_log.write("[dim]No errors during scan[/]")
            errors_panel.collapsed = True
        
        # Clear search input
        self.query_one("#search-input", Input).value = ""
        
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
        
        # Check if file exists and show confirmation dialog
        if output_path.exists():
            def handle_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._do_export(output_path, formatter, compact)
            
            self.push_screen(
                ConfirmScreen(
                    title="Overwrite File?",
                    message=f"'{output_path.name}' already exists.\nDo you want to overwrite it?"
                ),
                handle_confirm
            )
        else:
            self._do_export(output_path, formatter, compact)
    
    def _do_export(self, output_path: Path, formatter, compact: bool) -> None:
        """Perform the actual export operation."""
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
        # Save preference
        self.settings_mgr.save_settings({"dark_mode": self.dark})


def main():
    """Entry point for the TUI application."""
    app = ModlistGeneratorApp()
    app.run()


if __name__ == "__main__":
    main()
