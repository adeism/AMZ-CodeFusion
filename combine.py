import os
import datetime
import logging
import re
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import List
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FileCombiner:
    """Combines multiple files into a single output file, with various options."""

    def __init__(self):
        self.source_dir = "."
        self.output_file = "combined_files.txt"
        self.extensions = []  # Empty list means all extensions are included
        self.exclude_folders = ['.git']
        self.exclude_patterns = []
        self.include_line_numbers = False
        self.include_timestamp = False
        self.include_file_size = False
        self.add_syntax_highlight = False  # Requires manual language specification in output
        self.max_file_size_mb = None
        self.create_zip_archive = False
        self.exclude_images = False  # Basic image extension check, not fully reliable
        self.exclude_executable = False
        self.exclude_temp_and_backup_files = False
        self.exclude_hidden_files = False
        self.num_worker_threads = 4
        self.lock = threading.Lock()


    def get_user_preferences(self):
        """Interactively gets user preferences for file combination."""

        print("\n=== File Combiner Configuration ===")

        self.source_dir = self._get_input("Source directory (default: .): ", self.source_dir, os.path.isdir)
        self.output_file = self._get_input("Output file name (default: combined_files.txt): ", self.output_file)
        self.extensions = self._get_list_input("File extensions to include (comma-separated, or Enter for all): ")
        self.exclude_folders = self._get_list_input("Folders to exclude (comma-separated, default: .git): ", self.exclude_folders)
        self.exclude_patterns = self._get_list_input("Regex patterns to exclude (comma-separated): ")

        self.include_line_numbers = self._get_boolean_input("Include line numbers? (y/n): ")
        self.include_timestamp = self._get_boolean_input("Include timestamps? (y/n): ")
        self.include_file_size = self._get_boolean_input("Include file sizes? (y/n): ")
        self.add_syntax_highlight = self._get_boolean_input("Add syntax highlighting (requires manual language spec)? (y/n): ")  # Clarify manual aspect
        self.max_file_size_mb = self._get_float_input("Max file size to include (MB, or Enter for no limit): ")
        self.create_zip_archive = self._get_boolean_input("Create zip archive of output? (y/n): ")
        self.exclude_images = self._get_boolean_input("Exclude common image files (basic check, not fully reliable)? (y/n): ")
        self.exclude_executable = self._get_boolean_input("Exclude executable files? (y/n): ")
        self.exclude_temp_and_backup_files = self._get_boolean_input("Exclude temp/backup files? (y/n): ")
        self.exclude_hidden_files = self._get_boolean_input("Exclude hidden files? (y/n): ")
        self.num_worker_threads = self._get_int_input("Number of worker threads (default: 4): ", 4, lambda x: x > 0)


    def _get_input(self, prompt: str, default: str = None, validator=lambda x: True) -> str:
        while True:
            value = input(prompt).strip()
            if not value:
                return default
            if validator(value):
                return value
            print("Invalid input.")


    def _get_list_input(self, prompt: str, default: list = None) -> list:
        value = input(prompt).strip()
        if not value:
            return default or []
        return [x.strip() for x in value.split(',') if x.strip()]


    def _get_boolean_input(self, prompt: str) -> bool:
        return self._get_input(prompt + " (y/n): ", "n", lambda x: x.lower() in ('y', 'n')) == 'y'


    def _get_float_input(self, prompt: str) -> float or None: # returns float or None for no input
        while True:
            value = input(prompt).strip()
            if not value:
                return None  # Allow no input, return None
            try:
                return float(value)
            except ValueError:
                print("Invalid input. Please enter a number.")


    def _get_int_input(self, prompt: str, default: int, validator=lambda x: True) -> int:
        while True:
            value = input(prompt).strip()
            if not value:
                return default
            try:
                int_value = int(value)
                if validator(int_value):
                    return int_value
                else:
                    print("Invalid input. Value does not meet criteria.")
            except ValueError:
                print("Invalid input. Please enter an integer.")


    def should_process_file(self, filepath: str) -> bool:
        """Determines whether a file should be included in the combination based on user settings."""

        if self.extensions and not any(filepath.endswith(ext) for ext in self.extensions):
            return False
        if any(folder in filepath for folder in self.exclude_folders):
            return False
        if self.exclude_patterns and any(re.match(pattern, filepath) for pattern in self.exclude_patterns):
            return False
        try:
            file_size = os.path.getsize(filepath)
            if self.max_file_size_mb and file_size > self.max_file_size_mb * 1024 * 1024:
                return False
        except OSError:
            logging.warning(f"Could not get size of {filepath}. Skipping.")
            return False
        if self.exclude_images and any(filepath.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']):
            return False  # Basic image file extension check.
        if self.exclude_executable and os.access(filepath, os.X_OK):
            return False
        if self.exclude_temp_and_backup_files and (filepath.startswith(tempfile.gettempdir()) or any(filepath.endswith(ext) for ext in ['.tmp', '.temp', '.bak', '~'])):
            return False
        if self.exclude_hidden_files and os.path.basename(filepath).startswith('.'):
            return False

        return True

    def _process_file(self, filepath: str, outfile):
        """Processes and writes a single file to the output."""
        try:
            with open(filepath, 'r', encoding='utf-8') as infile:
                content = infile.read()
                with self.lock:  # Lock to prevent race conditions with multithreading
                    self._write_file_header(outfile, filepath)
                    if self.add_syntax_highlight:
                        ext = os.path.splitext(filepath)[1]
                        outfile.write(f"```{ext[1:] if ext else ''}\n")  # Manual language specification
                    if self.include_line_numbers:
                        for i, line in enumerate(content.splitlines(), 1):
                            outfile.write(f"{i:4d} | {line}\n")
                    else:
                        outfile.write(content)
                    if self.add_syntax_highlight:
                        outfile.write("```\n")
                    outfile.write("\n")

            return 1, os.path.getsize(filepath)  # Return file count and size
        except Exception as e:
            logging.error(f"Error reading {filepath}: {e}")
            with self.lock:
                outfile.write(f"Error reading {filepath}: {e}\n\n")
            return 0, 0 # File not read, size is 0.

    def _write_summary(self, outfile):
        """Writes the initial summary information to the output file."""
        outfile.write("=== File Combination Summary ===\n")
        outfile.write(f"Generated on: {datetime.datetime.now()}\n")
        outfile.write(f"Source directory: {os.path.abspath(self.source_dir)}\n")

        outfile.write(f"Included extensions: {', '.join(self.extensions) if self.extensions else 'All'}\n")
        outfile.write(f"Excluded folders: {', '.join(self.exclude_folders)}\n")

        outfile.write("=" * 80 + "\n\n")

    def _write_file_header(self, outfile, filepath):
        outfile.write("=" * 80 + "\n")
        outfile.write(f"File: {os.path.relpath(filepath, self.source_dir)}\n")  # Use relative path
        if self.include_timestamp:
             timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
             outfile.write(f"Last Modified: {timestamp}\n")

        if self.include_file_size:
            size = os.path.getsize(filepath)
            outfile.write(f"Size: {size / 1024:.2f} KB\n")
        outfile.write("=" * 80 + "\n\n")


    def _write_combination_summary(self, outfile, files_processed, total_size):
        """Writes the final combination summary to the output file."""

        outfile.write("=" * 80 + "\n")
        outfile.write(f"Total files processed: {files_processed}\n")
        outfile.write(f"Total size: {total_size / 1024 / 1024:.2f} MB\n")


    def combine_files(self):
        """Combines the files according to the user preferences."""


        try:
            with open(self.output_file, 'w', encoding='utf-8') as outfile:
                self._write_summary(outfile)


                file_paths = []
                for dirpath, dirnames, filenames in os.walk(self.source_dir, followlinks=False): # followlinks=False added
                    dirnames[:] = [d for d in dirnames if d not in self.exclude_folders]  # Exclude specified directories
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        if self.should_process_file(filepath):
                            file_paths.append(filepath)

                with ThreadPoolExecutor(max_workers=self.num_worker_threads) as executor:
                    results = executor.map(self._process_file, file_paths, [outfile] * len(file_paths))
                    files_processed, total_size = sum([r[0] for r in results]), sum([r[1] for r in results])

                self._write_combination_summary(outfile, files_processed, total_size)

            if self.create_zip_archive:
                self._create_zip_archive()

            logging.info(f"Combined {files_processed} files into {self.output_file}")
            logging.info(f"Total size: {total_size / 1024 / 1024:.2f} MB")

            print(f"\nCombined {files_processed} files into {self.output_file}")
            print(f"Total size: {total_size / 1024 / 1024:.2f} MB")

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            print(f"An error occurred: {e}")



    def _create_zip_archive(self):
        zip_filename = self.output_file.replace('.txt', '.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(self.output_file, arcname=os.path.basename(self.output_file)) # Use arcname for correct filename in zip
            logging.info(f"Created zip archive: {zip_filename}")
            print(f"Created zip archive: {zip_filename}")

        except Exception as e:
            logging.error(f"Error creating zip archive: {e}")
            print(f"Error creating zip archive: {e}")



def main():
    combiner = FileCombiner()
    combiner.get_user_preferences()
    combiner.combine_files()

if __name__ == "__main__":
    main()