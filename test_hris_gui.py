"""
Temporary launcher for Sprint 6.23 HRIS GUI.

Run from project root:
py test_hris_gui.py
"""

from __future__ import annotations

import tkinter as tk

from hris.gui import HRISUploadGUI


def main() -> None:
    root = tk.Tk()
    HRISUploadGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
