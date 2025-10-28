"""NovaEdit -- A simple text editor in Python. Supports syntax 
highlighting for C-like languages, Python, JavaScript, and more.
Runs in terminal mode by default or GUI mode with --gui flag.
No external dependencies beyond standard Python libraries (Tkinter for GUI).
"""

import sys
import termios
import os
import time
import atexit
import signal
import argparse
from tkinter import *
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
import re
import platform # <-- IMPORTED FOR OS DETECTION

NOVA_VERSION = "0.0.5"  # Refactored syntax highlighting and pure CLI

# Syntax highlight categories
HL_NORMAL = 0
HL_NONPRINT = 1
HL_COMMENT = 2
HL_MLCOMMENT = 3
HL_KEYWORD1 = 4
HL_KEYWORD2 = 5
HL_STRING = 6
HL_NUMBER = 7
HL_MATCH = 8

HL_HIGHLIGHT_STRINGS = 1 << 0
HL_HIGHLIGHT_NUMBERS = 1 << 1

class EditorSyntax:
    def __init__(self, file_extensions, keywords, singleline_comment_start, multiline_comment_start, multiline_comment_end, flags):
        self.file_extensions = file_extensions
        self.keywords = keywords
        self.singleline_comment_start = singleline_comment_start
        self.multiline_comment_start = multiline_comment_start
        self.multiline_comment_end = multiline_comment_end
        self.flags = flags

# Define syntaxes
C_EXTENSIONS = [".c", ".h", ".cpp", ".hpp", ".cc"]
C_KEYWORDS = [
    "auto", "break", "case", "continue", "default", "do", "else", "enum",
    "extern", "for", "goto", "if", "register", "return", "sizeof", "static",
    "struct", "switch", "typedef", "union", "volatile", "while", "NULL",
    "alignas", "alignof", "and", "and_eq", "asm", "bitand", "bitor", "class",
    "compl", "constexpr", "const_cast", "deltype", "delete", "dynamic_cast",
    "explicit", "export", "false", "friend", "inline", "mutable", "namespace",
    "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq",
    "private", "protected", "public", "reinterpret_cast", "static_assert",
    "static_cast", "template", "this", "thread_local", "throw", "true", "try",
    "typeid", "typename", "virtual", "xor", "xor_eq",
    "int|", "long|", "double|", "float|", "char|", "unsigned|", "signed|",
    "void|", "short|", "auto|", "const|", "bool|"
]

CLIKE_EXTENSIONS = [".clike"]
CLIKE_KEYWORDS = [
    "if", "else", "while", "for", "return", "print",
    "int|", "float|", "void|", "char|", "string|"
]

JS_EXTENSIONS = [".js"]
JS_KEYWORDS = [
    "function", "var", "let", "const", "if", "else", "switch", "case", "default",
    "for", "while", "do", "break", "continue", "return", "try", "catch", "throw",
    "new", "this", "typeof", "instanceof", "true", "false", "null", "undefined",
    "Number|", "String|", "Boolean|", "Object|", "Array|", "Function|"
]

PY_EXTENSIONS = [".py"]
PY_KEYWORDS = [
    "and", "as", "assert", "break", "class", "continue", "def", "del", "elif",
    "else", "except", "finally", "for", "from", "global", "if", "import",
    "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return",
    "try", "while", "with", "yield",
    "True|", "False|", "None|"
]

SYNTAX_DB = [
    EditorSyntax(C_EXTENSIONS, C_KEYWORDS, "//", "/*", "*/", HL_HIGHLIGHT_STRINGS | HL_HIGHLIGHT_NUMBERS),
    EditorSyntax(CLIKE_EXTENSIONS, CLIKE_KEYWORDS, "//", "/*", "*/", HL_HIGHLIGHT_STRINGS | HL_HIGHLIGHT_NUMBERS),
    EditorSyntax(JS_EXTENSIONS, JS_KEYWORDS, "//", "/*", "*/", HL_HIGHLIGHT_STRINGS | HL_HIGHLIGHT_NUMBERS),
    EditorSyntax(PY_EXTENSIONS, PY_KEYWORDS, "#", "", "", HL_HIGHLIGHT_STRINGS | HL_HIGHLIGHT_NUMBERS)
]

class EditorState:
    def __init__(self):
        self.cursor_x = 0
        self.cursor_y = 0
        self.row_offset = 0
        self.col_offset = 0
        self.screen_rows = 0
        self.screen_cols = 0
        self.total_rows = 0
        self.rows = []
        self.modified = 0
        self.file_name = None
        self.status_message = ""
        self.status_message_time = 0
        self.current_syntax = None
        
        self.undo_stack = []  # List of (rows_copy, cursor_x, cursor_y)
        self.redo_stack = []
        
        self.mark_x = None    # For selection start
        self.mark_y = None
        self.clipboard = ""   # Internal clipboard
        
        self.update_screen_size()

    def update_screen_size(self):
        try:
            terminal_size = os.get_terminal_size(sys.stdout.fileno())
            self.screen_cols = terminal_size.columns
            self.screen_rows = terminal_size.lines - 2
        except OSError:
            # Handle cases where stdout is not a TTY
            self.screen_cols = 80
            self.screen_rows = 24


E = EditorState()

class EditorRow:
    def __init__(self, index, content):
        self.index = index
        self.content = content
        self.content_size = len(content)
        self.rendered_content = None
        self.rendered_size = 0
        self.highlight = None
        self.open_comment = 0
        self.update_rendered()

    def has_open_comment(self):
        if self.highlight and self.rendered_size and self.highlight[-1] == HL_MLCOMMENT:
            if self.rendered_size < 2 or (self.rendered_content[-2] != '*' or self.rendered_content[-1] != '/'):
                return True
        return False

    def update_syntax(self):
        self.highlight = [HL_NORMAL] * self.rendered_size
        if E.current_syntax is None:
            return

        prev_open_comment = self.index > 0 and E.rows[self.index - 1].has_open_comment()

        self.highlight, new_open_comment = get_syntax_highlighting(
            self.rendered_content, E.current_syntax, prev_open_comment
        )

        # Check if the comment state change needs to propagate
        if self.open_comment != new_open_comment and self.index + 1 < E.total_rows:
            E.rows[self.index + 1].update_syntax()
        self.open_comment = new_open_comment

    def update_rendered(self):
        self.rendered_content = self.content.replace('\t', '        ')
        self.rendered_size = len(self.rendered_content)
        self.update_syntax()

    def insert_char(self, position, ch):
        if position > self.content_size:
            position = self.content_size
        self.content = self.content[:position] + ch + self.content[position:]
        self.content_size += 1
        self.update_rendered()

    def append_string(self, string):
        self.content += string
        self.content_size += len(string)
        self.update_rendered()

    def delete_char(self, position):
        if position >= self.content_size:
            return
        self.content = self.content[:position] + self.content[position + 1:]
        self.content_size -= 1
        self.update_rendered()

original_termios = None

def disable_raw_mode():
    if original_termios is not None and os.name == 'posix':
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, original_termios)

def enable_raw_mode():
    global original_termios
    
    # --- ADDED: Platform check for CLI mode ---
    if os.name != 'posix':
        print("NovaEdit CLI mode is only supported on Unix-like systems (Linux, macOS).")
        print("For Windows, please use the --gui flag.")
        sys.exit(1)
        
    try:
        fd = sys.stdin.fileno()
        original_termios = termios.tcgetattr(fd)
    except (termios.error, OSError, AttributeError):
        # Fail gracefully if not in a proper terminal
        print("Not a TTY. Terminal mode disabled.")
        return
        
    raw = termios.tcgetattr(fd)
    raw[0] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)
    raw[1] &= ~(termios.OPOST)
    raw[2] |= termios.CS8
    raw[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
    raw[6][termios.VMIN] = 0
    raw[6][termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSAFLUSH, raw)
    atexit.register(disable_raw_mode)

KEY_ACTION = {
    'NULL': 0,
    'CTRL_A': 1,
    'CTRL_B': 2,
    'CTRL_C': 3,
    'CTRL_D': 4,
    'CTRL_F': 6,
    'CTRL_H': 8,
    'TAB': 9,
    'CTRL_L': 12,
    'ENTER': ord('\r'),
    'CTRL_O': 15,
    'CTRL_Q': 17,
    'CTRL_R': 18,
    'CTRL_S': 19,
    'CTRL_U': 21,
    'CTRL_V': 22,
    'CTRL_X': 24,
    'CTRL_Z': 26,
    'ESC': 27,
    'BACKSPACE': 127,
    'ARROW_LEFT': 1000,
    'ARROW_RIGHT': 1001,
    'ARROW_UP': 1002,
    'ARROW_DOWN': 1003,
    'DEL_KEY': 1004,
    'HOME_KEY': 1005,
    'END_KEY': 1006,
    'PAGE_UP': 1007,
    'PAGE_DOWN': 1008
}

def read_key():
    try:
        ch = os.read(sys.stdin.fileno(), 1)
    except (OSError, AttributeError):
        # Handle cases where stdin is not available (e.g., in some IDEs)
        return KEY_ACTION['ESC']
        
    if len(ch) == 0:
        return KEY_ACTION['ESC']
    ch = ord(ch)
    if ch == KEY_ACTION['ESC']:
        seq = os.read(sys.stdin.fileno(), 5)
        if len(seq) < 2:
            return KEY_ACTION['ESC']
        seq1, seq2 = seq[0], seq[1]
        if seq1 == ord('['):
            if ord('0') <= seq2 <= ord('9'):
                if len(seq) < 3:
                    return KEY_ACTION['ESC']
                seq3 = seq[2]
                if seq3 == ord('~'):
                    if seq2 == ord('3'):
                        return KEY_ACTION['DEL_KEY']
                    if seq2 == ord('5'):
                        return KEY_ACTION['PAGE_UP']
                    if seq2 == ord('6'):
                        return KEY_ACTION['PAGE_DOWN']
            else:
                if seq2 == ord('A'):
                    return KEY_ACTION['ARROW_UP']
                if seq2 == ord('B'):
                    return KEY_ACTION['ARROW_DOWN']
                if seq2 == ord('C'):
                    return KEY_ACTION['ARROW_RIGHT']
                if seq2 == ord('D'):
                    return KEY_ACTION['ARROW_LEFT']
                if seq2 == ord('H'):
                    return KEY_ACTION['HOME_KEY']
                if seq2 == ord('F'):
                    return KEY_ACTION['END_KEY']
        elif seq1 == ord('O'):
            if seq2 == ord('H'):
                return KEY_ACTION['HOME_KEY']
            if seq2 == ord('F'):
                return KEY_ACTION['END_KEY']
    return ch

def is_separator(ch):
    return ch == '\0' or ch.isspace() or ch in ",.()+-/*=~%[];"

def syntax_to_color(hl):
    color_map = {
        HL_COMMENT: 36, HL_MLCOMMENT: 36,
        HL_KEYWORD1: 33,
        HL_KEYWORD2: 32,
        HL_STRING: 35,
        HL_NUMBER: 31,
        HL_MATCH: 34
    }
    return color_map.get(hl, 37)

def syntax_to_tk_color(hl):
    color_map = {
        HL_COMMENT: "gray", HL_MLCOMMENT: "gray",
        HL_KEYWORD1: "blue",
        HL_KEYWORD2: "green",
        HL_STRING: "red",
        HL_NUMBER: "purple",
        HL_MATCH: "orange"
    }
    return color_map.get(hl, "black")

def select_syntax_highlight(file_name):
    if file_name is None:
        E.current_syntax = None
        return None
    for syntax in SYNTAX_DB:
        for ext in syntax.file_extensions:
            if file_name.endswith(ext):
                E.current_syntax = syntax
                return syntax
    E.current_syntax = None
    return None

# --- NEW: Shared Syntax Highlighting Function ---
def get_syntax_highlighting(line, syntax, prev_open_comment):
    """
    Shared syntax highlighting logic for both CLI and GUI modes.
    Takes a line of text, syntax rules, and previous comment state.
    Returns a list of highlight constants and the new open_comment state (bool).
    """
    highlight = [HL_NORMAL] * len(line)
    if syntax is None:
        return highlight, False # Return False for open_comment

    keywords = syntax.keywords
    scs = syntax.singleline_comment_start
    mcs = syntax.multiline_comment_start
    mce = syntax.multiline_comment_end

    i = 0
    prev_sep = True
    in_string = ''
    in_comment = prev_open_comment

    while i < len(line):
        ch = line[i]
        
        # Handle Single-line comments
        if scs and not in_string and not in_comment and line.startswith(scs, i):
            for j in range(i, len(line)):
                highlight[j] = HL_COMMENT
            return highlight, False # Single line comment can't carry over

        # Handle Multi-line comments
        if in_comment:
            highlight[i] = HL_MLCOMMENT
            if mce and line.startswith(mce, i) and (len(mce) > 0):
                for j in range(len(mce)):
                    if i + j < len(line):
                         highlight[i + j] = HL_MLCOMMENT
                i += len(mce)
                in_comment = False
                prev_sep = True
                continue
            prev_sep = False
            i += 1
            continue
        elif mcs and line.startswith(mcs, i) and (len(mcs) > 0):
            for j in range(len(mcs)):
                 if i + j < len(line):
                    highlight[i + j] = HL_MLCOMMENT
            i += len(mcs)
            in_comment = True
            prev_sep = False
            continue

        # Handle Strings
        if in_string:
            highlight[i] = HL_STRING
            if ch == '\\':
                if i + 1 < len(line):
                    highlight[i + 1] = HL_STRING
                    i += 2
                    prev_sep = False
                    continue
            if ch == in_string:
                in_string = ''
            i += 1
            continue
        else:
            if ch in ('"', "'"):
                in_string = ch
                highlight[i] = HL_STRING
                i += 1
                prev_sep = False
                continue

        # Handle Numbers
        if (ch.isdigit() and (prev_sep or (i > 0 and highlight[i - 1] == HL_NUMBER))) or \
           (ch == '.' and i > 0 and highlight[i - 1] == HL_NUMBER):
            highlight[i] = HL_NUMBER
            i += 1
            prev_sep = False
            continue

        # Handle Keywords
        if prev_sep:
            found_kw = False
            for kw in keywords:
                kw2 = kw.endswith('|')
                klen = len(kw) - 1 if kw2 else len(kw)
                if line[i:i + klen] == kw[:klen] and (i + klen >= len(line) or is_separator(line[i + klen])):
                    hl_type = HL_KEYWORD2 if kw2 else HL_KEYWORD1
                    for j in range(klen):
                        highlight[i + j] = hl_type
                    i += klen
                    found_kw = True
                    break
            if found_kw:
                prev_sep = False
                continue

        prev_sep = is_separator(ch)
        i += 1

    return highlight, in_comment
# --- END: Shared Function ---


def get_content_col(row, rendered_col):
    content_col = 0
    rendered = 0
    while content_col < row.content_size and rendered < rendered_col:
        if row.content[content_col] == '\t':
            tab_len = 8 - (rendered % 8)
            if rendered + tab_len > rendered_col:
                break
            rendered += tab_len
        else:
            rendered += 1
        content_col += 1
    return content_col

def get_rendered_col(row, content_col):
    rendered = 0
    for i in range(min(content_col, len(row.content))):
        if row.content[i] == '\t':
            rendered += 8 - (rendered % 8)
        else:
            rendered += 1
    return rendered

def insert_editor_row(position, content):
    if position > E.total_rows:
        position = E.total_rows
    new_row = EditorRow(position, content)
    E.rows.insert(position, new_row)
    for i in range(position + 1, E.total_rows + 1):
        E.rows[i].index += 1
    E.total_rows += 1
    E.modified = 1

def delete_editor_row(position):
    if position >= E.total_rows:
        return
    del E.rows[position]
    for i in range(position, E.total_rows - 1):
        E.rows[i].index -= 1
    E.total_rows -= 1
    E.modified = 1

def rows_to_string():
    return '\n'.join(row.content for row in E.rows) + '\n'

def save_undo_state():
    rows_copy = [row.content for row in E.rows]
    E.undo_stack.append((rows_copy, E.cursor_x, E.cursor_y, E.col_offset, E.row_offset))
    E.redo_stack = []  # Clear redo on new action
    if len(E.undo_stack) > 50:
        E.undo_stack.pop(0)

def undo():
    if not E.undo_stack:
        set_status_message("Nothing to undo")
        return
    current_state = ([row.content for row in E.rows], E.cursor_x, E.cursor_y, E.col_offset, E.row_offset)
    E.redo_stack.append(current_state)
    rows_copy, cursor_x, cursor_y, col_offset, row_offset = E.undo_stack.pop()
    E.rows = []
    E.total_rows = 0
    for content in rows_copy:
        insert_editor_row(E.total_rows, content)
    E.cursor_x = cursor_x
    E.cursor_y = cursor_y
    E.col_offset = col_offset
    E.row_offset = row_offset
    E.modified = 1
    set_status_message("Undo performed")

def redo():
    if not E.redo_stack:
        set_status_message("Nothing to redo")
        return
    current_state = ([row.content for row in E.rows], E.cursor_x, E.cursor_y, E.col_offset, E.row_offset)
    E.undo_stack.append(current_state)
    rows_copy, cursor_x, cursor_y, col_offset, row_offset = E.redo_stack.pop()
    E.rows = []
    E.total_rows = 0
    for content in rows_copy:
        insert_editor_row(E.total_rows, content)
    E.cursor_x = cursor_x
    E.cursor_y = cursor_y
    E.col_offset = col_offset
    E.row_offset = row_offset
    E.modified = 1
    set_status_message("Redo performed")

def insert_char(ch):
    save_undo_state()
    ch = chr(ch) if isinstance(ch, int) else ch
    file_row = E.row_offset + E.cursor_y
    if file_row > E.total_rows:
         file_row = E.total_rows
    while E.total_rows <= file_row:
        insert_editor_row(E.total_rows, '')
    row = E.rows[file_row]
    file_col = get_content_col(row, E.col_offset + E.cursor_x)

    row.insert_char(file_col, ch)
    E.cursor_x += 1
    if E.cursor_x == E.screen_cols:
        E.cursor_x -= 1
        E.col_offset += 1
    E.modified = 1
    E.mark_x = None
    E.mark_y = None

def insert_newline():
    save_undo_state()
    file_row = E.row_offset + E.cursor_y
    if E.total_rows <= file_row:
        insert_editor_row(file_row, '')
    else:
        row = E.rows[file_row]
        file_col = get_content_col(row, E.col_offset + E.cursor_x)
        if file_col > row.content_size:
            file_col = row.content_size
        if file_col == 0:
            insert_editor_row(file_row, '')
        else:
            insert_editor_row(file_row + 1, row.content[file_col:])
            row.content = row.content[:file_col]
            row.update_rendered()
            
    E.cursor_x = 0
    E.col_offset = 0
    if E.cursor_y == E.screen_rows - 1:
        E.row_offset += 1
    else:
        E.cursor_y += 1
    E.mark_x = None
    E.mark_y = None

def delete_char():
    save_undo_state()
    file_row = E.row_offset + E.cursor_y
    if file_row >= E.total_rows:
        return
    row = E.rows[file_row]
    rendered_pos = E.col_offset + E.cursor_x
    if rendered_pos == 0:
        if file_row == 0:
            return
        prev_row = E.rows[file_row - 1]
        prev_row_len_before = prev_row.content_size
        prev_row.append_string(row.content)
        delete_editor_row(file_row)
        if E.cursor_y == 0:
            if E.row_offset > 0: E.row_offset -= 1
        else:
            E.cursor_y -= 1
        
        # Calculate new cursor position
        E.cursor_x = get_rendered_col(prev_row, prev_row_len_before)
        if E.cursor_x >= E.screen_cols:
            E.col_offset = E.cursor_x - E.screen_cols + 1
            E.cursor_x = E.screen_cols - 1
        else:
             E.col_offset = 0 # Reset col_offset
             if E.cursor_x < 0: E.cursor_x = 0
             
    else:
        position = get_content_col(row, rendered_pos - 1)
        row.delete_char(position)
        if E.cursor_x > 0:
            E.cursor_x -= 1
        elif E.col_offset > 0:
            E.col_offset -= 1
            
    E.modified = 1
    E.mark_x = None
    E.mark_y = None

# This is a helper function just for open_file_terminal
def _prompt_user_cli(prompt_text, default=""):
    """Internal prompt for CLI mode, as prompt_user was removed."""
    input_str = default
    while True:
        set_status_message(prompt_text + input_str + " (ESC to cancel)")
        refresh_screen()
        key = read_key()
        if key == KEY_ACTION['ENTER']:
            set_status_message("")
            return input_str
        elif key == KEY_ACTION['ESC']:
            set_status_message("")
            return None
        elif key == KEY_ACTION['BACKSPACE'] or key == KEY_ACTION['CTRL_H'] or key == KEY_ACTION['DEL_KEY']:
            if input_str:
                input_str = input_str[:-1]
        elif key not in (KEY_ACTION['CTRL_L'], KEY_ACTION['ENTER'], KEY_ACTION['ESC']) and 32 <= key <= 126:
            input_str += chr(key)

def open_file_terminal(file_name=None):
    
    # --- UPDATED: Use CLI prompt instead of Tkinter ---
    if file_name is None:
        file_name = _prompt_user_cli("Open file: ")
        if not file_name:
            set_status_message("Open canceled")
            return
            
    if E.modified:
        discard = _prompt_user_cli("Unsaved changes. Discard? (y/n) ")
        if discard is None or discard.lower() != "y":
            set_status_message("Open canceled")
            return
            
    E.file_name = file_name # Set file_name first
    E.current_syntax = select_syntax_highlight(file_name) # <-- FIX: Set syntax *before* loading rows
    
    E.rows = []
    E.total_rows = 0
    E.modified = 0
    E.cursor_x = E.cursor_y = E.row_offset = E.col_offset = 0

    try:
        with open(file_name, 'r') as f:
            for line in f:
                line = line.rstrip('\r\n')
                insert_editor_row(E.total_rows, line)
    except FileNotFoundError:
        set_status_message(f"File {file_name} not found. Created new file.")
    except Exception as e:
        set_status_message(f"Error opening file: {str(e)}")
        return
        
    E.modified = 0 # Reset modified flag after loading
    set_status_message(f"Opened {file_name}")

def save_file_terminal(save_as=False):
    
    # --- UPDATED: Use CLI prompt instead of Tkinter ---
    if save_as or not E.file_name:
        prompt_default = E.file_name or "untitled.txt"
        new_name = _prompt_user_cli("Save as: ", default=prompt_default)
        if not new_name:
            set_status_message("Save canceled")
            return
        E.file_name = new_name
        E.current_syntax = select_syntax_highlight(E.file_name) # Update syntax
    
    if not E.file_name: # Still no file name (e.g., canceled Save As on new file)
        set_status_message("Save canceled")
        return

    content = rows_to_string().rstrip('\n')
    try:
        with open(E.file_name, 'w') as f:
            f.write(content)
        E.modified = 0
        set_status_message(f"{len(content)} bytes saved to {E.file_name}")
        # Re-highlight after save (in case file type changed)
        for row in E.rows:
            row.update_syntax()
    except Exception as e:
        set_status_message(f"Error saving file: {str(e)}")

def set_status_message(message):
    E.status_message = message
    E.status_message_time = time.time()

class AppendBuffer:
    def __init__(self):
        self.buffer = []

    def append(self, string):
        self.buffer.append(string)

    def get(self):
        return ''.join(self.buffer)

def refresh_screen():
    ab = AppendBuffer()
    ab.append("\x1b[?25l")  # Hide cursor
    ab.append("\x1b[H")  # Home

    for y in range(E.screen_rows):
        file_row = E.row_offset + y
        if file_row >= E.total_rows:
            if E.total_rows == 0 and y == E.screen_rows // 3:
                welcome = f"NovaEdit -- version {NOVA_VERSION}\x1b[0K\r\n"
                padding = (E.screen_cols - len(welcome)) // 2
                if padding > 0:
                    ab.append('~')
                    ab.append(' ' * (padding - 1))
                ab.append(welcome)
            else:
                ab.append("~\x1b[0K\r\n")
            continue

        row = E.rows[file_row]
        length = row.rendered_size - E.col_offset
        if length < 0: length = 0
        if length > E.screen_cols:
            length = E.screen_cols
            
        content = row.rendered_content[E.col_offset:E.col_offset + length]
        hl = row.highlight[E.col_offset:E.col_offset + length]
        current_color = -1
        
        for i in range(length):
            if hl[i] == HL_NONPRINT:
                ab.append("\x1b[7m")
                sym = '@' + chr(ord(content[i])) if ord(content[i]) <= 26 else '?'
                ab.append(sym)
                ab.append("\x1b[0m")
            elif hl[i] == HL_NORMAL:
                if current_color != -1:
                    ab.append("\x1b[39m")
                    current_color = -1
                ab.append(content[i])
            else:
                color = syntax_to_color(hl[i])
                if color != current_color:
                    ab.append(f"\x1b[{color}m")
                    current_color = color
                ab.append(content[i])
                
        ab.append("\x1b[39m")
        ab.append("\x1b[0K")
        ab.append("\r\n")

    # Status bar
    ab.append("\x1b[0K")
    ab.append("\x1b[7m")
    
    file_name_str = E.file_name or "[No Name]"
    status = f"{file_name_str[:20]} - {E.total_rows} lines {'(modified)' if E.modified else ''}"
    rstatus = f"{E.row_offset + E.cursor_y + 1}/{E.total_rows}"
    status_length = len(status)
    
    if status_length > E.screen_cols:
        status_length = E.screen_cols
    ab.append(status[:status_length])
    
    while status_length < E.screen_cols:
        if E.screen_cols - status_length == len(rstatus):
            ab.append(rstatus)
            status_length += len(rstatus)
            break
        ab.append(" ")
        status_length += 1
        
    ab.append("\x1b[0m\r\n")

    # Status message
    ab.append("\x1b[0K")
    msg_len = len(E.status_message)
    if msg_len and time.time() - E.status_message_time < 5:
        ab.append(E.status_message[:min(msg_len, E.screen_cols)])

    # Cursor position
    cx = 1
    file_row = E.row_offset + E.cursor_y
    if file_row < E.total_rows:
        row = E.rows[file_row]
        # Use get_rendered_col for accurate cursor positioning
        cx = get_rendered_col(row, get_content_col(row, E.col_offset + E.cursor_x)) - E.col_offset + 1
        if cx < 1: cx = 1
        
    ab.append(f"\x1b[{E.cursor_y + 1};{cx}H")
    ab.append("\x1b[?25h")  # Show cursor

    sys.stdout.write(ab.get())
    sys.stdout.flush()

def move_cursor(key):
    file_row = E.row_offset + E.cursor_y
    row = E.rows[file_row] if file_row < E.total_rows else None
    
    if key == KEY_ACTION['ARROW_LEFT']:
        if E.cursor_x == 0:
            if E.col_offset:
                E.col_offset -= 1
            elif file_row > 0:
                E.cursor_y -= 1
                row = E.rows[file_row - 1]
                E.cursor_x = row.rendered_size
                if E.cursor_x > E.screen_cols - 1:
                    E.col_offset = E.cursor_x - E.screen_cols + 1
                    E.cursor_x = E.screen_cols - 1
        else:
            E.cursor_x -= 1
    elif key == KEY_ACTION['ARROW_RIGHT']:
        if row:
            file_col = E.col_offset + E.cursor_x
            if file_col < row.rendered_size:
                if E.cursor_x == E.screen_cols - 1:
                    E.col_offset += 1
                else:
                    E.cursor_x += 1
            elif file_col == row.rendered_size and file_row < E.total_rows - 1:
                E.cursor_x = 0
                E.col_offset = 0
                E.cursor_y += 1
    elif key == KEY_ACTION['ARROW_UP']:
        if E.cursor_y == 0:
            if E.row_offset:
                E.row_offset -= 1
        else:
            E.cursor_y -= 1
    elif key == KEY_ACTION['ARROW_DOWN']:
        if file_row < E.total_rows - 1:
            if E.cursor_y == E.screen_rows - 1:
                E.row_offset += 1
            else:
                E.cursor_y += 1

    # Snap cursor to end of line if it's past it
    file_row = E.row_offset + E.cursor_y
    row = E.rows[file_row] if file_row < E.total_rows else None
    row_len = row.rendered_size if row else 0
    file_col = E.col_offset + E.cursor_x
    if file_col > row_len:
        E.cursor_x = row_len - E.col_offset
        if E.cursor_x < 0:
            E.col_offset = row_len
            E.cursor_x = 0
            
def set_mark():
    E.mark_x = E.col_offset + E.cursor_x
    E.mark_y = E.row_offset + E.cursor_y
    set_status_message("Mark set")

def copy_selection():
    if E.mark_y is None or E.mark_x is None:
        set_status_message("No selection")
        return
    start_y, end_y = sorted([E.mark_y, E.row_offset + E.cursor_y])
    start_x, end_x = (E.mark_x, E.col_offset + E.cursor_x) if start_y == E.mark_y else (E.col_offset + E.cursor_x, E.mark_x)
    clipboard_lines = []
    for y in range(start_y, end_y + 1):
        if y >= E.total_rows: continue
        row = E.rows[y]
        line_start = start_x if y == start_y else 0
        line_end = end_x if y == end_y else row.rendered_size
        content_start = get_content_col(row, line_start)
        content_end = get_content_col(row, line_end)
        clipboard_lines.append(row.content[content_start:content_end])
    E.clipboard = '\n'.join(clipboard_lines)
    set_status_message("Copied to clipboard")

def cut_selection():
    copy_selection()
    if E.clipboard:
        save_undo_state()
        start_y, end_y = sorted([E.mark_y, E.row_offset + E.cursor_y])
        start_x_render, end_x_render = (E.mark_x, E.col_offset + E.cursor_x) if start_y == E.mark_y else (E.col_offset + E.cursor_x, E.mark_x)
        
        # Recalculate cursor position to the start of selection
        new_cursor_y_file = start_y
        new_cursor_x_render = start_x_render

        # Delete logic (from end to start)
        first_row = E.rows[start_y]
        last_row = E.rows[end_y]
        
        start_x_content = get_content_col(first_row, start_x_render)
        end_x_content = get_content_col(last_row, end_x_render)
        
        # Merge start and end row parts
        first_row.content = first_row.content[:start_x_content] + last_row.content[end_x_content:]
        first_row.update_rendered()
        
        # Delete intermediate rows
        for y in range(end_y, start_y, -1):
            if y < E.total_rows:
                delete_editor_row(y)
                
        # Set new cursor position
        if new_cursor_y_file < E.row_offset:
            E.row_offset = new_cursor_y_file
        if new_cursor_y_file >= E.row_offset + E.screen_rows:
            E.row_offset = new_cursor_y_file - E.screen_rows + 1
        E.cursor_y = new_cursor_y_file - E.row_offset

        if new_cursor_x_render < E.col_offset:
            E.col_offset = new_cursor_x_render
        if new_cursor_x_render >= E.col_offset + E.screen_cols:
            E.col_offset = new_cursor_x_render - E.screen_cols + 1
        E.cursor_x = new_cursor_x_render - E.col_offset
        
        E.mark_x = None
        E.mark_y = None
        E.modified = 1
        set_status_message("Cut to clipboard")

def paste_clipboard():
    if not E.clipboard:
        set_status_message("Clipboard empty")
        return
    save_undo_state()
    lines = E.clipboard.split('\n')
    file_row = E.row_offset + E.cursor_y
    if file_row >= E.total_rows:
        insert_editor_row(E.total_rows, "")
    
    row = E.rows[file_row]
    file_col = get_content_col(row, E.col_offset + E.cursor_x)

    # Insert first line
    remaining_content = row.content[file_col:]
    row.content = row.content[:file_col] + lines[0]
    
    # Calculate cursor pos for after paste
    new_cursor_y_file = file_row + len(lines) - 1
    new_cursor_x_content = len(lines[-1])
    if len(lines) == 1:
        new_cursor_x_content += file_col
    
    # Insert remaining lines
    for i, line in enumerate(lines[1:], 1):
        file_row += 1
        insert_editor_row(file_row, line)
    
    # Add the remaining content to the last pasted line
    E.rows[file_row].content += remaining_content
    E.rows[file_row].update_rendered()
    
    # Update all rows syntax in between
    for i in range(E.row_offset + E.cursor_y, file_row + 1):
        if i < E.total_rows:
            E.rows[i].update_rendered()

    # Set new cursor position
    new_row = E.rows[new_cursor_y_file]
    new_cursor_x_render = get_rendered_col(new_row, new_cursor_x_content)
    
    if new_cursor_y_file < E.row_offset:
        E.row_offset = new_cursor_y_file
    if new_cursor_y_file >= E.row_offset + E.screen_rows:
        E.row_offset = new_cursor_y_file - E.screen_rows + 1
    E.cursor_y = new_cursor_y_file - E.row_offset

    if new_cursor_x_render < E.col_offset:
        E.col_offset = new_cursor_x_render
    if new_cursor_x_render >= E.col_offset + E.screen_cols:
        E.col_offset = new_cursor_x_render - E.screen_cols + 1
    E.cursor_x = new_cursor_x_render - E.col_offset

    E.modified = 1
    set_status_message("Pasted from clipboard")

def terminal_process_keypress():
    quit_times = 3
    while True:
        refresh_screen()
        key = read_key()

        if key == KEY_ACTION['ENTER']:
            insert_newline()
        elif key == KEY_ACTION['CTRL_Q']:
            if E.modified and quit_times > 0:
                set_status_message(f"Warning: Unsaved changes. Hold Ctrl-Q to to quit.")
                quit_times -= 1
                continue
            sys.stdout.write("\x1b[2J\x1b[H\x1b[?25h") # Clear screen, home, show cursor
            sys.exit(0)
        elif key == KEY_ACTION['CTRL_S']:
            save_file_terminal()
        elif key == KEY_ACTION['CTRL_A']:
            save_file_terminal(save_as=True)
        elif key == KEY_ACTION['CTRL_O']:
            open_file_terminal()
        elif key == KEY_ACTION['CTRL_Z']:
            undo()
        elif key == KEY_ACTION['CTRL_R']:
            redo()
        elif key == KEY_ACTION['CTRL_B']:
            set_mark()
        elif key == KEY_ACTION['CTRL_C']:
            copy_selection()
        elif key == KEY_ACTION['CTRL_X']:
            cut_selection()
        elif key == KEY_ACTION['CTRL_V']:
            paste_clipboard()
        elif key == KEY_ACTION['BACKSPACE'] or key == KEY_ACTION['CTRL_H'] or key == KEY_ACTION['DEL_KEY']:
            delete_char()
        elif key in (KEY_ACTION['ARROW_UP'], KEY_ACTION['ARROW_DOWN'], KEY_ACTION['ARROW_LEFT'], KEY_ACTION['ARROW_RIGHT']):
            move_cursor(key)
        elif key == KEY_ACTION['PAGE_UP'] or key == KEY_ACTION['PAGE_DOWN']:
            times = E.screen_rows
            direction = KEY_ACTION['ARROW_UP'] if key == KEY_ACTION['PAGE_UP'] else KEY_ACTION['ARROW_DOWN']
            while times:
                move_cursor(direction)
                times -= 1
        elif key not in (KEY_ACTION['ESC'], KEY_ACTION['CTRL_L']) and key < 1000 and key >= 32:
            insert_char(key)
        quit_times = 3
        

def handle_resize(signum, frame):
    E.update_screen_size()
    if E.cursor_y > E.screen_rows - 1:
        E.cursor_y = E.screen_rows - 1
    if E.cursor_x > E.screen_cols - 1:
        E.cursor_x = E.screen_cols - 1
    refresh_screen()

# GUI Mode
class GUIEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("NovaEdit GUI")
        self.menu = Menu(root)
        root.config(menu=self.menu)

        # --- OS-Aware Accelerator STRINGS ---
        if platform.system() == 'Darwin': # macOS
            mod_key = 'Cmd'
            redo_accel = 'Cmd+Shift+Z'
            # Bind Mac-specific Redo
            self.root.bind('<Command-Shift-z>', self.safe_redo) 
        else: # Windows/Linux
            mod_key = 'Ctrl'
            redo_accel = 'Ctrl+Y'
            # Bind standard Redo
            self.root.bind('<Control-y>', self.safe_redo)
        # --- END OS-Awareness ---

        file_menu = Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Tab", command=self.new_tab, accelerator=f"{mod_key}+N")
        file_menu.add_command(label="Open", command=self.open_file_gui, accelerator=f"{mod_key}+O")
        file_menu.add_command(label="Save", command=self.save_file_gui, accelerator=f"{mod_key}+S")
        file_menu.add_command(label="Save As", command=self.save_as_gui, accelerator=f"{mod_key}+Shift+S")
        file_menu.add_command(label="Close Tab", command=self.close_tab, accelerator=f"{mod_key}+W")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_exit)

        edit_menu = Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self.safe_undo, accelerator=f"{mod_key}+Z")
        edit_menu.add_command(label="Redo", command=self.safe_redo, accelerator=redo_accel)
        edit_menu.add_separator()
        edit_menu.add_command(label="Find/Replace", command=self.find_replace_dialog, accelerator=f"{mod_key}+F")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        self.tabs = {}  # tab_id: {'text': Text, 'file_name': str, 'modified': bool, 'syntax': EditorSyntax}
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        # Open initial file or new tab
        initial_file = args.filename if args.filename else None
        self.add_tab(os.path.basename(initial_file) if initial_file else "untitled.txt", initial_file)

    def safe_undo(self, event=None):
        text = self.get_current_text()
        if text:
            try:
                text.edit_undo()
            except TclError:
                pass # Stack is empty

    def safe_redo(self, event=None):
        text = self.get_current_text()
        if text:
            try:
                text.edit_redo()
            except TclError:
                pass # Stack is empty

    def new_tab(self, event=None):
        self.add_tab("untitled.txt")

    def add_tab(self, tab_name, file_name=None):
        frame = Frame(self.notebook)
        text = Text(frame, wrap="none", undo=True, font=("Courier", 12))
        
        yscroll = Scrollbar(frame, orient=VERTICAL, command=text.yview)
        xscroll = Scrollbar(frame, orient=HORIZONTAL, command=text.xview)
        text.config(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        
        yscroll.pack(side=RIGHT, fill=Y)
        xscroll.pack(side=BOTTOM, fill=X)
        text.pack(fill="both", expand=True)
        
        self.notebook.add(frame, text=tab_name)
        syntax = select_syntax_highlight(file_name or tab_name)
        self.tabs[id(frame)] = {'text': text, 'file_name': file_name, 'modified': False, 'syntax': syntax}
        
        text.bind("<KeyRelease>", self.on_key_release)
        text.bind("<Button-1>", self.on_key_release) # For cursor move
        
        # --- Bind menu shortcuts directly to the text widget ---
        if platform.system() == 'Darwin':
             text.bind('<Command-n>', self.new_tab)
             text.bind('<Command-o>', self.open_file_gui)
             text.bind('<Command-s>', self.save_file_gui)
             text.bind('<Command-Shift-s>', self.save_as_gui)
             text.bind('<Command-w>', self.close_tab)
             text.bind('<Command-f>', self.find_replace_dialog)
        else:
             text.bind('<Control-n>', self.new_tab)
             text.bind('<Control-o>', self.open_file_gui)
             text.bind('<Control-s>', self.save_file_gui)
             text.bind('<Control-Shift-s>', self.save_as_gui)
             text.bind('<Control-w>', self.close_tab)
             text.bind('<Control-f>', self.find_replace_dialog)

        if file_name:
            self.load_file_to_tab(id(frame), file_name)
            
        self.highlight_syntax(id(frame))
        self.notebook.select(frame)

    def on_tab_change(self, event):
        if not self.notebook.tabs():
            return
        self.highlight_syntax(self.get_current_tab_id())

    def get_current_tab_id(self):
        try:
            current_tab = self.notebook.select()
            if not current_tab:
                return None
            return id(self.notebook.nametowidget(current_tab))
        except (TclError, KeyError):
            return None

    def get_current_text(self):
        tab_id = self.get_current_tab_id()
        if tab_id:
            return self.tabs[tab_id]['text']
        return None

    def get_current_syntax(self):
        tab_id = self.get_current_tab_id()
        if tab_id:
            return self.tabs[tab_id]['syntax']
        return None

    def load_file_to_tab(self, tab_id, file_name):
        text = self.tabs[tab_id]['text']
        text.delete(1.0, END)
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                text.insert(END, f.read())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {e}")
            self.close_tab_by_id(tab_id) # Close tab if file read fails
            return
            
        self.tabs[tab_id]['file_name'] = file_name
        self.tabs[tab_id]['modified'] = False
        self.tabs[tab_id]['syntax'] = select_syntax_highlight(file_name)
        self.update_tab_title(tab_id)
        self.highlight_syntax(tab_id)
        text.edit_reset() # Clear undo stack

    def open_file_gui(self, event=None):
        file_name = filedialog.askopenfilename()
        if file_name:
            # Check if file is already open
            for tab_id, data in self.tabs.items():
                if data['file_name'] == file_name:
                    frame = self.notebook.nametowidget([f for f in self.notebook.tabs() if id(self.notebook.nametowidget(f)) == tab_id][0])
                    self.notebook.select(frame)
                    return
            self.add_tab(os.path.basename(file_name), file_name)

    def save_file_gui(self, event=None):
        tab_id = self.get_current_tab_id()
        if not tab_id: return
        file_name = self.tabs[tab_id]['file_name']
        if file_name:
            text = self.tabs[tab_id]['text']
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(text.get(1.0, END).rstrip('\n'))
                self.tabs[tab_id]['modified'] = False
                self.update_tab_title(tab_id)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")
        else:
            self.save_as_gui()

    def save_as_gui(self, event=None):
        tab_id = self.get_current_tab_id()
        if not tab_id: return
        file_name = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=self.tabs[tab_id]['file_name'] or "untitled.txt")
        if file_name:
            text = self.tabs[tab_id]['text']
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(text.get(1.0, END).rstrip('\n'))
                self.tabs[tab_id]['file_name'] = file_name
                self.tabs[tab_id]['modified'] = False
                self.tabs[tab_id]['syntax'] = select_syntax_highlight(file_name)
                self.update_tab_title(tab_id)
                self.highlight_syntax(tab_id) # Re-highlight for new extension
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")

    def close_tab(self, event=None):
        tab_id = self.get_current_tab_id()
        if tab_id:
            self.close_tab_by_id(tab_id)

    def close_tab_by_id(self, tab_id):
        if self.tabs[tab_id]['modified']:
            self.notebook.select(self.notebook.nametowidget([f for f in self.notebook.tabs() if id(self.notebook.nametowidget(f)) == tab_id][0]))
            if not messagebox.askyesno("Unsaved Changes", f"Close '{self.notebook.tab('current')['text']}' without saving?"):
                return False # Indicate close was canceled
        
        current_tab_widget = self.notebook.nametowidget([f for f in self.notebook.tabs() if id(self.notebook.nametowidget(f)) == tab_id][0])
        self.notebook.forget(current_tab_widget)
        del self.tabs[tab_id]
        if not self.notebook.tabs():
            self.root.quit()
        return True # Indicate close was successful

    def on_exit(self):
        for tab_id in list(self.tabs.keys()):
            if not self.close_tab_by_id(tab_id):
                # User canceled the close, so abort exiting
                return
        # If all tabs closed successfully, self.tabs will be empty
        if not self.tabs:
            self.root.quit()

    def update_tab_title(self, tab_id):
        file_name = self.tabs[tab_id]['file_name']
        modified = self.tabs[tab_id]['modified']
        title = os.path.basename(file_name) if file_name else "untitled.txt"
        if modified:
            title += "*"
        
        try:
            frame = self.notebook.nametowidget([f for f in self.notebook.tabs() if id(self.notebook.nametowidget(f)) == tab_id][0])
            self.notebook.tab(frame, text=title)
        except (IndexError, TclError):
            pass # Tab was already closed

    def on_key_release(self, event):
        tab_id = self.get_current_tab_id()
        if not tab_id: return
        
        # Check if key is a modification key
        if event.keysym not in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Up', 'Down', 'Left', 'Right', 'Command_L', 'Command_R'):
             if not self.tabs[tab_id]['modified']:
                self.tabs[tab_id]['modified'] = True
                self.update_tab_title(tab_id)
        
        # We can be smarter and only highlight the current line, but for simplicity:
        self.highlight_syntax(tab_id)

    def highlight_syntax(self, tab_id):
        if not tab_id: return
        text = self.tabs[tab_id]['text']
        syntax = self.tabs[tab_id]['syntax']

        # Clear all old tags
        for tag in text.tag_names():
            if tag != "sel": # Don't remove selection tag
                text.tag_remove(tag, "1.0", "end")

        if syntax is None:
            return

        content = text.get("1.0", END).rstrip('\n')
        lines = content.split('\n')
        open_comment = False # Changed from 0 to False for clarity
        
        for line_num, line in enumerate(lines, 1):
            
            # --- UPDATED: Call shared function ---
            highlight, open_comment = get_syntax_highlighting(line, syntax, open_comment)
            
            for col, hl in enumerate(highlight):
                if hl != HL_NORMAL:
                    color = syntax_to_tk_color(hl)
                    tag_name = f"hl_{hl}"
                    start = f"{line_num}.{col}"
                    end = f"{line_num}.{col+1}"
                    text.tag_add(tag_name, start, end)
                    text.tag_config(tag_name, foreground=color)

    # --- REMOVED: get_highlight_for_line (now uses shared function) ---

    def find_replace_dialog(self, event=None):
        top = Toplevel(self.root)
        top.title("Find/Replace")

        Label(top, text="Find:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        find_entry = Entry(top)
        find_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        Label(top, text="Replace:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        replace_entry = Entry(top)
        replace_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        current_text_widget = self.get_current_text()
        if not current_text_widget:
            top.destroy()
            return
            
        current_text_widget.tag_remove("find_match", "1.0", END)
        last_find_pos = "1.0"

        def find_next():
            nonlocal last_find_pos
            text = current_text_widget
            search = find_entry.get()
            if not search:
                return
                
            text.tag_remove("find_match", "1.0", END)
            start = text.index(INSERT)
            if start == last_find_pos:
                start = f"{start}+1c" # Move past the last match
                
            pos = text.search(search, start, stopindex=END)
            if not pos:
                # Loop back to top
                pos = text.search(search, "1.0", stopindex=END)
                if not pos:
                    messagebox.showinfo("Find", "No more matches found")
                    last_find_pos = "1.0"
                    return
            
            end = f"{pos}+{len(search)}c"
            last_find_pos = end
            
            text.tag_remove(SEL, "1.0", END)
            text.tag_add(SEL, pos, end)
            text.mark_set(INSERT, end)
            text.see(INSERT)
            text.focus()

        def replace():
            text = current_text_widget
            search = find_entry.get()
            repl = replace_entry.get()
            if not search:
                return
                
            if text.tag_ranges(SEL):
                start, end = text.tag_ranges(SEL)
                if text.get(start, end) == search:
                    text.delete(start, end)
                    text.insert(start, repl)
                    text.tag_remove(SEL, "1.row.0", END)
            find_next()

        def replace_all():
            text = current_text_widget
            search = find_entry.get()
            repl = replace_entry.get()
            if not search:
                return
                
            content = text.get("1.0", END)
            if search not in content:
                messagebox.showinfo("Replace All", "No matches found")
                return

            new_content = content.replace(search, repl)
            text.delete("1.0", END)
            text.insert("1.0", new_content)
            self.on_key_release(None) # Trigger modified state and highlighting

        Button(top, text="Find Next", command=find_next).grid(row=2, column=0, padx=5, pady=10)
        Button(top, text="Replace", command=replace).grid(row=2, column=1, padx=5, pady=10)
        Button(top, text="Replace All", command=replace_all).grid(row=2, column=2, padx=5, pady=10)
        
        top.grid_columnconfigure(1, weight=1)
        top.grid_columnconfigure(2, weight=1)
        
        def on_close():
            current_text_widget.tag_remove(SEL, "1.0", END)
            top.destroy()
        top.protocol("WM_DELETE_WINDOW", on_close)

def run_gui():
    root = Tk()
    app = GUIEditor(root)
    root.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NovaEdit: A simple text editor supporting syntax highlighting. Use CLI mode for terminal editing or --gui for graphical interface."
    )
    parser.add_argument("filename", nargs="?", help="File to open (optional in GUI mode).")
    parser.add_argument("--gui", action="store_true", help="Run in GUI mode with tabbed editing, find/replace, and menu options.")
    args = parser.parse_args()

    if args.gui:
        run_gui()
    else:
        # --- UPDATED: Moved enable_raw_mode up to check OS first ---
        enable_raw_mode()
        signal.signal(signal.SIGWINCH, handle_resize)
        E.update_screen_size() # Initial size update
        open_file_terminal(args.filename) # Pass filename, can be None
        # --- UPDATED help string (removed Ctrl+F) ---
        set_status_message("Help: Ctrl-S = Save | Ctrl-A = Save As | Ctrl-O = Open | Ctrl-Z = Undo | Ctrl-R = Redo | Ctrl-B = Mark | Ctrl-C = Copy | Ctrl-X = Cut | Ctrl-V = Paste | Ctrl-Q = Quit")
        terminal_process_keypress()