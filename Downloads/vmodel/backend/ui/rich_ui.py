"""Rich UI package (stub)."""
from __future__ import annotations

RICH_AVAILABLE = False


def clear_screen():
    pass


def show_logo():
    print("VModel - Text Quality Intelligence Engine")


def show_mode_selection():
    print("Choose cleaning mode: 1=Safe, 2=Strict, 3=Clean+Translate, 4=Only Clean, 5=Only Translate")


def prompt_text(message, default=None):
    return input(f"{message}: ")


def print_warning(msg):
    print(f"WARNING: {msg}")


def print_error(msg):
    print(f"ERROR: {msg}")


def prompt_confirm(message, default=False):
    ans = input(f"{message} [y/N]: ").strip().lower()
    return ans in ("y", "yes")


class Console:
    def print(self, obj):
        print(obj)


console = Console()


class Panel:
    def __init__(self, obj, title="", border_style="", box=None):
        self.obj = obj


class rich_box:
    ROUNDED = None


def show_file_info(name, fmt, rows, cols, text_cells):
    return f"{name} | {fmt} | {rows} rows | {cols} cols | {text_cells} text cells"


def show_sample_preview(columns, rows):
    return f"Preview: {len(columns)} cols, {len(rows)} rows"
