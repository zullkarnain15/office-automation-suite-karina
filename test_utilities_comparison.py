"""Run Comparison-Attendance Reconciliation directly from the project root."""

import tkinter as tk

from utilities.attendance_reconciliation.gui import (
    AttendanceReconciliationGUI,
)


def main() -> None:
    root = tk.Tk()
    AttendanceReconciliationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
