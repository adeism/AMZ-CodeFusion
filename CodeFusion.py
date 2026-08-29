import os
import sys
import datetime
import logging
import re
import tempfile
import zipfile
import hashlib
import json
import argparse
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import ctypes  # For detecting hidden files on Windows
import webbrowser  # For opening the output file

# ---------------------------------------------------------------------------
# Lazy tkinter import – CLI mode must work without tkinter installed.
# ---------------------------------------------------------------------------
_tk_mod = None
_ttk_mod = None
_filedialog_mod = None
_messagebox_mod = None

def _ensure_tk():
    """Import tkinter on first use; raises ImportError if unavailable."""
    global _tk_mod, _ttk_mod, _filedialog_mod, _messagebox_mod
    if _tk_mod is None:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        _tk_mod = tk
        _ttk_mod = ttk
        _filedialog_mod = filedialog
        _messagebox_mod = messagebox
    return _tk_mod, _ttk_mod, _filedialog_mod, _messagebox_mod

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = frozenset(['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg', '.webp', '.ico'])
EXECUTABLE_EXTENSIONS_NT = frozenset(['.exe', '.bat', '.cmd', '.com', '.ps1', '.msi', '.dll'])
TEMP_BACKUP_EXTENSIONS = frozenset(['.tmp', '.temp', '.bak', '.swp', '.swo', '~'])
DEFAULT_EXCLUDE_FOLDERS = ['.git']
DEFAULT_OUTPUT_FILE = 'codefusion_output.txt'
DEFAULT_WORKER_THREADS = 4

# Pre-compiled regex for comment removal (compiled once at module level)
_BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)
_LINE_COMMENT_RE = re.compile(r'//[^\n]*')

# Approximate token estimation: ~4 chars per token for English/code
CHARS_PER_TOKEN = 4


def _file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file for deduplication."""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
    except OSError:
        return ''
    return h.hexdigest()


def _estimate_tokens(text: str) -> int:
    """Rough token count estimation for RAG optimization."""
    return max(1, len(text) // CHARS_PER_TOKEN)


# ---------------------------------------------------------------------------
# AMZCodeFusion
# ---------------------------------------------------------------------------

class AMZCodeFusion:
    """
    AMZ-CodeFusion: Human-in-the-Loop Code Documentation & Source Code Dataset Generator for RAG.

    Combines multiple code files into a single output file, optimized for creating
    source code datasets, documentation, and archives for RAG (Retrieval-Augmented Generation) applications.
    Facilitates human-in-the-loop workflows for code understanding and documentation enhancement.
    """

    def __init__(self):
        # Default settings
        self.source_dir = "."
        self.output_file = DEFAULT_OUTPUT_FILE
        self.extensions = []
        self.exclude_folders = list(DEFAULT_EXCLUDE_FOLDERS)
        self.exclude_patterns = []
        self.include_line_numbers = False
        self.include_timestamp = False
        self.include_file_size = False
        self.add_syntax_highlight = False
        self.max_file_size_mb = None
        self.create_zip_archive = False
        self.exclude_images = True
        self.exclude_executable = True
        self.exclude_temp_and_backup_files = True
        self.exclude_hidden_files = True
        self.num_worker_threads = DEFAULT_WORKER_THREADS
        self.include_skipped_folders_detail = True
        self.include_skipped_files_detail = True
        self.exclude_comments = False
        self.exclude_line_comments = False
        self.deduplicate = False
        self.smart_chunk = False
        self.chunk_max_tokens = 2000
        self.output_format = 'txt'
        self.dry_run = False

        # Internal state
        self.lock = threading.Lock()
        self.skipped_folders = []
        self.skipped_files = []
        self.skipped_lists_lock = threading.Lock()

        # Pre-compiled user patterns
        self._compiled_patterns = []

        # Pre-computed absolute paths for excluded folders
        self._exclude_folder_abs = set()

        # Pre-computed extension frozensets for fast lookup
        self._ext_set = frozenset()
        self._image_ext_set = IMAGE_EXTENSIONS
        self._exec_ext_set_nt = EXECUTABLE_EXTENSIONS_NT
        self._temp_ext_set = TEMP_BACKUP_EXTENSIONS

        # Deduplication state
        self._seen_hashes = {}
        self._seen_hashes_lock = threading.Lock()

        # GUI references
        self.root = None
        self.progress_var = None
        self.progress_bar = None

    # ------------------------------------------------------------------
    # Pre-computation helpers (called once before processing)
    # ------------------------------------------------------------------

    def _precompute(self):
        """Pre-compile patterns and pre-compute lookup sets for performance."""
        self._compiled_patterns = []
        for pat in self.exclude_patterns:
            try:
                self._compiled_patterns.append(re.compile(pat))
            except re.error as e:
                logging.warning(f"Invalid regex pattern '{pat}': {e}")

        self._exclude_folder_abs = set()
        for folder in self.exclude_folders:
            self._exclude_folder_abs.add(os.path.abspath(os.path.join(self.source_dir, folder)))

        self._ext_set = frozenset(ext.lower().lstrip('.') for ext in self.extensions) if self.extensions else frozenset()
        self._seen_hashes = {}

    # ------------------------------------------------------------------
    # GUI
    # ------------------------------------------------------------------

    def get_user_preferences(self):
        """Opens a GUI window to get user preferences."""
        tk, ttk, filedialog, messagebox = _ensure_tk()

        if self.root:
            return

        self.root = tk.Tk()
        self.root.title("AMZ-CodeFusion Configuration")
        self.root.resizable(True, True)

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, sticky='nsew')
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        row = 0

        # Source directory
        ttk.Label(main_frame, text="Source Code Directory:").grid(row=row, column=0, sticky='e', padx=5, pady=2)
        self.source_dir_var = tk.StringVar(value=self.source_dir)
        ttk.Entry(main_frame, textvariable=self.source_dir_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        ttk.Button(main_frame, text="Browse...", command=self.browse_source_dir).grid(row=row, column=2, padx=5, pady=2)
        row += 1

        # Output file
        ttk.Label(main_frame, text="Output Dataset File Name:").grid(row=row, column=0, sticky='e', padx=5, pady=2)
        self.output_file_var = tk.StringVar(value=self.output_file)
        ttk.Entry(main_frame, textvariable=self.output_file_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        ttk.Button(main_frame, text="Browse...", command=self.browse_output_file).grid(row=row, column=2, padx=5, pady=2)
        row += 1

        # Output format
        ttk.Label(main_frame, text="Output Format:").grid(row=row, column=0, sticky='e', padx=5, pady=2)
        self.output_format_var = tk.StringVar(value=self.output_format)
        fmt_frame = ttk.Frame(main_frame)
        fmt_frame.grid(row=row, column=1, columnspan=2, sticky='w', padx=5, pady=2)
        for fmt in ('txt', 'json', 'markdown'):
            ttk.Radiobutton(fmt_frame, text=fmt.upper(), value=fmt, variable=self.output_format_var).pack(side='left', padx=5)
        row += 1

        # File extensions
        ttk.Label(main_frame, text="Code File Extensions (comma-separated):").grid(row=row, column=0, sticky='e', padx=5, pady=2)
        self.extensions_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.extensions_var, width=50).grid(row=row, column=1, columnspan=2, padx=5, pady=2)
        row += 1

        # Exclude folders
        ttk.Label(main_frame, text="Exclude Folders (comma-separated):").grid(row=row, column=0, sticky='e', padx=5, pady=2)
        self.exclude_folders_var = tk.StringVar(value=','.join(self.exclude_folders))
        ttk.Entry(main_frame, textvariable=self.exclude_folders_var, width=50).grid(row=row, column=1, columnspan=2, padx=5, pady=2)
        row += 1

        # Exclude patterns
        ttk.Label(main_frame, text="Regex Patterns to Exclude:").grid(row=row, column=0, sticky='e', padx=5, pady=2)
        self.exclude_patterns_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.exclude_patterns_var, width=50).grid(row=row, column=1, columnspan=2, padx=5, pady=2)
        row += 1

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=5)
        row += 1

        # Boolean options
        self.include_line_numbers_var = tk.BooleanVar(value=self.include_line_numbers)
        self.include_timestamp_var = tk.BooleanVar(value=self.include_timestamp)
        self.include_file_size_var = tk.BooleanVar(value=self.include_file_size)
        self.add_syntax_highlight_var = tk.BooleanVar(value=self.add_syntax_highlight)
        self.create_zip_archive_var = tk.BooleanVar(value=self.create_zip_archive)
        self.exclude_images_var = tk.BooleanVar(value=self.exclude_images)
        self.exclude_executable_var = tk.BooleanVar(value=self.exclude_executable)
        self.exclude_temp_and_backup_files_var = tk.BooleanVar(value=self.exclude_temp_and_backup_files)
        self.exclude_hidden_files_var = tk.BooleanVar(value=self.exclude_hidden_files)
        self.exclude_comments_var = tk.BooleanVar(value=self.exclude_comments)
        self.exclude_line_comments_var = tk.BooleanVar(value=self.exclude_line_comments)
        self.include_skipped_folders_detail_var = tk.BooleanVar(value=self.include_skipped_folders_detail)
        self.include_skipped_files_detail_var = tk.BooleanVar(value=self.include_skipped_files_detail)
        self.deduplicate_var = tk.BooleanVar(value=self.deduplicate)
        self.smart_chunk_var = tk.BooleanVar(value=self.smart_chunk)
        self.dry_run_var = tk.BooleanVar(value=self.dry_run)

        chk_opts = [
            ("Line Numbers", self.include_line_numbers_var),
            ("Timestamp", self.include_timestamp_var),
            ("File Size", self.include_file_size_var),
            ("Syntax Highlight", self.add_syntax_highlight_var),
            ("Zip Archive", self.create_zip_archive_var),
            ("Exclude Images", self.exclude_images_var),
            ("Exclude Executables", self.exclude_executable_var),
            ("Exclude Temp/Backup", self.exclude_temp_and_backup_files_var),
            ("Exclude Hidden", self.exclude_hidden_files_var),
            ("Exclude Comments (/* */)", self.exclude_comments_var),
            ("Exclude Line Comments (//)", self.exclude_line_comments_var),
            ("Deduplicate Files", self.deduplicate_var),
            ("Smart Chunking (RAG)", self.smart_chunk_var),
            ("Dry Run (Preview Only)", self.dry_run_var),
            ("Include Skipped Folders Detail", self.include_skipped_folders_detail_var),
            ("Include Skipped Files Detail", self.include_skipped_files_detail_var),
        ]

        for i, (label, var) in enumerate(chk_opts):
            r = row + (i // 3)
            c = i % 3
            ttk.Checkbutton(main_frame, text=label, variable=var).grid(row=r, column=c, sticky='w', padx=5, pady=1)
        row += (len(chk_opts) + 2) // 3

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=5)
        row += 1

        # Max file size
        ttk.Label(main_frame, text="Max File Size (MB):").grid(row=row, column=0, sticky='e', padx=5, pady=2)
        self.max_file_size_mb_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.max_file_size_mb_var, width=10).grid(row=row, column=1, sticky='w', padx=5, pady=2)
        row += 1

        # Worker threads
        ttk.Label(main_frame, text="Worker Threads:").grid(row=row, column=0, sticky='e', padx=5, pady=2)
        self.num_worker_threads_var = tk.StringVar(value=str(self.num_worker_threads))
        ttk.Entry(main_frame, textvariable=self.num_worker_threads_var, width=10).grid(row=row, column=1, sticky='w', padx=5, pady=2)
        row += 1

        # Config presets
        ttk.Label(main_frame, text="Config Preset:").grid(row=row, column=0, sticky='e', padx=5, pady=2)
        preset_frame = ttk.Frame(main_frame)
        preset_frame.grid(row=row, column=1, columnspan=2, sticky='w', padx=5, pady=2)
        ttk.Button(preset_frame, text="Save Config", command=self.save_config).pack(side='left', padx=2)
        ttk.Button(preset_frame, text="Load Config", command=self.load_config).pack(side='left', padx=2)
        row += 1

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=5)
        row += 1

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100, length=400)
        self.progress_bar.grid(row=row, column=0, columnspan=3, padx=5, pady=5)
        row += 1

        # Progress label
        self.progress_label = ttk.Label(main_frame, text="")
        self.progress_label.grid(row=row, column=0, columnspan=3)
        row += 1

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=10)
        ttk.Button(btn_frame, text="Start Fusion", command=self.on_start).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.on_cancel).pack(side='left', padx=5)

        self.root.mainloop()

    # ------------------------------------------------------------------
    # Config save/load
    # ------------------------------------------------------------------

    def save_config(self):
        """Save current GUI settings to a JSON preset file."""
        tk, ttk, filedialog, messagebox = _ensure_tk()
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Configuration Preset"
        )
        if not filepath:
            return
        try:
            config = {
                'source_dir': self.source_dir_var.get(),
                'output_file': self.output_file_var.get(),
                'output_format': self.output_format_var.get(),
                'extensions': self.extensions_var.get(),
                'exclude_folders': self.exclude_folders_var.get(),
                'exclude_patterns': self.exclude_patterns_var.get(),
                'include_line_numbers': self.include_line_numbers_var.get(),
                'include_timestamp': self.include_timestamp_var.get(),
                'include_file_size': self.include_file_size_var.get(),
                'add_syntax_highlight': self.add_syntax_highlight_var.get(),
                'create_zip_archive': self.create_zip_archive_var.get(),
                'exclude_images': self.exclude_images_var.get(),
                'exclude_executable': self.exclude_executable_var.get(),
                'exclude_temp_and_backup_files': self.exclude_temp_and_backup_files_var.get(),
                'exclude_hidden_files': self.exclude_hidden_files_var.get(),
                'exclude_comments': self.exclude_comments_var.get(),
                'exclude_line_comments': self.exclude_line_comments_var.get(),
                'deduplicate': self.deduplicate_var.get(),
                'smart_chunk': self.smart_chunk_var.get(),
                'dry_run': self.dry_run_var.get(),
                'include_skipped_folders_detail': self.include_skipped_folders_detail_var.get(),
                'include_skipped_files_detail': self.include_skipped_files_detail_var.get(),
                'max_file_size_mb': self.max_file_size_mb_var.get(),
                'num_worker_threads': self.num_worker_threads_var.get(),
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("Saved", f"Configuration saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save configuration: {e}")

    def load_config(self):
        """Load settings from a JSON preset file into the GUI."""
        tk, ttk, filedialog, messagebox = _ensure_tk()
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Configuration Preset"
        )
        if not filepath:
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.source_dir_var.set(config.get('source_dir', '.'))
            self.output_file_var.set(config.get('output_file', DEFAULT_OUTPUT_FILE))
            self.output_format_var.set(config.get('output_format', 'txt'))
            self.extensions_var.set(config.get('extensions', ''))
            self.exclude_folders_var.set(config.get('exclude_folders', ','.join(DEFAULT_EXCLUDE_FOLDERS)))
            self.exclude_patterns_var.set(config.get('exclude_patterns', ''))
            self.include_line_numbers_var.set(config.get('include_line_numbers', False))
            self.include_timestamp_var.set(config.get('include_timestamp', False))
            self.include_file_size_var.set(config.get('include_file_size', False))
            self.add_syntax_highlight_var.set(config.get('add_syntax_highlight', False))
            self.create_zip_archive_var.set(config.get('create_zip_archive', False))
            self.exclude_images_var.set(config.get('exclude_images', True))
            self.exclude_executable_var.set(config.get('exclude_executable', True))
            self.exclude_temp_and_backup_files_var.set(config.get('exclude_temp_and_backup_files', True))
            self.exclude_hidden_files_var.set(config.get('exclude_hidden_files', True))
            self.exclude_comments_var.set(config.get('exclude_comments', False))
            self.exclude_line_comments_var.set(config.get('exclude_line_comments', False))
            self.deduplicate_var.set(config.get('deduplicate', False))
            self.smart_chunk_var.set(config.get('smart_chunk', False))
            self.dry_run_var.set(config.get('dry_run', False))
            self.include_skipped_folders_detail_var.set(config.get('include_skipped_folders_detail', True))
            self.include_skipped_files_detail_var.set(config.get('include_skipped_files_detail', True))
            self.max_file_size_mb_var.set(config.get('max_file_size_mb', ''))
            self.num_worker_threads_var.set(config.get('num_worker_threads', str(DEFAULT_WORKER_THREADS)))
            messagebox.showinfo("Loaded", f"Configuration loaded from {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load configuration: {e}")

    # ------------------------------------------------------------------
    # Output writing (buffered I/O – single file handle)
    # ------------------------------------------------------------------

    def _write_output(self, file_results, files_processed, total_size, total_tokens):
        """Write the complete output in the selected format. Uses buffered I/O."""
        fmt = self.output_format
        try:
            with open(self.output_file, 'w', encoding='utf-8', buffering=1024 * 1024) as out:
                if fmt == 'json':
                    self._write_json_output(out, file_results, files_processed, total_size, total_tokens)
                elif fmt == 'markdown':
                    self._write_markdown_output(out, file_results, files_processed, total_size, total_tokens)
                else:
                    self._write_txt_output(out, file_results, files_processed, total_size, total_tokens)
        except Exception as e:
            logging.error(f"Error writing output file: {e}")
            if self.root:
                tk, ttk, filedialog, messagebox = _ensure_tk()
                messagebox.showerror("File Error", f"Could not write output file: {e}")

    def _write_txt_output(self, out, file_results, files_processed, total_size, total_tokens):
        """Write plain text output (original format)."""
        out.write(f"# AMZ-CodeFusion Output - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        out.write(f"Source Code Directory: {os.path.abspath(self.source_dir)}\n")
        if self.extensions:
            out.write(f"Included Code Extensions: {', '.join(self.extensions)}\n")
        if self.exclude_folders != list(DEFAULT_EXCLUDE_FOLDERS):
            out.write(f"Excluded Folders: {', '.join(self.exclude_folders)}\n")
        if self.exclude_patterns:
            out.write(f"Excluded Patterns: {', '.join(self.exclude_patterns)}\n")
        if total_tokens > 0:
            out.write(f"Estimated Tokens: {total_tokens:,}\n")
        out.write("\n")

        for rel_path, content in file_results:
            out.write(f"\n## File: {rel_path}\n")
            if self.add_syntax_highlight:
                ext = os.path.splitext(rel_path)[1].lstrip('.')
                out.write(f"```{ext}\n")
            if self.include_line_numbers:
                for i, line in enumerate(content.splitlines(), 1):
                    out.write(f"{i:4d} | {line}\n")
            else:
                out.write(content)
            if self.add_syntax_highlight:
                out.write("```\n")
            out.write("\n")

        out.write(f"\n---\nCode Files Processed: {files_processed}\n")
        out.write(f"Total Dataset Size: {total_size / 1024 / 1024:.2f} MB\n")
        if total_tokens > 0:
            out.write(f"Total Estimated Tokens: {total_tokens:,}\n")

        self._write_skipped_summary_txt(out)

    def _write_markdown_output(self, out, file_results, files_processed, total_size, total_tokens):
        """Write Markdown output with table of contents and metadata."""
        out.write(f"# AMZ-CodeFusion Code Dataset\n\n")
        out.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        out.write(f"**Source:** `{os.path.abspath(self.source_dir)}`\n\n")
        if self.extensions:
            out.write(f"**Extensions:** {', '.join(self.extensions)}\n\n")
        if total_tokens > 0:
            out.write(f"**Estimated Tokens:** {total_tokens:,}\n\n")
        out.write(f"**Files:** {files_processed} | **Size:** {total_size / 1024 / 1024:.2f} MB\n\n")
        out.write("---\n\n")

        # Table of contents
        out.write("## Table of Contents\n\n")
        for i, (rel_path, _) in enumerate(file_results, 1):
            out.write(f"{i}. `{rel_path}`\n")
        out.write("\n---\n\n")

        for i, (rel_path, content) in enumerate(file_results, 1):
            ext = os.path.splitext(rel_path)[1].lstrip('.')
            out.write(f"## {i}. `{rel_path}`\n\n")
            out.write(f"```{ext}\n")
            if self.include_line_numbers:
                for ln, line in enumerate(content.splitlines(), 1):
                    out.write(f"{ln:4d} | {line}\n")
            else:
                out.write(content)
            out.write("\n```\n\n")

        out.write("---\n\n")
        out.write(f"## Summary\n\n")
        out.write(f"- **Files Processed:** {files_processed}\n")
        out.write(f"- **Total Size:** {total_size / 1024 / 1024:.2f} MB\n")
        if total_tokens > 0:
            out.write(f"- **Estimated Tokens:** {total_tokens:,}\n")
        self._write_skipped_summary_md(out)

    def _write_json_output(self, out, file_results, files_processed, total_size, total_tokens):
        """Write structured JSON output for programmatic RAG ingestion."""
        files_json = []
        for rel_path, content in file_results:
            entry = {
                "path": rel_path,
                "content": content,
                "size_bytes": len(content.encode('utf-8', errors='replace')),
                "tokens": _estimate_tokens(content),
            }
            files_json.append(entry)

        output = {
            "metadata": {
                "tool": "AMZ-CodeFusion",
                "generated": datetime.datetime.now().isoformat(),
                "source_directory": os.path.abspath(self.source_dir),
                "extensions": self.extensions if self.extensions else None,
                "excluded_folders": self.exclude_folders,
                "excluded_patterns": self.exclude_patterns,
                "files_processed": files_processed,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "estimated_tokens": total_tokens,
            },
            "files": files_json,
            "skipped_folders": [os.path.relpath(f, self.source_dir) for f in self.skipped_folders],
            "skipped_files": [os.path.relpath(f, self.source_dir) for f in self.skipped_files],
        }
        json.dump(output, out, indent=2, ensure_ascii=False)

    def _write_skipped_summary_txt(self, out):
        """Write skipped items summary in text format."""
        if self.include_skipped_folders_detail and self.skipped_folders:
            out.write("\nSkipped Folders:\n")
            for folder in self.skipped_folders:
                out.write(f"- {os.path.relpath(folder, self.source_dir)}\n")
        elif self.skipped_folders:
            out.write(f"\nSkipped Folders Count: {len(self.skipped_folders)}\n")

        if self.include_skipped_files_detail and self.skipped_files:
            out.write("\nSkipped Files:\n")
            for file in self.skipped_files:
                out.write(f"- {os.path.relpath(file, self.source_dir)}\n")
        elif self.skipped_files:
            out.write(f"Skipped Files Count: {len(self.skipped_files)}\n")

    def _write_skipped_summary_md(self, out):
        """Write skipped items summary in markdown format."""
        if self.include_skipped_folders_detail and self.skipped_folders:
            out.write(f"### Skipped Folders ({len(self.skipped_folders)})\n\n")
            for folder in self.skipped_folders:
                out.write(f"- `{os.path.relpath(folder, self.source_dir)}`\n")
            out.write("\n")
        elif self.skipped_folders:
            out.write(f"- **Skipped Folders:** {len(self.skipped_folders)}\n")

        if self.include_skipped_files_detail and self.skipped_files:
            out.write(f"### Skipped Files ({len(self.skipped_files)})\n\n")
            for file in self.skipped_files:
                out.write(f"- `{os.path.relpath(file, self.source_dir)}`\n")
            out.write("\n")
        elif self.skipped_files:
            out.write(f"- **Skipped Files:** {len(self.skipped_files)}\n")

    # ------------------------------------------------------------------
    # Smart chunking for RAG
    # ------------------------------------------------------------------

    def _chunk_content(self, content: str, rel_path: str):
        """Split file content into chunks for RAG-optimized output.

        Splits on function/class boundaries when possible, falls back to line-based chunking.
        """
        max_chars = self.chunk_max_tokens * CHARS_PER_TOKEN
        lines = content.splitlines(keepends=True)

        if len(content) <= max_chars:
            return [(rel_path, content)]

        chunks = []
        current_chunk = []
        current_size = 0

        for line in lines:
            line_len = len(line)
            if current_size + line_len > max_chars and current_chunk:
                chunk_text = ''.join(current_chunk)
                chunk_label = f"{rel_path} [chunk {len(chunks) + 1}]"
                chunks.append((chunk_label, chunk_text))
                current_chunk = []
                current_size = 0

            current_chunk.append(line)
            current_size += line_len

        if current_chunk:
            chunk_text = ''.join(current_chunk)
            chunk_label = f"{rel_path} [chunk {len(chunks) + 1}]"
            chunks.append((chunk_label, chunk_text))

        return chunks if chunks else [(rel_path, content)]

    # ------------------------------------------------------------------
    # File filtering
    # ------------------------------------------------------------------

    def browse_source_dir(self):
        """Opens a dialog to select the source code directory."""
        tk, ttk, filedialog, messagebox = _ensure_tk()
        directory = filedialog.askdirectory(initialdir=self.source_dir, title="Select Source Code Directory")
        if directory:
            self.source_dir_var.set(directory)
            source_folder_name = os.path.basename(directory)
            suggested_output_file = f"codefusion_output_{source_folder_name}.txt"
            self.output_file_var.set(suggested_output_file)

    def browse_output_file(self):
        """Opens a dialog to select the output dataset file."""
        tk, ttk, filedialog, messagebox = _ensure_tk()
        file = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=self.output_file,
                                            title="Save Output Dataset File")
        if file:
            self.output_file_var.set(file)

    def on_start(self):
        """Starts the code file combination and dataset generation process."""
        self._read_gui_values()
        if not self._validate_inputs():
            return

        self.toggle_gui_elements(disabled=True)
        if self.progress_var is not None:
            self.progress_var.set(0)

        with self.skipped_lists_lock:
            self.skipped_folders = []
            self.skipped_files = []

        threading.Thread(target=self.combine_files, daemon=True).start()

    def _read_gui_values(self):
        """Read all values from the GUI into instance variables."""
        self.source_dir = self.source_dir_var.get() or "."
        self.output_file = self.output_file_var.get() or DEFAULT_OUTPUT_FILE
        self.output_format = self.output_format_var.get() or 'txt'
        self.extensions = [ext.strip().lstrip('.') for ext in self.extensions_var.get().split(',')] if self.extensions_var.get() else []
        self.exclude_folders = [folder.strip() for folder in self.exclude_folders_var.get().split(',')] if self.exclude_folders_var.get() else list(DEFAULT_EXCLUDE_FOLDERS)
        self.exclude_patterns = [pattern.strip() for pattern in self.exclude_patterns_var.get().split(',')] if self.exclude_patterns_var.get() else []

        self.include_line_numbers = self.include_line_numbers_var.get()
        self.include_timestamp = self.include_timestamp_var.get()
        self.include_file_size = self.include_file_size_var.get()
        self.add_syntax_highlight = self.add_syntax_highlight_var.get()
        self.create_zip_archive = self.create_zip_archive_var.get()
        self.exclude_images = self.exclude_images_var.get()
        self.exclude_executable = self.exclude_executable_var.get()
        self.exclude_temp_and_backup_files = self.exclude_temp_and_backup_files_var.get()
        self.exclude_hidden_files = self.exclude_hidden_files_var.get()
        self.exclude_comments = self.exclude_comments_var.get()
        self.exclude_line_comments = self.exclude_line_comments_var.get()
        self.deduplicate = self.deduplicate_var.get()
        self.smart_chunk = self.smart_chunk_var.get()
        self.dry_run = self.dry_run_var.get()
        self.include_skipped_folders_detail = self.include_skipped_folders_detail_var.get()
        self.include_skipped_files_detail = self.include_skipped_files_detail_var.get()

        try:
            max_file_size_str = self.max_file_size_mb_var.get()
            self.max_file_size_mb = float(max_file_size_str) if max_file_size_str else None
        except ValueError:
            tk, ttk, filedialog, messagebox = _ensure_tk()
            messagebox.showerror("Invalid Input", "Max file size must be a number.")
            return

        try:
            num_worker_threads_str = self.num_worker_threads_var.get()
            if num_worker_threads_str:
                self.num_worker_threads = int(num_worker_threads_str)
                if self.num_worker_threads <= 0:
                    raise ValueError
            else:
                self.num_worker_threads = DEFAULT_WORKER_THREADS
        except ValueError:
            tk, ttk, filedialog, messagebox = _ensure_tk()
            messagebox.showerror("Invalid Input", "Number of worker threads must be a positive integer.")
            return

    def _validate_inputs(self) -> bool:
        """Validate GUI inputs before processing."""
        tk, ttk, filedialog, messagebox = _ensure_tk()
        if not os.path.isdir(self.source_dir):
            messagebox.showerror("Invalid Input", "Source code directory is not valid.")
            return False
        if not self.output_file:
            messagebox.showerror("Invalid Input", "Output dataset file name cannot be empty.")
            return False
        return True

    def on_cancel(self):
        """Handles cancel button click."""
        if self.root:
            self.root.destroy()
            self.root = None

    def toggle_gui_elements(self, disabled=False):
        """Enables or disables GUI elements. No-op in CLI mode."""
        if not self.root:
            return
        tk, ttk, filedialog, messagebox = _ensure_tk()
        state = 'disabled' if disabled else 'normal'
        for child in self.root.winfo_children():
            try:
                child.configure(state=state)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------
    # File classification helpers
    # ------------------------------------------------------------------

    def _is_executable(self, filepath: str) -> bool:
        """Checks if a file is an executable (optimized with frozenset lookup)."""
        if os.name == 'nt':
            return filepath.lower().endswith(tuple(self._exec_ext_set_nt))
        return os.access(filepath, os.X_OK)

    def _is_hidden(self, filepath: str) -> bool:
        """Checks if a file is hidden."""
        name = os.path.basename(os.path.abspath(filepath))
        if name.startswith('.'):
            return True
        if os.name == 'nt':
            try:
                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(filepath))
                assert attrs != -1
                return bool(attrs & 2)
            except (AttributeError, AssertionError, OSError):
                return False
        return False

    def should_process_file(self, filepath: str) -> bool:
        """Determines whether a code file should be included in the dataset.

        Uses pre-computed sets and compiled patterns for maximum performance.
        """
        # Extension check (fast path with frozenset)
        if self._ext_set:
            _, ext = os.path.splitext(filepath)
            ext_lower = ext.lower().lstrip('.')
            if ext_lower not in self._ext_set:
                self._add_skipped_file(filepath)
                return False

        # Excluded folder check (uses pre-computed absolute paths)
        filepath_abs = os.path.abspath(filepath)
        for exc_abs in self._exclude_folder_abs:
            if filepath_abs.startswith(exc_abs + os.sep) or filepath_abs == exc_abs:
                self._add_skipped_file(filepath)
                return False

        # Regex pattern check (uses pre-compiled patterns)
        if self._compiled_patterns and any(p.search(filepath) for p in self._compiled_patterns):
            self._add_skipped_file(filepath)
            return False

        # File size check
        try:
            file_size = os.path.getsize(filepath)
            if self.max_file_size_mb is not None and file_size > self.max_file_size_mb * 1024 * 1024:
                self._add_skipped_file(filepath)
                return False
        except OSError:
            self._add_skipped_file(filepath)
            return False

        # Image check (frozenset)
        if self.exclude_images and filepath.lower().endswith(tuple(self._image_ext_set)):
            self._add_skipped_file(filepath)
            return False

        # Executable check
        if self.exclude_executable and self._is_executable(filepath):
            self._add_skipped_file(filepath)
            return False

        # Temp/backup check (frozenset)
        if self.exclude_temp_and_backup_files:
            if filepath.lower().endswith(tuple(self._temp_ext_set)):
                self._add_skipped_file(filepath)
                return False

        # Hidden file check
        if self.exclude_hidden_files and self._is_hidden(filepath):
            self._add_skipped_file(filepath)
            return False

        return True

    def _add_skipped_file(self, filepath: str):
        """Thread-safe addition to skipped files list."""
        with self.skipped_lists_lock:
            self.skipped_files.append(filepath)

    # ------------------------------------------------------------------
    # File processing
    # ------------------------------------------------------------------

    def _remove_comments(self, text: str) -> str:
        """Removes /* ... */ style comments from text."""
        return _BLOCK_COMMENT_RE.sub('', text)

    def _remove_line_comments(self, text: str) -> str:
        """Removes // style line comments from text."""
        return _LINE_COMMENT_RE.sub('', text)

    def _process_file(self, filepath: str):
        """Processes a single code file: reads content, applies filters, returns result.

        Returns: (rel_path, content, file_size, tokens) or None if skipped/duplicate.
        """
        try:
            # Try UTF-8 first, fall back to latin-1 (which never fails)
            try:
                with open(filepath, 'r', encoding='utf-8') as infile:
                    content = infile.read()
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='latin-1') as infile:
                    content = infile.read()

            if self.exclude_comments:
                content = self._remove_comments(content)
            if self.exclude_line_comments:
                content = self._remove_line_comments(content)

            # Deduplication check
            if self.deduplicate:
                fhash = _file_hash(filepath)
                if fhash:
                    with self._seen_hashes_lock:
                        if fhash in self._seen_hashes:
                            logging.debug(f"Duplicate skipped: {filepath} (same as {self._seen_hashes[fhash]})")
                            return None
                        self._seen_hashes[fhash] = filepath

            rel_path = os.path.relpath(filepath, self.source_dir)
            file_size = os.path.getsize(filepath)
            tokens = _estimate_tokens(content)

            return (rel_path, content, file_size, tokens)

        except Exception as e:
            logging.error(f"Error processing {filepath}: {e}")
            return None

    # ------------------------------------------------------------------
    # Directory scanning (optimized)
    # ------------------------------------------------------------------

    def _scan_directory(self):
        """Scan directory and return list of file paths to process.

        Uses pre-computed exclusion sets and avoids redundant directory walks.
        """
        file_paths = []
        exclude_abs = self._exclude_folder_abs

        for dirpath, dirnames, filenames in os.walk(self.source_dir, followlinks=False):
            # Filter excluded directories in-place
            filtered_dirs = []
            for d in dirnames:
                full_dir_abs = os.path.abspath(os.path.join(dirpath, d))
                if full_dir_abs in exclude_abs:
                    with self.skipped_lists_lock:
                        self.skipped_folders.append(os.path.join(dirpath, d))
                    self._record_skipped_folder_contents(os.path.join(dirpath, d))
                else:
                    filtered_dirs.append(d)
            dirnames[:] = filtered_dirs

            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if self.should_process_file(filepath):
                    file_paths.append(filepath)

        return file_paths

    def _record_skipped_folder_contents(self, folder_path: str):
        """Record all files inside a skipped folder (lightweight walk)."""
        try:
            for dirpath, _, filenames in os.walk(folder_path, followlinks=False):
                for fn in filenames:
                    fp = os.path.join(dirpath, fn)
                    with self.skipped_lists_lock:
                        self.skipped_files.append(fp)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Main combine_files logic
    # ------------------------------------------------------------------

    def combine_files(self):
        """Combines code files from the source directory into a single output."""
        try:
            with self.skipped_lists_lock:
                self.skipped_folders = []
                self.skipped_files = []
            self._precompute()

            # Scan directory
            self._update_progress(0, "Scanning directory...")
            file_paths = self._scan_directory()

            total_files = len(file_paths)
            if total_files == 0:
                if self.root:
                    tk, ttk, filedialog, messagebox = _ensure_tk()
                    messagebox.showinfo("Information", "No code files found to process with the current settings.")
                else:
                    logging.info("No files found to process.")
                self.toggle_gui_elements(disabled=False)
                return

            logging.info(f"Found {total_files} files to process with {self.num_worker_threads} workers")
            self._update_progress(5, f"Found {total_files} files. Processing...")

            # Dry-run mode
            if self.dry_run:
                self._do_dry_run(file_paths)
                self.toggle_gui_elements(disabled=False)
                return

            # Process files using thread pool with as_completed for better progress tracking
            file_results = []
            files_processed = 0
            total_size = 0
            total_tokens = 0
            completed = 0

            with ThreadPoolExecutor(max_workers=self.num_worker_threads) as executor:
                future_to_path = {executor.submit(self._process_file, fp): fp for fp in file_paths}

                for future in as_completed(future_to_path):
                    result = future.result()
                    completed += 1

                    if result is not None:
                        rel_path, content, file_size, tokens = result

                        if self.smart_chunk:
                            chunks = self._chunk_content(content, rel_path)
                            for chunk_path, chunk_content in chunks:
                                file_results.append((chunk_path, chunk_content))
                                total_size += len(chunk_content.encode('utf-8', errors='replace'))
                                total_tokens += _estimate_tokens(chunk_content)
                                files_processed += 1
                        else:
                            file_results.append((rel_path, content))
                            total_size += file_size
                            total_tokens += tokens
                            files_processed += 1

                    if completed % max(1, total_files // 20) == 0 or completed == total_files:
                        progress = 5 + (completed / total_files) * 85
                        self._update_progress(progress, f"Processed {completed}/{total_files} files")

            # Sort results by path for consistent output
            file_results.sort(key=lambda x: x[0])

            # Write output (single buffered write)
            self._update_progress(92, "Writing output file...")
            self._write_output(file_results, files_processed, total_size, total_tokens)

            if self.create_zip_archive:
                self._update_progress(97, "Creating zip archive...")
                self._create_zip_archive()

            self._update_progress(100, "Complete!")

            logging.info(f"Combined {files_processed} code files into {self.output_file}")
            logging.info(f"Total dataset size: {total_size / 1024 / 1024:.2f} MB")
            if total_tokens > 0:
                logging.info(f"Estimated tokens: {total_tokens:,}")

            if self.root:
                tk, ttk, filedialog, messagebox = _ensure_tk()
                messagebox.showinfo("Success",
                                    f"Combined {files_processed} code files into {self.output_file}\n"
                                    f"Total dataset size: {total_size / 1024 / 1024:.2f} MB\n"
                                    f"Estimated tokens: {total_tokens:,}")
                self.open_output_file()

        except Exception as e:
            logging.error(f"An error occurred during code file combination: {e}")
            if self.root:
                tk, ttk, filedialog, messagebox = _ensure_tk()
                messagebox.showerror("Error", f"An error occurred during code file combination: {e}")
        finally:
            self.toggle_gui_elements(disabled=False)

    def _update_progress(self, percent, message):
        """Thread-safe progress update for GUI."""
        if self.root:
            try:
                self.progress_var.set(percent)
                self.progress_label.config(text=message)
                self.root.update_idletasks()
            except Exception:
                pass

    def _do_dry_run(self, file_paths):
        """Perform a dry run: analyze files and report without writing output."""
        total_size = 0
        total_tokens = 0
        ext_counts = {}

        for fp in file_paths:
            try:
                sz = os.path.getsize(fp)
                total_size += sz
                _, ext = os.path.splitext(fp)
                ext = ext.lower() or '(no ext)'
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                try:
                    with open(fp, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(fp, 'r', encoding='latin-1') as f:
                        content = f.read()
                total_tokens += _estimate_tokens(content)
            except OSError:
                pass

        report = (
            f"=== DRY RUN REPORT ===\n"
            f"Files to process: {len(file_paths)}\n"
            f"Total size: {total_size / 1024 / 1024:.2f} MB\n"
            f"Estimated tokens: {total_tokens:,}\n"
            f"\nFile types:\n"
        )
        for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
            report += f"  {ext}: {count} files\n"
        report += f"\nSkipped folders: {len(self.skipped_folders)}\n"
        report += f"Skipped files: {len(self.skipped_files)}\n"

        logging.info(report)
        if self.root:
            tk, ttk, filedialog, messagebox = _ensure_tk()
            messagebox.showinfo("Dry Run Report", report)
        else:
            print(report)

    # ------------------------------------------------------------------
    # Zip archive
    # ------------------------------------------------------------------

    def _create_zip_archive(self):
        """Creates a zip archive of the output dataset file."""
        base, _ = os.path.splitext(self.output_file)
        zip_filename = base + '.zip'
        try:
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(self.output_file, arcname=os.path.basename(self.output_file))
            logging.info(f"Created zip archive: {zip_filename}")
            if self.root:
                tk, ttk, filedialog, messagebox = _ensure_tk()
                messagebox.showinfo("Zip Archive Created", f"Created zip archive: {zip_filename}")
        except Exception as e:
            logging.error(f"Error creating zip archive: {e}")
            if self.root:
                tk, ttk, filedialog, messagebox = _ensure_tk()
                messagebox.showerror("Error", f"Error creating zip archive: {e}")

    def open_output_file(self):
        """Opens the output dataset file using the default system application."""
        try:
            webbrowser.open(self.output_file)
        except Exception as e:
            logging.error(f"Error opening output file: {e}")
            if self.root:
                tk, ttk, filedialog, messagebox = _ensure_tk()
                messagebox.showerror("Error", f"Could not open the output file: {e}")

    # ------------------------------------------------------------------
    # CLI Mode
    # ------------------------------------------------------------------

    @classmethod
    def from_cli(cls, args):
        """Create an AMZCodeFusion instance from CLI arguments (no GUI)."""
        instance = cls()
        instance.source_dir = args.source_dir
        instance.output_file = args.output
        instance.output_format = args.format
        instance.extensions = [e.strip().lstrip('.') for e in args.extensions.split(',')] if args.extensions else []
        instance.exclude_folders = [f.strip() for f in args.exclude_folders.split(',')] if args.exclude_folders else list(DEFAULT_EXCLUDE_FOLDERS)
        instance.exclude_patterns = [p.strip() for p in args.exclude_patterns.split(',')] if args.exclude_patterns else []
        instance.include_line_numbers = args.line_numbers
        instance.include_timestamp = args.timestamp
        instance.include_file_size = args.file_size
        instance.add_syntax_highlight = args.syntax_highlight
        instance.create_zip_archive = args.zip
        instance.exclude_images = not args.include_images
        instance.exclude_executable = not args.include_executables
        instance.exclude_temp_and_backup_files = not args.include_temp
        instance.exclude_hidden_files = not args.include_hidden
        instance.exclude_comments = args.exclude_comments
        instance.exclude_line_comments = args.exclude_line_comments
        instance.deduplicate = args.deduplicate
        instance.smart_chunk = args.smart_chunk
        instance.dry_run = args.dry_run
        instance.include_skipped_folders_detail = not args.no_skipped_detail
        instance.include_skipped_files_detail = not args.no_skipped_detail
        instance.max_file_size_mb = args.max_size
        instance.num_worker_threads = args.workers
        instance.root = None
        return instance


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_cli_parser() -> argparse.ArgumentParser:
    """Build the argument parser for CLI mode."""
    parser = argparse.ArgumentParser(
        prog='CodeFusion',
        description='AMZ-CodeFusion: Source Code Dataset Generator for RAG applications.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage - process all files in current directory
  python CodeFusion.py --cli -s . -o output.txt

  # Process only Python and JavaScript files
  python CodeFusion.py --cli -s ./myproject -o dataset.txt -e py,js

  # Generate JSON output with deduplication and smart chunking
  python CodeFusion.py --cli -s ./myproject -o dataset.json --format json --deduplicate --smart-chunk

  # Dry run to preview what would be processed
  python CodeFusion.py --cli -s ./myproject -o output.txt --dry-run

  # Exclude comments and use 8 workers
  python CodeFusion.py --cli -s ./myproject -o clean.txt --exclude-comments --exclude-line-comments -w 8

  # Launch GUI mode (default)
  python CodeFusion.py
"""
    )

    parser.add_argument('--cli', action='store_true', help='Run in CLI mode (no GUI)')
    parser.add_argument('-s', '--source-dir', default='.', help='Source directory to process (default: current dir)')
    parser.add_argument('-o', '--output', default=DEFAULT_OUTPUT_FILE, help='Output file path')
    parser.add_argument('--format', choices=['txt', 'json', 'markdown'], default='txt', help='Output format (default: txt)')
    parser.add_argument('-e', '--extensions', default='', help='Comma-separated file extensions (e.g., py,js,ts)')
    parser.add_argument('--exclude-folders', default=','.join(DEFAULT_EXCLUDE_FOLDERS), help='Comma-separated folders to exclude')
    parser.add_argument('--exclude-patterns', default='', help='Comma-separated regex patterns to exclude')
    parser.add_argument('--line-numbers', action='store_true', help='Include line numbers in output')
    parser.add_argument('--timestamp', action='store_true', help='Include timestamp in output')
    parser.add_argument('--file-size', action='store_true', help='Include file sizes in output')
    parser.add_argument('--syntax-highlight', action='store_true', help='Wrap code in syntax-highlight blocks')
    parser.add_argument('--zip', action='store_true', help='Create zip archive of output')
    parser.add_argument('--include-images', action='store_true', help='Include image files')
    parser.add_argument('--include-executables', action='store_true', help='Include executable files')
    parser.add_argument('--include-temp', action='store_true', help='Include temp/backup files')
    parser.add_argument('--include-hidden', action='store_true', help='Include hidden files')
    parser.add_argument('--exclude-comments', action='store_true', help='Remove /* */ block comments')
    parser.add_argument('--exclude-line-comments', action='store_true', help='Remove // line comments')
    parser.add_argument('--deduplicate', action='store_true', help='Deduplicate files by content hash')
    parser.add_argument('--smart-chunk', action='store_true', help='Chunk large files for RAG optimization')
    parser.add_argument('--dry-run', action='store_true', help='Preview files without writing output')
    parser.add_argument('--no-skipped-detail', action='store_true', help='Skip detailed skipped items listing')
    parser.add_argument('--max-size', type=float, default=None, help='Max file size in MB')
    parser.add_argument('-w', '--workers', type=int, default=DEFAULT_WORKER_THREADS, help=f'Number of worker threads (default: {DEFAULT_WORKER_THREADS})')

    return parser


def main():
    """Main entry point: CLI or GUI mode."""
    if '--cli' in sys.argv:
        parser = build_cli_parser()
        args = parser.parse_args()
        fusion = AMZCodeFusion.from_cli(args)
        fusion.combine_files()
    else:
        fusion = AMZCodeFusion()
        fusion.get_user_preferences()


if __name__ == "__main__":
    main()
