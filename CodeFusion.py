import os
import datetime
import logging
import re
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import ctypes  # For detecting hidden files on Windows
import webbrowser  # For opening the output file

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AMZCodeFusion:
    """
    AMZ-CodeFusion: Human-in-the-Loop Code Documentation & Source Code Dataset Generator for RAG.

    Combines multiple code files into a single output file, optimized for creating
    source code datasets, documentation, and archives for RAG (Retrieval-Augmented Generation) applications.
    Facilitates human-in-the-loop workflows for code understanding and documentation enhancement.
    """

    def __init__(self):
        # Default settings - Optimized for RAG & character count, code dataset focus
        self.source_dir = "."
        self.output_file = "codefusion_output.txt" # Default output file for CodeFusion
        self.extensions = []  # Empty list means all extensions are included (for code files)
        self.exclude_folders = ['.git'] # Default exclude for code repos
        self.exclude_patterns = []
        self.include_line_numbers = False # Default off for cleaner RAG datasets
        self.include_timestamp = False # Default off for cleaner RAG datasets
        self.include_file_size = False # Default off for cleaner RAG datasets
        self.add_syntax_highlight = False  # Requires manual language specification in output, default off
        self.max_file_size_mb = None
        self.create_zip_archive = False
        self.exclude_images = True  # Default True for code datasets
        self.exclude_executable = True  # Default True for code datasets
        self.exclude_temp_and_backup_files = True  # Default True for code datasets
        self.exclude_hidden_files = True  # Default True for code datasets
        self.num_worker_threads = 4
        self.lock = threading.Lock()
        self.skipped_folders = [] # To store skipped folder paths
        self.skipped_files = []   # To store skipped file paths
        self.skipped_lists_lock = threading.Lock() # Lock for skipped_folders and skipped_files
        self.include_skipped_folders_detail = True # Default True to include detail
        self.include_skipped_files_detail = True   # Default True to include detail
        self.exclude_comments = False # New feature: Exclude comments /* ... */ for cleaner datasets
        self.root = None # Initialize root to None for safety

    def get_user_preferences(self):
        """
        Opens a GUI window to get user preferences for code file combination and dataset generation using AMZ-CodeFusion.
        """
        if self.root: # Check if root already exists to prevent multiple windows
            return

        self.root = tk.Tk()
        self.root.title("AMZ-CodeFusion Configuration") # Updated title

        # Source directory
        tk.Label(self.root, text="Source Code Directory:").grid(row=0, column=0, sticky='e')
        self.source_dir_var = tk.StringVar(value=self.source_dir)
        tk.Entry(self.root, textvariable=self.source_dir_var, width=50).grid(row=0, column=1)
        tk.Button(self.root, text="Browse...", command=self.browse_source_dir).grid(row=0, column=2)

        # Output file
        tk.Label(self.root, text="Output Dataset File Name:").grid(row=1, column=0, sticky='e')
        self.output_file_var = tk.StringVar(value=self.output_file)
        tk.Entry(self.root, textvariable=self.output_file_var, width=50).grid(row=1, column=1)
        tk.Button(self.root, text="Browse...", command=self.browse_output_file).grid(row=1, column=2)

        # File extensions
        tk.Label(self.root, text="Code File Extensions (comma-separated):").grid(row=2, column=0, sticky='e') # Shortened label
        self.extensions_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.extensions_var, width=50).grid(row=2, column=1, columnspan=2)

        # Exclude folders
        tk.Label(self.root, text="Exclude Folders (comma-separated):").grid(row=3, column=0, sticky='e') # Shortened label
        self.exclude_folders_var = tk.StringVar(value=','.join(self.exclude_folders))
        tk.Entry(self.root, textvariable=self.exclude_folders_var, width=50).grid(row=3, column=1, columnspan=2)

        # Exclude patterns
        tk.Label(self.root, text="Regex Patterns to Exclude (comma-separated):\n(e.g., folder/temp, file_.*\\.tmp$)").grid(row=4, column=0, sticky='e') # Shortened label + example
        self.exclude_patterns_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.exclude_patterns_var, width=50).grid(row=4, column=1, columnspan=2)

        # Boolean options - rearranged and default values changed for RAG
        self.include_line_numbers_var = tk.BooleanVar(value=self.include_line_numbers)
        self.include_timestamp_var = tk.BooleanVar(value=self.include_timestamp)
        self.include_file_size_var = tk.BooleanVar(value=self.include_file_size)
        self.add_syntax_highlight_var = tk.BooleanVar(value=self.add_syntax_highlight)
        self.create_zip_archive_var = tk.BooleanVar(value=self.create_zip_archive)
        self.exclude_images_var = tk.BooleanVar(value=self.exclude_images)
        self.exclude_executable_var = tk.BooleanVar(value=self.exclude_executable)
        self.exclude_temp_and_backup_files_var = tk.BooleanVar(value=self.exclude_temp_and_backup_files)
        self.exclude_hidden_files_var = tk.BooleanVar(value=self.exclude_hidden_files)
        self.exclude_comments_var = tk.BooleanVar(value=self.exclude_comments) # Added for exclude comments feature
        self.include_skipped_folders_detail_var = tk.BooleanVar(value=self.include_skipped_folders_detail) # Added for skipped folders detail
        self.include_skipped_files_detail_var = tk.BooleanVar(value=self.include_skipped_files_detail)   # Added for skipped files detail


        tk.Checkbutton(self.root, text="Line Numbers", variable=self.include_line_numbers_var).grid(row=5, column=0, sticky='w', padx=20) # Shortened labels
        tk.Checkbutton(self.root, text="Timestamp", variable=self.include_timestamp_var).grid(row=5, column=1, sticky='w') # Shortened labels
        tk.Checkbutton(self.root, text="File Size", variable=self.include_file_size_var).grid(row=5, column=2, sticky='w') # Shortened labels

        tk.Checkbutton(self.root, text="Syntax Highlight", variable=self.add_syntax_highlight_var).grid(row=6, column=0, sticky='w', padx=20) # Shortened labels
        tk.Checkbutton(self.root, text="Zip Archive", variable=self.create_zip_archive_var).grid(row=6, column=1, sticky='w') # Shortened labels
        tk.Checkbutton(self.root, text="Exclude Images", variable=self.exclude_images_var).grid(row=6, column=2, sticky='w') # Shortened labels

        tk.Checkbutton(self.root, text="Exclude Executables", variable=self.exclude_executable_var).grid(row=7, column=0, sticky='w', padx=20) # Shortened labels
        tk.Checkbutton(self.root, text="Exclude Temp/Backup", variable=self.exclude_temp_and_backup_files_var).grid(row=7, column=1, sticky='w') # Shortened labels
        tk.Checkbutton(self.root, text="Exclude Hidden", variable=self.exclude_hidden_files_var).grid(row=7, column=2, sticky='w') # Shortened labels
        tk.Checkbutton(self.root, text="Exclude Comments (/* ... */)", variable=self.exclude_comments_var).grid(row=8, column=0, sticky='w', padx=20) # Added exclude comments
        tk.Checkbutton(self.root, text="Include Skipped Folders Detail", variable=self.include_skipped_folders_detail_var).grid(row=8, column=1, sticky='w') # Added skipped folders detail
        tk.Checkbutton(self.root, text="Include Skipped Files Detail", variable=self.include_skipped_files_detail_var).grid(row=8, column=2, sticky='w')   # Added skipped files detail


        # Max file size
        tk.Label(self.root, text="Max File Size (MB):").grid(row=10, column=0, sticky='e') # Shortened label
        self.max_file_size_mb_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.max_file_size_mb_var, width=10).grid(row=10, column=1, sticky='w')

        # Number of worker threads
        tk.Label(self.root, text="Worker Threads:").grid(row=11, column=0, sticky='e') # Shortened label
        self.num_worker_threads_var = tk.StringVar(value=str(self.num_worker_threads))
        tk.Entry(self.root, textvariable=self.num_worker_threads_var, width=10).grid(row=11, column=1, sticky='w')

        # Progress label
        self.progress_label = tk.Label(self.root, text="")
        self.progress_label.grid(row=12, column=0, columnspan=3)

        # Buttons
        tk.Button(self.root, text="Start Fusion", command=self.on_start).grid(row=13, column=1, pady=10) # Shortened button label, "Fusion" for AMZ-CodeFusion
        tk.Button(self.root, text="Cancel", command=self.on_cancel).grid(row=13, column=2) # Use a dedicated cancel function

        self.root.mainloop()


    def _write_summary(self):
        """Writes a concise summary header to the output dataset/archive file."""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as outfile:
                outfile.write(f"# AMZ-CodeFusion Output - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n") # Updated header for CodeFusion
                outfile.write(f"Source Code Directory: {os.path.abspath(self.source_dir)}\n") # Updated source info label
                if self.extensions:
                    outfile.write(f"Included Code Extensions: {', '.join(self.extensions)}\n") # Updated label
                if self.exclude_folders != ['.git']: # Only show if not default
                    outfile.write(f"Excluded Folders: {', '.join(self.exclude_folders)}\n")
                if self.exclude_patterns:
                    outfile.write(f"Excluded Patterns: {', '.join(self.exclude_patterns)}\n")
                outfile.write("\n")
        except Exception as e:
            logging.error(f"Error writing summary to output file: {e}")
            messagebox.showerror("File Error", f"Could not write summary to output file: {e}")

    def _write_file_header(self, outfile, filepath):
        """Writes a simplified file header: just file path, for code dataset readability."""
        outfile.write(f"\n## File: {os.path.relpath(filepath, self.source_dir)}\n") # Simplified file header, markdown style for readability


    def _write_combination_summary(self, files_processed, total_size):
        """Writes a concise combination summary for the code dataset/archive."""
        try:
            with open(self.output_file, 'a', encoding='utf-8') as outfile:
                outfile.write(f"\n---\nCode Files Processed: {files_processed}\n") # Updated summary label
                outfile.write(f"Total Dataset Size: {total_size / 1024 / 1024:.2f} MB\n") # Updated label

                if self.include_skipped_folders_detail: # Conditionally include detailed skipped folders list
                    if self.skipped_folders:
                        outfile.write("\nSkipped Folders:\n")
                        for folder in self.skipped_folders:
                            outfile.write(f"- {os.path.relpath(folder, self.source_dir)}\n") # Use relative path
                elif self.skipped_folders: # Show just count if detailed list is off, but something was skipped
                    outfile.write(f"\nSkipped Folders Count: {len(self.skipped_folders)}\n") # Just show counts

                if self.include_skipped_files_detail:   # Conditionally include detailed skipped files list
                    if self.skipped_files:
                        outfile.write("\nSkipped Files:\n")
                        for file in self.skipped_files:
                            outfile.write(f"- {os.path.relpath(file, self.source_dir)}\n") # Use relative path
                elif self.skipped_files: # Show just count if detailed list is off, but something was skipped
                    outfile.write(f"Skipped Files Count: {len(self.skipped_files)}\n")
        except Exception as e:
            logging.error(f"Error writing combination summary to output file: {e}")
            messagebox.showerror("File Error", f"Could not write combination summary to output file: {e}")


    def browse_source_dir(self):
        """Opens a dialog to select the source code directory and suggests output dataset filename."""
        directory = filedialog.askdirectory(initialdir=self.source_dir, title="Select Source Code Directory") # Updated title
        if directory:
            self.source_dir_var.set(directory)
            # Suggest output filename based on source directory name
            source_folder_name = os.path.basename(directory)
            suggested_output_file = f"codefusion_output_{source_folder_name}.txt" # Updated suggested filename
            self.output_file_var.set(suggested_output_file) # Update output_file_var

    def browse_output_file(self):
        """Opens a dialog to select the output dataset file."""
        file = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=self.output_file, title="Save Output Dataset File") # Updated title
        if file:
            self.output_file_var.set(file)

    def on_start(self):
        """Starts the code file combination and dataset generation process in AMZ-CodeFusion."""
        # Retrieve values from GUI
        self.source_dir = self.source_dir_var.get() or "."
        self.output_file = self.output_file_var.get() or "codefusion_output.txt" # Default output file name updated
        self.extensions = [ext.strip() for ext in self.extensions_var.get().split(',')] if self.extensions_var.get() else []
        self.exclude_folders = [folder.strip() for folder in self.exclude_folders_var.get().split(',')] if self.exclude_folders_var.get() else ['.git']
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
        self.exclude_comments = self.exclude_comments_var.get() # Get the value for exclude comments
        self.include_skipped_folders_detail = self.include_skipped_folders_detail_var.get() # Get value for skipped folders detail
        self.include_skipped_files_detail = self.include_skipped_files_detail_var.get()   # Get value for skipped files detail


        try:
            max_file_size_str = self.max_file_size_mb_var.get()
            if max_file_size_str: # Only attempt to convert if not empty
                self.max_file_size_mb = float(max_file_size_str)
            else:
                self.max_file_size_mb = None # Explicitly set to None if empty
        except ValueError:
            messagebox.showerror("Invalid Input", "Max file size must be a number.")
            return

        try:
            num_worker_threads_str = self.num_worker_threads_var.get()
            if num_worker_threads_str: # Only attempt to convert if not empty
                self.num_worker_threads = int(num_worker_threads_str)
                if self.num_worker_threads <= 0:
                    raise ValueError
            else:
                self.num_worker_threads = 4 # Revert to default if empty or invalid
        except ValueError:
            messagebox.showerror("Invalid Input", "Number of worker threads must be a positive integer.")
            return

        if not os.path.isdir(self.source_dir): # Validate source directory
            messagebox.showerror("Invalid Input", "Source code directory is not valid.") # Updated message
            return

        if not self.output_file: # Validate output file name
            messagebox.showerror("Invalid Input", "Output dataset file name cannot be empty.") # Updated message
            return

        # Disable the GUI elements while processing
        self.toggle_gui_elements(disabled=True)

        # Reset skipped lists before each run
        with self.skipped_lists_lock:
            self.skipped_folders = []
            self.skipped_files = []

        # Start the file combination in a separate thread to keep the GUI responsive
        threading.Thread(target=self.combine_files).start()

    def on_cancel(self):
        """Handles cancel button click - destroys the GUI window for AMZ-CodeFusion."""
        if self.root:
            self.root.destroy()
            self.root = None # Reset root

    def toggle_gui_elements(self, disabled=False):
        """Enables or disables GUI elements of AMZ-CodeFusion."""
        state = 'disabled' if disabled else 'normal'
        if self.root: # Check if root exists before accessing its children
            for child in self.root.winfo_children():
                child.configure(state=state)

    def is_executable(self, filepath):
        """Checks if a file is an executable."""
        if os.name == 'nt':
            executable_extensions = ['.exe', '.bat', '.cmd', '.com', '.ps1']
            return filepath.lower().endswith(tuple(executable_extensions))
        else:
            return os.access(filepath, os.X_OK)

    def is_hidden(self, filepath):
        """Checks if a file is hidden."""
        name = os.path.basename(os.path.abspath(filepath))
        if name.startswith('.'):
            return True
        else:
            if os.name == 'nt':
                try:
                    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(filepath))
                    assert attrs != -1
                    return bool(attrs & 2)
                except (AttributeError, AssertionError):
                    return False
            else:
                return False

    def should_process_file(self, filepath: str) -> bool:
        """Determines whether a code file should be included in the dataset based on user settings.

        Important notes:
        - Regex patterns specified by the user are matched *anywhere* in the file path (using re.search).
          To match from the beginning of the path, the regex pattern must start with '^'.
        - Hidden file detection using ctypes is only applicable to Windows. On other platforms,
          hidden file detection is based solely on the filename starting with '.'.
        """
        # Check file extension
        if self.extensions and not any(filepath.lower().endswith(ext.lower()) for ext in self.extensions): # Case-insensitive extension check
            logging.debug(f"Excluded {filepath} due to extension filter.")
            with self.skipped_lists_lock: # Protect access to skipped_files
                self.skipped_files.append(filepath) # Add to skipped files list
            return False

        # Check if file is in an excluded folder
        if any(os.path.abspath(os.path.join(self.source_dir, folder)) in os.path.abspath(filepath) for folder in self.exclude_folders):
            logging.debug(f"Excluded {filepath} because it is in an excluded folder.")
            with self.skipped_lists_lock: # Protect access to skipped_files
                self.skipped_files.append(filepath) # Add to skipped files list # Even if folder is excluded, we record the file as skipped
            return False

        # Check exclude patterns
        if self.exclude_patterns and any(re.search(pattern, filepath) for pattern in self.exclude_patterns): # Use re.search for pattern matching anywhere in the path
            logging.debug(f"Excluded {filepath} due to exclude pattern.")
            with self.skipped_lists_lock: # Protect access to skipped_files
                self.skipped_files.append(filepath) # Add to skipped files list
            return False

        # Check file size
        try:
            file_size = os.path.getsize(filepath)
            if self.max_file_size_mb is not None and file_size > self.max_file_size_mb * 1024 * 1024: # Check if max_file_size_mb is set
                logging.debug(f"Excluded {filepath} due to size limit.")
                with self.skipped_lists_lock: # Protect access to skipped_files
                    self.skipped_files.append(filepath) # Add to skipped files list
                return False
        except OSError:
            logging.warning(f"Could not get size of {filepath}. Skipping.")
            with self.skipped_lists_lock: # Protect access to skipped_files
                self.skipped_files.append(filepath) # Add to skipped files list due to error getting size
            return False

        # Exclude images - case-insensitive check - **SVG ADDED HERE**
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg']
        if self.exclude_images and any(filepath.lower().endswith(ext) for ext in image_extensions):
            logging.debug(f"Excluded {filepath} because it is an image.")
            with self.skipped_lists_lock: # Protect access to skipped_files
                self.skipped_files.append(filepath) # Add to skipped files list
            return False

        # Exclude executables
        if self.exclude_executable and self.is_executable(filepath):
            logging.debug(f"Excluded {filepath} because it is executable.")
            with self.skipped_lists_lock: # Protect access to skipped_files
                self.skipped_files.append(filepath) # Add to skipped files list
            return False

        # Exclude temp and backup files
        if self.exclude_temp_and_backup_files and (filepath.startswith(tempfile.gettempdir()) or any(filepath.lower().endswith(ext) for ext in ['.tmp', '.temp', '.bak', '~'])): # Case-insensitive extension check
            logging.debug(f"Excluded {filepath} because it is a temp or backup file.")
            with self.skipped_lists_lock: # Protect access to skipped_files
                self.skipped_files.append(filepath) # Add to skipped files list
            return False

        # Exclude hidden files
        if self.exclude_hidden_files and self.is_hidden(filepath):
            logging.debug(f"Excluded {filepath} because it is hidden.")
            with self.skipped_lists_lock: # Protect access to skipped_files
                self.skipped_files.append(filepath) # Add to skipped files list
            return False

        return True

    def _remove_comments(self, text):
        """Removes /* ... */ style comments from text for cleaner code datasets."""
        return re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    def _process_file(self, filepath: str):
        """Processes a single code file: reads content, applies filters, and writes to the output dataset."""
        try:
            with open(filepath, 'r', encoding='utf-8') as infile:
                content = infile.read()

            if self.exclude_comments: # Add condition to remove comments
                content = self._remove_comments(content)

            with self.lock:  # Lock to prevent race conditions with multithreading
                with open(self.output_file, 'a', encoding='utf-8') as outfile:
                    self._write_file_header(outfile, filepath)
                    if self.add_syntax_highlight:
                        ext = os.path.splitext(filepath)[1]
                        outfile.write(f"```{ext[1:] if ext else ''}\n")  # Manual language specification
                    if self.include_line_numbers:
                        for i, line in enumerate(content.splitlines(), 1):
                            outfile.write(f"{i:4d} | {line}\n")
                    else:
                        outfile.write(content) # Write processed content (with or without comments removed)
                    if self.add_syntax_highlight:
                        outfile.write("```\n")
                    outfile.write("\n")
            return 1, os.path.getsize(filepath)  # Return file count and size
        except Exception as e:
            logging.error(f"Error reading or processing {filepath}: {e}") # More descriptive error
            with self.lock:
                with open(self.output_file, 'a', encoding='utf-8') as outfile:
                    outfile.write(f"Error reading {filepath}: {e}\n\n")
            return 0, 0  # File not read, size is 0.


    def combine_files(self):
        """
        Combines code files from the source directory into a single output dataset/archive file
        according to user preferences, optimized for RAG applications.

        Important notes:
        - The program requires read permissions for all files in the source directory and write permissions
          to create the output file and zip archive. Ensure appropriate permissions are granted.
        """
        try:
            with self.skipped_lists_lock: # Clear skipped lists at the start, protect with lock just in case.
                self.skipped_folders = []
                self.skipped_files = []
            self._write_summary()

            file_paths = []
            # Walk through the source directory
            for dirpath, dirnames, filenames in os.walk(self.source_dir, followlinks=False):
                original_dirnames = list(dirnames) # Create a copy to iterate over
                for d in original_dirnames:
                    if d in self.exclude_folders:
                        full_dir_path = os.path.join(dirpath, d)
                        with self.skipped_lists_lock: # Protect access to skipped_folders
                            self.skipped_folders.append(full_dir_path) # Add skipped folder to list

                        # Add files in skipped folders to skipped_files list
                        for root_dir, _, files in os.walk(full_dir_path): # Walk through the skipped folder
                            for file in files:
                                skipped_file_path = os.path.join(root_dir, file)
                                with self.skipped_lists_lock: # Protect access to skipped_files
                                    self.skipped_files.append(skipped_file_path) # Add each file in skipped folder
                        dirnames.remove(d) # Modify dirnames in place to prevent os.walk from going into excluded folders


                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if self.should_process_file(filepath):
                        file_paths.append(filepath)

            total_files = len(file_paths)
            if total_files == 0:
                messagebox.showinfo("Information", "No code files found to process with the current settings.") # Updated message
                logging.info("No files found to process.")
                self.toggle_gui_elements(disabled=False) # Re-enable GUI even if no files
                return

            files_processed = 0
            total_size = 0

            with ThreadPoolExecutor(max_workers=self.num_worker_threads) as executor:
                file_count = len(file_paths) # Get file count outside loop for progress calculation
                for index, result in enumerate(executor.map(self._process_file, file_paths), 1): # Enumerate for progress
                    files_processed += result[0]
                    total_size += result[1]
                    # Update progress label - use file index for more accurate progress
                    progress_percent = (index / file_count) * 100
                    self.progress_label.config(text=f"Processed {index}/{file_count} files ({progress_percent:.0f}%) ...") # Updated progress text
                    self.root.update_idletasks()

            self._write_combination_summary(files_processed, total_size)

            if self.create_zip_archive:
                self._create_zip_archive()

            logging.info(f"Combined {files_processed} code files into {self.output_file}") # Updated log message
            logging.info(f"Total dataset size: {total_size / 1024 / 1024:.2f} MB") # Updated log message

            print(f"\nCombined {files_processed} code files into {self.output_file}") # Updated print message
            print(f"Total dataset size: {total_size / 1024 / 1024:.2f} MB") # Updated print message

            messagebox.showinfo("Success", f"Combined {files_processed} code files into {self.output_file}\nTotal dataset size: {total_size / 1024 / 1024:.2f} MB") # Updated message

            # Open the output file after processing
            self.open_output_file()

        except Exception as e:
            logging.error(f"An error occurred during code file combination: {e}") # More specific error log
            print(f"An error occurred during code file combination: {e}") # More specific error print
            messagebox.showerror("Error", f"An error occurred during code file combination: {e}") # More specific error message
        finally:
            # Re-enable the GUI elements after processing
            self.toggle_gui_elements(disabled=False)

    def _create_zip_archive(self):
        """Creates a zip archive of the output dataset file."""
        zip_filename = self.output_file.replace('.txt', '.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(self.output_file, arcname=os.path.basename(self.output_file))  # Use arcname for correct filename in zip
            logging.info(f"Created zip archive: {zip_filename}")
            print(f"Created zip archive: {zip_filename}")
            messagebox.showinfo("Zip Archive Created", f"Created zip archive: {zip_filename}")

        except Exception as e:
            logging.error(f"Error creating zip archive: {e}")
            print(f"Error creating zip archive: {e}")
            messagebox.showerror("Error", f"Error creating zip archive: {e}")

    def open_output_file(self):
        """Opens the output dataset file using the default system application."""
        try:
            # Attempt to open the output file with the default application
            webbrowser.open(self.output_file)
        except Exception as e:
            logging.error(f"Error opening output file: {e}")
            messagebox.showerror("Error", f"Could not open the output file: {e}")

def main():
    code_fusion = AMZCodeFusion()
    code_fusion.get_user_preferences()

if __name__ == "__main__":
    main()
