import os
import datetime
from typing import List, Optional

class FileCombiner:
    def __init__(self):
        self.extensions = ['.php']
        self.output_file = "combined_files.txt"
        self.source_dir = "."
        self.include_line_numbers = False
        self.include_timestamp = False
        self.add_syntax_highlight = False
        self.exclude_folders: List[str] = []
        self.include_file_size = False
        self.max_file_size_mb = None
        
    def get_user_preferences(self):
        """Interactive menu to get user preferences"""
        print("\n=== File Combiner Configuration ===")
        
        # Source directory
        print("\n1. Select source directory:")
        user_dir = input(f"Enter directory path (press Enter for current directory): ").strip()
        if user_dir and os.path.isdir(user_dir):
            self.source_dir = user_dir
            
        # File extensions
        print("\n2. Select file extensions to combine:")
        print("Common options: 1) PHP files 2) Python files 3) All files 4) Custom")
        ext_choice = input("Enter your choice (1-4): ").strip()
        if ext_choice == "1":
            self.extensions = ['.php']
        elif ext_choice == "2":
            self.extensions = ['.py']
        elif ext_choice == "3":
            self.extensions = []  # Empty list means all files
        elif ext_choice == "4":
            exts = input("Enter extensions separated by comma (e.g., .php,.py,.js): ").strip()
            self.extensions = [ext.strip() for ext in exts.split(',') if ext.strip()]
            
        # Output file
        print("\n3. Configure output:")
        output_name = input("Enter output filename (press Enter for 'combined_files.txt'): ").strip()
        if output_name:
            self.output_file = output_name if output_name.endswith('.txt') else output_name + '.txt'
            
        # Additional options
        print("\n4. Additional options (enter y/n for each):")
        self.include_line_numbers = input("Include line numbers? ").lower().startswith('y')
        self.include_timestamp = input("Include file timestamps? ").lower().startswith('y')
        self.include_file_size = input("Include file sizes? ").lower().startswith('y')
        self.add_syntax_highlight = input("Add syntax highlighting markers? ").lower().startswith('y')
        
        # Exclusions
        print("\n5. Exclusion options:")
        if input("Do you want to exclude specific folders? (y/n) ").lower().startswith('y'):
            folders = input("Enter folder names to exclude (comma-separated): ").strip()
            self.exclude_folders = [f.strip() for f in folders.split(',') if f.strip()]
            
        # File size limit
        if input("\nDo you want to set a maximum file size limit? (y/n) ").lower().startswith('y'):
            try:
                self.max_file_size_mb = float(input("Enter maximum file size in MB: "))
            except ValueError:
                print("Invalid input. No file size limit will be applied.")

    def should_process_file(self, filepath: str) -> bool:
        """Check if file should be processed based on settings"""
        # Check extensions
        if self.extensions and not any(filepath.endswith(ext) for ext in self.extensions):
            return False
            
        # Check excluded folders
        if any(folder in filepath for folder in self.exclude_folders):
            return False
            
        # Check file size
        if self.max_file_size_mb:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                return False
                
        return True

    def combine_files(self):
        """Combine files according to user preferences"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as outfile:
                # Write configuration summary
                outfile.write("=== File Combination Summary ===\n")
                outfile.write(f"Generated on: {datetime.datetime.now()}\n")
                outfile.write(f"Source directory: {os.path.abspath(self.source_dir)}\n")
                outfile.write(f"File types: {', '.join(self.extensions) if self.extensions else 'All files'}\n")
                outfile.write("=" * 80 + "\n\n")

                files_processed = 0
                total_size = 0

                for dirpath, dirnames, filenames in os.walk(self.source_dir):
                    # Remove excluded folders
                    dirnames[:] = [d for d in dirnames if d not in self.exclude_folders]
                    
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        
                        if not self.should_process_file(filepath):
                            continue

                        # Write file header
                        outfile.write("\n" + "=" * 80 + "\n")
                        outfile.write(f"File: {filename}\n")
                        outfile.write(f"Location: {os.path.relpath(filepath, self.source_dir)}\n")
                        
                        if self.include_timestamp:
                            timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                            outfile.write(f"Last modified: {timestamp}\n")
                            
                        if self.include_file_size:
                            size = os.path.getsize(filepath)
                            outfile.write(f"Size: {size/1024:.2f} KB\n")
                            total_size += size

                        outfile.write("=" * 80 + "\n\n")

                        # Write file content
                        try:
                            with open(filepath, 'r', encoding='utf-8') as infile:
                                if self.add_syntax_highlight:
                                    ext = os.path.splitext(filename)[1]
                                    outfile.write(f"```{ext[1:] if ext else ''}\n")
                                    
                                if self.include_line_numbers:
                                    for i, line in enumerate(infile, 1):
                                        outfile.write(f"{i:4d} | {line}")
                                else:
                                    outfile.write(infile.read())

                                if self.add_syntax_highlight:
                                    outfile.write("\n```\n")
                                    
                                outfile.write("\n")
                                files_processed += 1
                                
                        except Exception as e:
                            outfile.write(f"Error reading file: {str(e)}\n")

                # Write summary at the end
                outfile.write("\n" + "=" * 80 + "\n")
                outfile.write(f"Total files processed: {files_processed}\n")
                outfile.write(f"Total size: {total_size/1024/1024:.2f} MB\n")

            print(f"\nSuccessfully combined {files_processed} files into {self.output_file}")
            print(f"Total size: {total_size/1024/1024:.2f} MB")
            
        except Exception as e:
            print(f"An error occurred: {str(e)}")

def main():
    combiner = FileCombiner()
    combiner.get_user_preferences()
    combiner.combine_files()

if __name__ == "__main__":
    main()
