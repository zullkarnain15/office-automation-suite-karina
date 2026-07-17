"""Run the Utilities Hub directly from the project root."""

import tkinter as tk

from utilities.gui import UtilitiesGUI


def main() -> None:
    root = tk.Tk()
    UtilitiesGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
