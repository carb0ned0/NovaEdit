# NovaEdit

A simple, lightweight, dual-mode text editor written in Python. NovaEdit runs as a fast, minimal terminal editor by default, and also offers a modern, tabbed GUI mode.

## Core Features

NovaEdit combines the simplicity of a terminal editor with the convenience of a graphical interface.

⚠️ Note: I've only tested this only on mac and linux, although I implemented windows support also, but due to lack of testing the code might misbehave.

### GUI Mode (`--gui`)

* **Tabbed Editing:** Open, edit, and manage multiple files in one window.
* **Menu Bar:** Familiar `File` and `Edit` menus for all actions.
* **Find & Replace:** A dedicated dialog to find and replace text within a file.
* **Syntax Highlighting:** Full syntax highlighting for all supported languages.
* **OS-Aware Shortcuts:** Uses `Command+S` on macOS and `Ctrl+S` on Windows/Linux for a native feel.

### CLI (Terminal) Mode

* **`nano`-Inspired:** A true terminal-based UI that runs directly in your console.
* **Syntax Highlighting:** Full syntax highlighting for C, C++, Python, JavaScript, and especially for my own language which i built for self-learning purposes, check it out here [C-Like](https://github.com/carb0ned0/C-Like/).
* **Editing Essentials:**
  * Undo (`Ctrl+Z`) and Redo (`Ctrl+R`)
  * Cut (`Ctrl+X`), Copy (`Ctrl+C`), and Paste (`Ctrl+V`)
  * Mark selection (`Ctrl+B`)
* **File Operations:** Open (`Ctrl+O`), Save (`Ctrl+S`), and Save As (`Ctrl+A`) without leaving the editor.

## Installation

No external libraries are required; NovaEdit uses only the Python standard library.

1. Clone the repository:

    ```bash
    git clone [https://github.com/carb0ned0/NovaEdit.git](https://github.com/carb0ned0/NovaEdit.git)
    cd NovaEdit
    ```

2. (Note for Linux) You may need to install `tkinter` if it wasn't included with your Python installation:

    ```bash
    sudo apt-get install python3-tk
    ```

## Usage

You can run NovaEdit in either CLI mode or GUI mode.

### CLI Mode (Default)

To edit a file in your terminal:

```bash
python NovaEdit.py [filename]
```

If filename doesn't exist, it will be created on save.

### GUI Mode

To launch the graphical, tabbed editor:

```bash
python NovaEdit.py --gui
```

You can also open a specific file directly in the GUI:

```bash
python NovaEdit.py [filename] --gui
```

## Key Bindings and Features

1. **Core Editing Features**

    Test Case | Steps to Perform | Expected Result
    --- | --- | ---
    Type Text | Open the editor and type a few lines of code (e.g., a "hello world" program). | The text should appear correctly on the screen as you type.
    Delete Text | Use the `Backspace` key. | The character to the left of the cursor is deleted.
    Delete Text (Fwd) | Use the `Delete` key (if your keyboard has one). | The character to the right of the cursor is deleted.
    Create Newline | Press the `Enter` key in the middle of a line. | The line should split, and the text after the cursor should move to the next line.
    Modify Flag | 1. Open a file. 2. Type a single character. | The editor should indicate the file is modified (e.g., `(modified)` in the CLI status bar, or a `*` in the GUI tab title).

2. **File Operations**

    Test Case | Steps to Perform | Expected Result
    --- | --- | ---
    Save File | 1. Modify a file. 2. Press `Ctrl+S` (or `Cmd+S` on Mac). | 1. The "modified" status should disappear. 2. If you close and reopen the file, your changes should be there.
    Save As | 1. Modify a file. 2. Use "Save As" (`Ctrl+A` in CLI, Menu in GUI). 3. Save with a new name (e.g., `test2.py`). | 1. A new file is created with your changes. 2. The editor's window/tab should now show the new filename.
    Open File | 1. Use "Open" (`Ctrl+O` in CLI, Menu in GUI). 2. Select an existing file. | The contents of that file should load into the editor.
    Quit Warning | 1. Modify a file but do not save. 2. Try to quit (`Ctrl+Q` in CLI, close window/tab in GUI) | The editor should warn you about unsaved changes and ask you to confirm before quitting.

3. **Syntax Highlighting**

    Test Case | Steps to Perform | Expected Result
    --- | --- | ---
    Python | 1. Create a file named `test.py`. 2. Type: `def hello(): # a comment \n print(""world"")` | `def` and `print` should be one color (keyword), `# a comment` another (comment), and `"world"` a third (string).
    C/C++ | 1. Create a file named `test.c`. 2. Type: `int main() { /* comment */ \n return 0; }` | `int` and `return` should be one color (keyword), and `/* comment */` another (comment).
    Plain Text | 1. Create a file named `test.txt`. 2. Type the same code as above. | No colors should appear. All text should be the default color.

4. **CLI-Specific Tests**

    Test Case | Steps to Perform | Expected Result
    --- | --- | ---
    Cut/Copy/Paste | 1. Press `Ctrl+B` to set a mark. 2. Move the cursor to select text. 3. Press `Ctrl+C` (Copy). 4. Move the cursor. 5. Press `Ctrl+V` (Paste). 6. Repeat with `Ctrl+X` (Cut). | The selected text should be successfully copied and pasted. `Ctrl+X` should also remove the original text.
    Undo/Redo | 1. Type "Hello". 2. Press `Ctrl+Z` (Undo). 3. Press `Ctrl+R` (Redo). | 1. "Hello" should disappear. 2. "Hello" should reappear.
    Page Up/Down | 1. Create a file with 100+ lines. 2. Press `PageDown` and `PageUp`. | The view should scroll up or down by a full screen.

5. **GUI-Specific Tests**

    Test Case | Steps to Perform | Expected Result
    --- | --- | ---
    Find/Replace | 1. Press `Ctrl+F` (or `Cmd+F`). 2. Type a word in "Find". Click "Find Next". 3. Type a new word in "Replace". Click "Replace". 4. Click "Replace All". | 1. The cursor should jump to the word. 2. The single word is replaced. 3. All instances of the word are replaced.
    Tab Management | 1. Press `Ctrl+N` (or `Cmd+N`) to open a new tab.  2. Use the "Open" menu to open a file. | 1. A new "untitled" tab should appear.  2. A third tab should open with the file's contents.
    Undo/Redo (Menu) | "1. Type "Hello".  2. Use `Edit > Undo`.  3. Use `Edit > Redo`." | "1. "Hello" should disappear.  2. "Hello" should reappear.

### CLI Mode Controls

Key | Action
--- | ---
`Ctrl+S` | Save File
`Ctrl+A` | Save As... (Opens file dialog)
`Ctrl+O` | Open File... (Opens file dialog)
`Ctrl+Q` | Quit (Warns on unsaved changes)
`Ctrl+Z` | Undo
`Ctrl+R` | Redo
`Ctrl+B` | Set Selection Mark
`Ctrl+C` | Copy Selection
`Ctrl+X` | Cut Selection
`Ctrl+V` | Paste
`Arrow Keys` | Move Cursor
`PageUp/PageDown` | Move cursor up/down one screen

### GUI Mode Shortcuts

Shortcuts are OS-aware (e.g., `Cmd` on macOS, `Ctrl` on Windows/Linux).

Action | macOS | Windows/Linux
--- | --- | ---
New Tab | `Cmd+N` | `Ctrl+N`
Open File | `Cmd+O` | `Ctrl+O`
Save File | `Cmd+S` | `Ctrl+S`
Save As... | `Cmd+Shift+S` | `Ctrl+Shift+S`
Close Tab | `Cmd+W` | `Ctrl+W`
Find/Replace | `Cmd+F` | `Ctrl+F`
Undo | `Cmd+Z` | `Ctrl+Z`
Redo | `Cmd+Shift+Z` | `Ctrl+Y`
Cut | `Cmd+X` | `Ctrl+X`
Copy | `Cmd+C` | `Ctrl+C`
Paste | `Cmd+V` | `Ctrl+V`

## Tech Stack

* Python 3: Core language.
* `tkinter`: Used for the optional GUI mode.
* `termios`: Used for low-level terminal control in CLI mode.
* `argparse`: For parsing command-line arguments like `--gui`.
* `platform`: To detect the operating system for native GUI shortcuts.

## License

This project is licensed under the MIT License. See the LICENSE file for details
