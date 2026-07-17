"""Run the Attendance GUI directly from the project root."""

import tkinter as tk

from attendance.gui import AttendanceGUI


def main() -> None:
    root = tk.Tk()
    AttendanceGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
