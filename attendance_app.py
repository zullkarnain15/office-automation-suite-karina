from __future__ import annotations

import tkinter as tk

from attendance.gui import AttendanceGUI


def main() -> None:
    root = tk.Tk()
    AttendanceGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()