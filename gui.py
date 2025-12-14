"""
CustomTkinter GUI for Modlist Generator.

A modern desktop GUI for scanning Minecraft mod folders and generating modlists.
"""

import customtkinter as ctk
from tkinter import filedialog
from pathlib import Path
from typing import Optional, List, Any, Callable
import threading
import queue
import platform
import os

from src import __version__
from src.models import ModInfo, ScanResult
from src.scanner import ModScanner, ProgressUpdate
from src.formatters import get_formatter
from src.config import load_config
from src.cache import ScanCache

# Import SettingsManager from TUI (shared)
from tui import SettingsManager


# ============================================================================
# Custom Theme Colors
# ============================================================================

COLORS = {
    "success": ("#4CAF50", "#388E3C"),      # Green (light, dark hover)
    "error": ("#F44336", "#D32F2F"),        # Red
    "primary": ("#2196F3", "#1976D2"),      # Blue
    "warning": ("#FF9800", "#F57C00"),      # Orange
    "surface": ("#1E1E1E", "#2D2D2D"),      # Dark surfaces
    "text": ("#FFFFFF", "#B0B0B0"),         # Text colors
    "border": ("#3D3D3D", "#4D4D4D"),       # Borders
    "header": ("#2D2D2D", "#3D3D3D"),       # Table headers
    "row_even": ("#1E1E1E", "#252525"),     # Table rows
    "row_odd": ("#252525", "#2D2D2D"),
    "row_selected": ("#1976D2", "#2196F3"), # Selected row
}


# ============================================================================
# Custom DataTable Widget
# ============================================================================

class DataTable(ctk.CTkScrollableFrame):
    """Custom data table using CTkScrollableFrame with grid layout."""
    
    def __init__(
        self, 
        master, 
        headers: List[str],
        on_row_select: Optional[Callable[[int], None]] = None,
        on_header_click: Optional[Callable[[int], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        
        self.headers = headers
        self.on_row_select = on_row_select
        self.on_header_click = on_header_click
        self.rows: List[List[ctk.CTkLabel]] = []
        self.row_data: List[tuple] = []
        self.selected_row: Optional[int] = None
        self.sort_column: Optional[int] = None
        self.sort_reverse: bool = False
        
        # Configure column weights
        for i in range(len(headers)):
            self.grid_columnconfigure(i, weight=1)
        
        # Create header row
        self._create_headers()
    
    def _create_headers(self) -> None:
        """Create clickable header labels."""
        for col, header in enumerate(self.headers):
            label = ctk.CTkLabel(
                self,
                text=header,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=COLORS["header"][0],
                corner_radius=0,
                padx=10,
                pady=8,
                anchor="w"
            )
            label.grid(row=0, column=col, sticky="ew", padx=(0, 1), pady=(0, 2))
            
            # Bind click event
            label.bind("<Button-1>", lambda e, c=col: self._on_header_clicked(c))
            label.configure(cursor="hand2")
    
    def _on_header_clicked(self, column: int) -> None:
        """Handle header click for sorting."""
        if self.on_header_click:
            self.on_header_click(column)
    
    def add_row(self, data: tuple) -> None:
        """Add a row of data to the table."""
        row_idx = len(self.rows) + 1  # +1 for header row
        row_labels = []
        
        # Alternate row colors
        bg_color = COLORS["row_even"][0] if len(self.rows) % 2 == 0 else COLORS["row_odd"][0]
        
        for col, value in enumerate(data):
            label = ctk.CTkLabel(
                self,
                text=str(value),
                font=ctk.CTkFont(size=12),
                fg_color=bg_color,
                corner_radius=0,
                padx=10,
                pady=6,
                anchor="w"
            )
            label.grid(row=row_idx, column=col, sticky="ew", padx=(0, 1), pady=0)
            
            # Bind row selection
            label.bind("<Button-1>", lambda e, r=len(self.rows): self._on_row_clicked(r))
            label.configure(cursor="hand2")
            
            row_labels.append(label)
        
        self.rows.append(row_labels)
        self.row_data.append(data)
    
    def _on_row_clicked(self, row_idx: int) -> None:
        """Handle row selection."""
        # Deselect previous row
        if self.selected_row is not None and self.selected_row < len(self.rows):
            prev_bg = COLORS["row_even"][0] if self.selected_row % 2 == 0 else COLORS["row_odd"][0]
            for label in self.rows[self.selected_row]:
                label.configure(fg_color=prev_bg)
        
        # Select new row
        self.selected_row = row_idx
        for label in self.rows[row_idx]:
            label.configure(fg_color=COLORS["row_selected"][0])
        
        if self.on_row_select:
            self.on_row_select(row_idx)
    
    def clear(self) -> None:
        """Clear all rows (keep headers)."""
        for row_labels in self.rows:
            for label in row_labels:
                label.destroy()
        self.rows.clear()
        self.row_data.clear()
        self.selected_row = None
    
    def get_row_count(self) -> int:
        """Return number of data rows."""
        return len(self.rows)


# ============================================================================
# Confirmation Dialog
# ============================================================================

class ConfirmDialog(ctk.CTkToplevel):
    """Modal confirmation dialog."""
    
    def __init__(self, parent, title: str, message: str, callback: Callable[[bool], None]):
        super().__init__(parent)
        
        self.callback = callback
        self.result = False
        
        # Window setup
        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 180) // 2
        self.geometry(f"+{x}+{y}")
        
        # Content
        self.grid_columnconfigure(0, weight=1)
        
        # Icon and message
        msg_label = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=14),
            wraplength=350,
            justify="center"
        )
        msg_label.grid(row=0, column=0, padx=20, pady=(30, 20))
        
        # Buttons frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, pady=(0, 20))
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            command=self._on_cancel
        )
        cancel_btn.pack(side="left", padx=10)
        
        confirm_btn = ctk.CTkButton(
            btn_frame,
            text="Confirm",
            width=100,
            fg_color=COLORS["warning"][0],
            hover_color=COLORS["warning"][1],
            command=self._on_confirm
        )
        confirm_btn.pack(side="left", padx=10)
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Keyboard bindings
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.bind("<Return>", lambda e: self._on_confirm())
    
    def _on_cancel(self) -> None:
        self.callback(False)
        self.destroy()
    
    def _on_confirm(self) -> None:
        self.callback(True)
        self.destroy()


# ============================================================================
# Collapsible Frame
# ============================================================================

class CollapsibleFrame(ctk.CTkFrame):
    """A frame that can be collapsed/expanded."""
    
    def __init__(self, master, title: str = "", **kwargs):
        super().__init__(master, **kwargs)
        
        self._title = title
        self._collapsed = True
        
        # Header button
        self.header = ctk.CTkButton(
            self,
            text=f"▶ {title}",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            hover_color=COLORS["surface"][1],
            anchor="w",
            command=self.toggle
        )
        self.header.pack(fill="x", padx=5, pady=5)
        
        # Content frame
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        # Start collapsed - don't pack content
    
    def toggle(self) -> None:
        """Toggle collapsed state."""
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.content.pack_forget()
            self.header.configure(text=f"▶ {self._title}")
        else:
            self.content.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.header.configure(text=f"▼ {self._title}")
    
    def expand(self) -> None:
        """Expand the frame."""
        if self._collapsed:
            self.toggle()
    
    def collapse(self) -> None:
        """Collapse the frame."""
        if not self._collapsed:
            self.toggle()
    
    def set_title(self, title: str) -> None:
        """Update the title."""
        self._title = title
        prefix = "▼" if not self._collapsed else "▶"
        self.header.configure(text=f"{prefix} {title}")


# ============================================================================
# Main Application
# ============================================================================

class ModlistGeneratorApp(ctk.CTk):
    """Main GUI Application for Modlist Generator."""
    
    def __init__(self):
        super().__init__()
        
        # App configuration
        self.title(f"Modlist Generator v{__version__}")
        self.geometry("1100x700")
        self.minsize(900, 600)
        
        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Load settings and config
        self.settings_mgr = SettingsManager()
        self.config = load_config()
        
        # State
        self.scan_result: Optional[ScanResult] = None
        self._full_mod_list: List[ModInfo] = []
        self._cancel_event = threading.Event()
        self._queue = queue.Queue()
        self._sort_column: Optional[int] = None
        self._sort_reverse: bool = False
        self.is_scanning = False
        
        # Load last folder
        last_folder = self.settings_mgr.get("last_folder")
        self.input_folder = Path(last_folder) if last_folder else Path.cwd()
        
        # Build UI
        self._create_widgets()
        
        # Start queue checker
        self._check_queue()
    
    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        
        # Left panel - Settings
        self._create_settings_panel()
        
        # Right panel - Results
        self._create_results_panel()
    
    def _create_settings_panel(self) -> None:
        """Create the settings panel (left side)."""
        panel = ctk.CTkFrame(self, corner_radius=10)
        panel.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        
        panel.grid_columnconfigure(0, weight=1)
        
        # Title
        title = ctk.CTkLabel(
            panel,
            text="⚙️ Settings",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="w")
        
        # Folder selection
        folder_label = ctk.CTkLabel(panel, text="Mods Folder:", font=ctk.CTkFont(size=13))
        folder_label.grid(row=1, column=0, padx=15, pady=(10, 5), sticky="w")
        
        folder_frame = ctk.CTkFrame(panel, fg_color="transparent")
        folder_frame.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")
        folder_frame.grid_columnconfigure(0, weight=1)
        
        self.folder_entry = ctk.CTkEntry(folder_frame, placeholder_text="Select folder...")
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.folder_entry.insert(0, str(self.input_folder))
        
        browse_btn = ctk.CTkButton(
            folder_frame,
            text="📁",
            width=40,
            command=self._browse_folder
        )
        browse_btn.grid(row=0, column=1)
        
        # Output format
        format_label = ctk.CTkLabel(panel, text="Output Format:", font=ctk.CTkFont(size=13))
        format_label.grid(row=3, column=0, padx=15, pady=(10, 5), sticky="w")
        
        self.format_combo = ctk.CTkComboBox(
            panel,
            values=["JSON", "CSV", "Markdown", "YAML"],
            state="readonly"
        )
        self.format_combo.grid(row=4, column=0, padx=15, pady=(0, 10), sticky="ew")
        self.format_combo.set("JSON")
        
        # Options section
        options_label = ctk.CTkLabel(panel, text="Options:", font=ctk.CTkFont(size=13))
        options_label.grid(row=5, column=0, padx=15, pady=(10, 5), sticky="w")
        
        # Checkboxes
        self.recursive_var = ctk.BooleanVar(value=False)
        self.recursive_check = ctk.CTkCheckBox(
            panel, text="Recursive scan", variable=self.recursive_var
        )
        self.recursive_check.grid(row=6, column=0, padx=15, pady=3, sticky="w")
        
        self.disabled_var = ctk.BooleanVar(value=False)
        self.disabled_check = ctk.CTkCheckBox(
            panel, text="Include disabled mods", variable=self.disabled_var
        )
        self.disabled_check.grid(row=7, column=0, padx=15, pady=3, sticky="w")
        
        self.exclude_unknown_var = ctk.BooleanVar(value=False)
        self.exclude_unknown_check = ctk.CTkCheckBox(
            panel, text="Exclude unknown loaders", variable=self.exclude_unknown_var
        )
        self.exclude_unknown_check.grid(row=8, column=0, padx=15, pady=3, sticky="w")
        
        self.no_duplicates_var = ctk.BooleanVar(value=False)
        self.no_duplicates_check = ctk.CTkCheckBox(
            panel, text="Remove duplicates", variable=self.no_duplicates_var
        )
        self.no_duplicates_check.grid(row=9, column=0, padx=15, pady=3, sticky="w")
        
        self.compact_var = ctk.BooleanVar(value=False)
        self.compact_check = ctk.CTkCheckBox(
            panel, text="Compact JSON output", variable=self.compact_var
        )
        self.compact_check.grid(row=10, column=0, padx=15, pady=3, sticky="w")
        
        # Workers
        workers_label = ctk.CTkLabel(panel, text="Parallel Workers:", font=ctk.CTkFont(size=13))
        workers_label.grid(row=11, column=0, padx=15, pady=(15, 5), sticky="w")
        
        self.workers_combo = ctk.CTkComboBox(
            panel,
            values=["1", "2", "4", "8", "16"],
            state="readonly",
            width=100
        )
        self.workers_combo.grid(row=12, column=0, padx=15, pady=(0, 15), sticky="w")
        self.workers_combo.set("4")
        
        # Action buttons
        btn_frame = ctk.CTkFrame(panel, fg_color="transparent")
        btn_frame.grid(row=13, column=0, padx=15, pady=10, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        
        self.scan_btn = ctk.CTkButton(
            btn_frame,
            text="🔍 Scan Mods",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["success"][0],
            hover_color=COLORS["success"][1],
            height=40,
            command=self._start_scan
        )
        self.scan_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.cancel_btn = ctk.CTkButton(
            btn_frame,
            text="⏹ Cancel",
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["error"][0],
            hover_color=COLORS["error"][1],
            height=40,
            state="disabled",
            command=self._cancel_scan
        )
        self.cancel_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        
        self.export_btn = ctk.CTkButton(
            panel,
            text="💾 Export Results",
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["primary"][0],
            hover_color=COLORS["primary"][1],
            height=40,
            state="disabled",
            command=self._export_results
        )
        self.export_btn.grid(row=14, column=0, padx=15, pady=(5, 15), sticky="ew")
        
        # Progress
        self.progress_bar = ctk.CTkProgressBar(panel)
        self.progress_bar.grid(row=15, column=0, padx=15, pady=(5, 5), sticky="ew")
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(
            panel,
            text="Ready",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"][1]
        )
        self.status_label.grid(row=16, column=0, padx=15, pady=(0, 15), sticky="w")
        
        # Theme toggle at bottom
        self.theme_btn = ctk.CTkButton(
            panel,
            text="🌙 Toggle Theme",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=COLORS["surface"][1],
            command=self._toggle_theme
        )
        self.theme_btn.grid(row=17, column=0, padx=15, pady=(10, 15), sticky="ew")
    
    def _create_results_panel(self) -> None:
        """Create the results panel (right side)."""
        panel = ctk.CTkFrame(self, corner_radius=10)
        panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(4, weight=1)  # Table takes remaining space
        
        # Title
        title = ctk.CTkLabel(
            panel,
            text="📋 Results",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="w")
        
        # Search bar
        search_frame = ctk.CTkFrame(panel, fg_color="transparent")
        search_frame.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")
        search_frame.grid_columnconfigure(0, weight=1)
        
        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search mods...",
            height=35
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)
        
        # Summary
        self.summary_frame = ctk.CTkFrame(panel, fg_color=COLORS["surface"][0])
        self.summary_frame.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")
        
        self.summary_label = ctk.CTkLabel(
            self.summary_frame,
            text="No scan results yet. Click 'Scan Mods' to begin.",
            font=ctk.CTkFont(size=12),
            justify="left",
            anchor="w"
        )
        self.summary_label.pack(padx=15, pady=10, anchor="w")
        
        # Mod details collapsible
        self.details_frame = CollapsibleFrame(panel, title="📄 Mod Details")
        self.details_frame.grid(row=3, column=0, padx=15, pady=(0, 10), sticky="ew")
        
        self.details_text = ctk.CTkTextbox(
            self.details_frame.content,
            height=120,
            font=ctk.CTkFont(size=12),
            state="disabled"
        )
        self.details_text.pack(fill="both", expand=True)
        
        # Data table
        table_headers = ["Name", "Loader", "Version", "Author", "Deps", "MC Version", "Status"]
        self.data_table = DataTable(
            panel,
            headers=table_headers,
            on_row_select=self._on_row_selected,
            on_header_click=self._on_header_clicked,
            height=250
        )
        self.data_table.grid(row=4, column=0, padx=15, pady=(0, 10), sticky="nsew")
        
        # Errors collapsible
        self.errors_frame = CollapsibleFrame(panel, title="⚠️ Errors (0)")
        self.errors_frame.grid(row=5, column=0, padx=15, pady=(0, 10), sticky="ew")
        
        self.errors_text = ctk.CTkTextbox(
            self.errors_frame.content,
            height=80,
            font=ctk.CTkFont(size=11),
            state="disabled",
            text_color=COLORS["error"][0]
        )
        self.errors_text.pack(fill="both", expand=True)
        
        # Log panel
        log_label = ctk.CTkLabel(panel, text="📝 Log", font=ctk.CTkFont(size=13, weight="bold"))
        log_label.grid(row=6, column=0, padx=15, pady=(5, 5), sticky="w")
        
        self.log_text = ctk.CTkTextbox(
            panel,
            height=100,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled"
        )
        self.log_text.grid(row=7, column=0, padx=15, pady=(0, 15), sticky="ew")
        
        # Initial log message
        self._log(f"Modlist Generator v{__version__}")
        self._log("Select a mods folder and click 'Scan Mods' to begin.")
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def _browse_folder(self) -> None:
        """Open folder selection dialog."""
        folder = filedialog.askdirectory(
            title="Select Mods Folder",
            initialdir=str(self.input_folder)
        )
        if folder:
            self.input_folder = Path(folder)
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)
            self._log(f"Selected folder: {folder}")
            self.settings_mgr.save_settings({"last_folder": folder})
    
    def _on_search_changed(self, event=None) -> None:
        """Filter table based on search text."""
        if not self._full_mod_list:
            return
        
        search_text = self.search_entry.get().lower().strip()
        self.data_table.clear()
        
        for mod in self._full_mod_list:
            if search_text:
                searchable = f"{mod.name} {mod.loader} {mod.author or ''} {mod.version}".lower()
                if search_text not in searchable:
                    continue
            
            self._add_mod_to_table(mod)
    
    def _on_header_clicked(self, column: int) -> None:
        """Sort table by column."""
        if not self._full_mod_list:
            return
        
        # Toggle direction if same column
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        
        # Sort keys
        sort_keys = {
            0: lambda m: m.name.lower(),
            1: lambda m: m.loader.lower(),
            2: lambda m: m.version,
            3: lambda m: (m.author or "").lower(),
            4: lambda m: len(m.dependencies) if m.dependencies else 0,
            5: lambda m: m.mc_versions[0] if m.mc_versions else "",
            6: lambda m: not m.disabled,  # True for enabled, False for disabled
        }
        
        if column in sort_keys:
            self._full_mod_list.sort(key=sort_keys[column], reverse=self._sort_reverse)
            self.search_entry.delete(0, "end")
            self._refresh_table()
            
            direction = "↓" if self._sort_reverse else "↑"
            self._log(f"Sorted by column {column + 1} {direction}")
    
    def _on_row_selected(self, row_idx: int) -> None:
        """Show mod details when row selected."""
        if not self._full_mod_list or row_idx >= len(self._full_mod_list):
            return
        
        mod = self._full_mod_list[row_idx]
        
        # Build details
        lines = [
            f"{mod.name} v{mod.version}",
            f"Loader: {mod.loader.capitalize()}",
            f"File: {mod.filename}",
        ]
        
        if mod.author:
            lines.append(f"Author: {mod.author}")
        
        if mod.mc_versions:
            lines.append(f"MC Versions: {', '.join(mod.mc_versions)}")
        
        if mod.dependencies:
            lines.append(f"\nDependencies ({len(mod.dependencies)}):")
            for dep in mod.dependencies[:10]:
                lines.append(f"  • {dep}")
            if len(mod.dependencies) > 10:
                lines.append(f"  ... and {len(mod.dependencies) - 10} more")
        
        if mod.description:
            lines.append(f"\n{mod.description[:300]}")
        
        # Update details panel
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", "\n".join(lines))
        self.details_text.configure(state="disabled")
        
        self.details_frame.set_title(f"📄 {mod.name}")
        self.details_frame.expand()
    
    def _toggle_theme(self) -> None:
        """Toggle between light and dark mode."""
        current = ctk.get_appearance_mode()
        new_mode = "light" if current == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        self.settings_mgr.save_settings({"dark_mode": new_mode == "dark"})
    
    # =========================================================================
    # Scanning
    # =========================================================================
    
    def _start_scan(self) -> None:
        """Start scanning in background thread."""
        folder = Path(self.folder_entry.get())
        
        if not folder.exists():
            self._log("Error: Folder does not exist!")
            return
        
        if not folder.is_dir():
            self._log("Error: Path is not a directory!")
            return
        
        self.input_folder = folder
        self.is_scanning = True
        self._cancel_event.clear()
        
        # Update UI
        self.scan_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.export_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Scanning...")
        
        # Start background thread
        thread = threading.Thread(target=self._run_scan, daemon=True)
        thread.start()
    
    def _run_scan(self) -> None:
        """Run scan in background thread."""
        try:
            self._queue.put(("log", f"Starting scan of {self.input_folder}..."))
            
            # Create scanner with cache
            cache = None
            if self.config.enable_cache:
                cache = ScanCache(self.config.get_cache_dir())
                self._queue.put(("log", "Cache: enabled"))
            
            scanner = ModScanner(
                workers=int(self.workers_combo.get()),
                progress_batch_size=50,  # Batch more updates to reduce GUI lag
                progress_batch_interval=0.2,  # Slower update rate for smoother UI
                cache=cache,
                use_cache=(cache is not None)
            )
            
            def progress_callback(update: ProgressUpdate) -> None:
                if self._cancel_event.is_set():
                    raise InterruptedError("Scan cancelled by user")
                self._queue.put(("progress", update))
            
            result = scanner.scan_folder(
                self.input_folder,
                recursive=self.recursive_var.get(),
                include_disabled=self.disabled_var.get(),
                progress_callback=progress_callback
            )
            
            if self._cancel_event.is_set():
                raise InterruptedError("Scan cancelled by user")
            
            # Apply filters
            if self.exclude_unknown_var.get():
                result.mods = [m for m in result.mods if m.loader != 'unknown']
            
            if self.no_duplicates_var.get():
                seen = set()
                unique_mods = []
                for mod in result.mods:
                    key = mod.mod_id or mod.name.lower()
                    if key not in seen:
                        seen.add(key)
                        unique_mods.append(mod)
                result.mods = unique_mods
            
            self._queue.put(("result", result))
            
        except InterruptedError as e:
            self._queue.put(("cancelled", str(e)))
        except Exception as e:
            self._queue.put(("error", str(e)))
        finally:
            self._queue.put(("done", None))
    
    def _cancel_scan(self) -> None:
        """Cancel the running scan."""
        self._cancel_event.set()
        self._log("Cancellation requested...")
        self.status_label.configure(text="Cancelling...")
    
    def _check_queue(self) -> None:
        """Check queue for messages from background thread."""
        try:
            while True:
                msg_type, data = self._queue.get_nowait()
                
                if msg_type == "log":
                    self._log(data)
                
                elif msg_type == "progress":
                    update: ProgressUpdate = data
                    progress = update.current / update.total if update.total > 0 else 0
                    self.progress_bar.set(progress)
                    filename = update.filename[:30] + "..." if len(update.filename) > 30 else update.filename
                    self.status_label.configure(text=f"Processing: {filename}")
                
                elif msg_type == "result":
                    self.scan_result = data
                    self._full_mod_list = list(data.mods)
                    self._display_results()
                    self._log(f"Scan complete! Found {len(data.mods)} mods in {data.scan_duration:.2f}s")
                
                elif msg_type == "cancelled":
                    self._log(f"⏹ {data}")
                    self.status_label.configure(text="Cancelled")
                
                elif msg_type == "error":
                    self._log(f"Error: {data}")
                    self.status_label.configure(text=f"Error: {data[:30]}")
                
                elif msg_type == "done":
                    self.is_scanning = False
                    self._cancel_event.clear()
                    self.scan_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
                    if self.scan_result:
                        self.export_btn.configure(state="normal")
                        self.progress_bar.set(1)
                        self.status_label.configure(text="Ready")
        
        except queue.Empty:
            pass
        
        # Schedule next check (200ms for better performance)
        self.after(200, self._check_queue)
    
    # =========================================================================
    # Display Results
    # =========================================================================
    
    def _display_results(self) -> None:
        """Display scan results in the UI."""
        if not self.scan_result:
            return
        
        result = self.scan_result
        
        # Summary
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
        
        self.summary_label.configure(text="\n".join(summary_lines))
        
        # Table
        self._refresh_table()
        
        # Errors
        self.errors_text.configure(state="normal")
        self.errors_text.delete("1.0", "end")
        
        if result.errors:
            self.errors_frame.set_title(f"⚠️ Errors ({len(result.errors)})")
            for error in result.errors:
                self.errors_text.insert("end", f"• {error}\n")
            self.errors_frame.expand()
        else:
            self.errors_frame.set_title("⚠️ Errors (0)")
            self.errors_text.insert("end", "No errors during scan")
            self.errors_frame.collapse()
        
        self.errors_text.configure(state="disabled")
        
        # Clear search
        self.search_entry.delete(0, "end")
    
    def _refresh_table(self) -> None:
        """Refresh table with current mod list."""
        self.data_table.clear()
        
        for mod in self._full_mod_list:
            self._add_mod_to_table(mod)
    
    def _add_mod_to_table(self, mod: ModInfo) -> None:
        """Add a mod to the data table."""
        status = "✅" if not mod.disabled else "❌"
        deps_count = str(len(mod.dependencies)) if mod.dependencies else "0"
        mc_vers = ", ".join(mod.mc_versions[:2]) if mod.mc_versions else "-"
        if mod.mc_versions and len(mod.mc_versions) > 2:
            mc_vers += "..."
        
        self.data_table.add_row((
            mod.name[:35] + "..." if len(mod.name) > 35 else mod.name,
            mod.loader.capitalize(),
            mod.version[:12] + "..." if len(mod.version) > 12 else mod.version,
            (mod.author or "-")[:15],
            deps_count,
            mc_vers,
            status
        ))
    
    # =========================================================================
    # Export
    # =========================================================================
    
    def _export_results(self) -> None:
        """Export scan results to file."""
        if not self.scan_result:
            return
        
        format_name = self.format_combo.get().lower()
        formatter = get_formatter(format_name)
        
        if not formatter:
            self._log(f"Error: Unknown format '{format_name}'")
            return
        
        output_path = self.input_folder / f"modlist{formatter.extension}"
        
        # Check if file exists
        if output_path.exists():
            ConfirmDialog(
                self,
                "Overwrite File?",
                f"'{output_path.name}' already exists.\nDo you want to overwrite it?",
                lambda confirmed: self._do_export(output_path, formatter) if confirmed else None
            )
        else:
            self._do_export(output_path, formatter)
    
    def _do_export(self, output_path: Path, formatter) -> None:
        """Perform the actual export."""
        try:
            formatter.save(
                self.scan_result,
                output_path,
                include_errors=True,
                compact=self.compact_var.get()
            )
            self._log(f"Exported: {output_path}")
            self.status_label.configure(text=f"Saved to {output_path.name}")
        except Exception as e:
            self._log(f"Export error: {str(e)}")
    
    # =========================================================================
    # Logging
    # =========================================================================
    
    def _log(self, message: str) -> None:
        """Add message to log panel."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Entry point for the GUI application."""
    app = ModlistGeneratorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
