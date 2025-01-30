# 🤖 AMZ-CodeFusion 🚀
The smart tool designed for **human-in-the-loop code documentation**, **source code dataset creation**, and efficient **source code archiving**, all tailored for **RAG (Retrieval-Augmented Generation) applications**.  Are you looking to build robust RAG-based code assistants or archive your projects for future reference? AMZ-CodeFusion simplifies the process of consolidating scattered code files into a structured, documented dataset, ready to fuel your AI models and knowledge bases.

## ✨ Key Features for Code Documentation, Datasets & RAG

- **Human-in-the-Loop Documentation Focus:** Prepare your codebase for enhanced documentation efforts by consolidating code into manageable, structured outputs, ready for human review and annotation.
- **Source Code Dataset Generation:**  Create clean, combined source code datasets perfect for training and evaluating RAG models designed for code understanding and generation.
- **Source Code Archiving:**  Efficiently archive entire projects or specific code sections into single files for better organization, searchability, and long-term storage.
- **RAG-Optimized Output:** Generate output files specifically structured for optimal performance with Retrieval-Augmented Generation systems, enhancing code retrieval and context.
- **Intuitive GUI:**  User-friendly graphical interface powered by `tkinter` for effortless configuration and operation.
- **Flexible Input:** Select any source directory to process your code files.
- **Customizable Output:** Choose the output file name and location for your code dataset or archive.
- **File Extension Filtering:**  Include only specific code file types (e.g., `.py`, `.java`, `.js`, `.c`, `.cpp`, `.html`, `.css`).
- **Folder Exclusion:**  Exclude development-related folders (like `.git`, `node_modules`, `venv`) to focus on source code.
- **Regex Pattern Exclusion:**  Define regular expression patterns to exclude specific files or paths within your codebase.
- **File Size Limit:**  Manage dataset size by setting a maximum file size to skip processing very large code files.
- **Content Enhancements (Optional):**
    - Include line numbers for referencing specific lines of code in documentation.
    - Add timestamps for tracking code versions or archival dates.
    - Display file sizes for dataset analysis.
    - Opt-in for syntax highlighting in the output for improved readability in documentation and datasets.
- **Code-Focused Exclusion Options:**
    - Exclude images and non-code assets.
    - Exclude executable files and build artifacts.
    - Exclude temporary and backup files commonly found in development environments.
    - Exclude hidden files and folders.
    - **NEW!** Exclude comments (`/* ... */`) to create cleaner code datasets, focusing on the core logic.
- **Detailed Logging:**  Comprehensive logging to track the code dataset generation and archiving process, including skipped files and folders.
- **Summary Reports:**  Includes a summary header and a combination summary in the output file, detailing code files processed, dataset size, and skipped items.
- **Zip Archive Creation:**  Optionally create a `.zip` archive of the output code dataset or archive for easy sharing and distribution.
- **Multi-threaded Processing:**  Leverages multi-threading to accelerate the processing of large codebases.
- **Open Output File:** Automatically opens the generated code dataset or archive file after processing.
- **Skipped Items Detail:** Option to include detailed lists of skipped folders and files in the output summary for complete transparency in dataset creation.

## 🚀 Getting Started with AMZ-CodeFusion

### Prerequisites

- **Python 3.7 or higher:** Ensure Python is installed on your system. Get it from [python.org](https://www.python.org). No additional libraries are needed.

### Usage

1. **Download the Script:** [Download (windows exe file)](https://github.com/adeism/AMZ-CodeFusion/releases/download/AMZ-CodeFusion-v1/CodeFusion.zip) or clone the `CodeFusion.py` script to your local machine.
2. **Run the Script:** Open your terminal or command prompt, navigate to the script's directory, and execute:
   ```bash
   python CodeFusion.py
   ```
3. **Configure for Code Fusion:** The AMZ-CodeFusion GUI will launch.

![image](https://github.com/user-attachments/assets/2e1649b5-cd22-4dd8-95d3-8e0421fb36de)


   - **Source Code Directory:**  Click "Browse..." to select the root directory of your codebase.
   - **Output Dataset File Name:**  Enter a descriptive name for your code dataset or archive output file (e.g., `project_code_dataset.txt`, `code_archive_v1.txt`).
   - **Code File Extensions (comma-separated):** Specify code file extensions to include, such as `py, java, js, c, cpp, html, css`.
   - **Exclude Folders (comma-separated):**  List folders to exclude, like `.git, node_modules, venv, build, dist`. `.git` is excluded by default.
   - **Regex Patterns to Exclude (comma-separated):** Define regex patterns for fine-grained exclusion (e.g., `tests/, .*_test\.py$`).
   - **[Checkboxes]:**  Customize your code dataset or archive by toggling options like:
     - **Line Numbers:**  Useful for code documentation and referencing.
     - **Timestamp:**  For versioning and archival tracking.
     - **File Size:**  For dataset analysis and management.
     - **Syntax Highlight:** Enhance readability of the code dataset.
     - **Zip Archive:**  Create a compressed archive of your code dataset.
     - **Exclude Images, Executables, Temp/Backup, Hidden Files, Comments:**  Tailor your dataset content precisely.
     - **Include Skipped Folders/Files Detail:**  Maintain a detailed record of dataset generation.
   - **Max File Size (MB):**  Set a limit for individual code file sizes in your dataset.
   - **Worker Threads:**  Adjust for optimal processing speed based on your system.
4. **Start Code Fusion:** Click "Start Fusion" to begin generating your code dataset or archive. Track progress via the indicator.
5. **Access Your Code Dataset/Archive:** Upon completion, a success message will appear, and your output file will open, providing you with your consolidated codebase, ready for documentation, RAG integration, or archiving.

## ⚙️ Configuration Options for Code Datasets & Archives

| Setting                         | Description                                                                                                                                | Default Value                                  |
|---------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------|
| **Source Directory**            | The root directory of your codebase to generate a dataset or archive from.                                                                 | Current directory (`.`)                        |
| **Output File Name**            | The desired name for your generated code dataset or archive file.                                                                         | `codefusion_output.txt`                        |
| **File Extensions**             | Comma-separated list of code file extensions to include (e.g., `py, java, js`). Leave empty for all file types.                              | Empty (all extensions included)                 |
| **Exclude Folders**             | Comma-separated list of folders to exclude from your codebase dataset (e.g., `.git, node_modules`).                                        | `.git`                                         |
| **Regex Patterns to Exclude**   | Regex patterns to exclude specific code files or paths from the dataset.                                                                   | Empty (no regex exclusion)                      |
| **Line Numbers**                | Add line numbers to the code in the output, useful for documentation and referencing.                                                   | Unchecked (False)                              |
| **Timestamp**                   | Include a timestamp in the output, useful for versioning and archival.                                                                   | Unchecked (False)                              |
| **File Size**                   | Include file sizes in the output summary, helpful for dataset analysis.                                                                    | Unchecked (False)                              |
| **Syntax Highlight**            | Wrap code in Markdown code blocks for syntax highlighting in documentation or dataset viewers.                                           | Unchecked (False)                              |
| **Zip Archive**                 | Create a `.zip` archive of the generated code dataset or archive.                                                                       | Unchecked (False)                              |
| **Exclude Images**              | Exclude image files from the code dataset, focusing on source code.                                                                       | Checked (True)                                 |
| **Exclude Executables**         | Exclude executable files from the code dataset.                                                                                          | Checked (True)                                 |
| **Exclude Temp/Backup**         | Exclude temporary and backup files often present in code repositories.                                                                    | Checked (True)                                 |
| **Exclude Hidden Files**        | Exclude hidden files and folders from the code dataset.                                                                                   | Checked (True)                                 |
| **Exclude Comments (/* ... */)** | Remove `/* ... */` comments from the code in the dataset for cleaner RAG data.                                                               | Unchecked (False)                              |
| **Include Skipped Folders Detail**| List all skipped folders in detail in the output summary for dataset generation transparency.                                                | Checked (True)                                 |
| **Include Skipped Files Detail**  | List all skipped files in detail in the output summary for dataset generation transparency.                                                  | Checked (True)                                 |
| **Max File Size (MB)**          | Maximum file size in MB for individual code files to be included in the dataset.                                                           | Empty (no limit)                               |
| **Worker Threads**              | Number of threads to use for processing the codebase, adjust for performance.                                                               | `4`                                            |

## 📄 Output File Structure for Code Datasets/Archives

The output is a plain text file (`.txt` by default) representing your combined codebase dataset or archive. Structure:

1. **Summary Header:**
   - Dataset/Archive generation date and time.
   - Source codebase directory.
   - Included code file extensions (if specified).
   - Excluded folders (if specified).
   - Excluded patterns (if specified).

2. **Code File Blocks:**
   - Each code file's content is preceded by a header:
     - `## File: [relative/path/to/code/file]`
     - Optionally includes timestamp and file size based on settings.
   - The code content itself, optionally with line numbers.
   - If syntax highlighting is enabled, code is wrapped in Markdown code blocks.

3. **Dataset/Archive Summary:**
   - Total number of code files processed.
   - Total size of the generated code dataset/archive.
   - Optionally, detailed or count summary of skipped folders and code files.

### Example Output File (`codefusion_output.txt`)

```text
# AMZ-CodeFusion Output - 2024-01-01 12:00
Source Code Directory: /path/to/your/codebase
Included Code Extensions: py, js
Excluded Folders: .git, node_modules

---

## File: example_project/utils.py

def helper_function(data):
    """
    This is an example helper function.
    """
    return data * 2

## File: example_project/main.py

import utils

def main():
    data = 5
    result = utils.helper_function(data)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()

---
Code Files Processed: 2
Total Dataset Size: 0.01 MB

Skipped Folders Count: 2
Skipped Files Count: 5
```

---

**Generate powerful code datasets and archives with AMZ-CodeFusion! 🚀  Elevate your RAG and code documentation workflows! ✨**
