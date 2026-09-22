"""Terminal output.

Rich lives in this package and nowhere else. Everything below it stays
terminal-free, so the library can be driven from a notebook or another program
with no console attached.
"""

from llmsearchbench.ui.console import console, err_console, fail, warn
from llmsearchbench.ui.format import human_size

__all__ = ["console", "err_console", "fail", "human_size", "warn"]
