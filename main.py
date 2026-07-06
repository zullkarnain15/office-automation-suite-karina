"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : main.py
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
Application Entry Point
=========================================================
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from config.app_config import (
    APP_ICON,
    APP_VERSION,
    IMAGE_PATH,
    WINDOW_TITLE,
)
from config.ui_config import (
    BACKGROUND_COLOR,
    BORDER_COLOR,
    BUTTON_FONT,
    CARD_COLOR,
    DEFAULT_FONT,
    HEADER_FONT,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WINDOW_HEIGHT,
    WINDOW_RESIZABLE,
    WINDOW_WIDTH,
)
from shared.logger import get_logger

logger = get_logger(__name__)


# =========================================================
# EVENT
# =========================================================

def coming_soon(module_name: str) -> None:
    """Temporary event for unavailable modules."""

    logger.info("%s module clicked.", module_name)

    messagebox.showinfo(
        "Coming Soon",
        f"{module_name} module is under development.",
    )


# =========================================================
# MAIN
# =========================================================

def main() -> None:

    logger.info("Starting OAS-K")

    root = tk.Tk()

    root.title(WINDOW_TITLE)

    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

    root.configure(bg=BACKGROUND_COLOR)

    root.resizable(
        WINDOW_RESIZABLE,
        WINDOW_RESIZABLE,
    )

    try:
        root.iconbitmap(APP_ICON)
    except Exception:
        logger.warning("Application icon could not be loaded.")

    # =====================================================
    # Header
    # =====================================================

    header = tk.Frame(
        root,
        bg=PRIMARY_COLOR,
    )

    header.pack(fill="x")

    try:
        logo_image = tk.PhotoImage(
            file=IMAGE_PATH / "logo.png"
        )

        logo_image = logo_image.subsample(7, 7)

        logo = tk.Label(
            header,
            image=logo_image,
            bg=PRIMARY_COLOR,
        )

        logo.image = logo_image
        logo.pack(pady=(10, 4))

    except Exception as ex:
        logger.warning("Logo image failed : %s", ex)

    tk.Label(
        header,
        text="Office Automation Suite - Karina",
        font=("Segoe UI", 16, "bold"),
        bg=PRIMARY_COLOR,
        fg="#FFFFFF",
    ).pack(pady=(0, 2))

    tk.Label(
        header,
        text="OTO Finance",
        font=("Segoe UI", 11, "bold"),
        bg=PRIMARY_COLOR,
        fg="#DDEBFA",
    ).pack()

    tk.Label(
        header,
        text=f"Version {APP_VERSION}",
        font=("Segoe UI", 9),
        bg=PRIMARY_COLOR,
        fg="#BFD4EA",
    ).pack(pady=(0, 10))

    # =====================================================
    # Content
    # =====================================================

    content = tk.Frame(
        root,
        bg=BACKGROUND_COLOR,
    )

    content.pack(expand=True, pady=(24, 18))

    tk.Label(
        content,
        text="Automation Modules",
        font=HEADER_FONT,
        bg=BACKGROUND_COLOR,
        fg=TEXT_PRIMARY,
    ).grid(
        row=0,
        column=0,
        columnspan=2,
        pady=(0, 18),
    )

    modules = [
        ("Attendance", "attendance.png"),
        ("Outlook", "outlook.png"),
        ("HRIS", "hris.png"),
        ("Utilities", "utilities.png"),
    ]

    images = []

    row = 1
    col = 0

    for module_name, image_file in modules:

        card = tk.LabelFrame(
            content,
            text=module_name,
            padx=20,
            pady=15,
            bg=CARD_COLOR,
            fg=PRIMARY_COLOR,
            font=HEADER_FONT,
            bd=1,
            relief="solid",
            highlightbackground=BORDER_COLOR,
            highlightcolor=SECONDARY_COLOR,
        )

        card.grid(
            row=row,
            column=col,
            padx=20,
            pady=20,
        )

        try:

            image = tk.PhotoImage(
                file=IMAGE_PATH / image_file
            )

            image = image.subsample(6, 6)

            images.append(image)

            label = tk.Label(
                card,
                image=image,
                bg=CARD_COLOR,
            )

            label.pack()

        except Exception:

            tk.Label(
                card,
                text="[ Image ]",
                bg=CARD_COLOR,
                fg=TEXT_SECONDARY,
                font=DEFAULT_FONT,
            ).pack()

        tk.Button(
            card,
            text=module_name,
            width=18,
            font=BUTTON_FONT,
            bg=SECONDARY_COLOR,
            fg="#FFFFFF",
            activebackground=PRIMARY_COLOR,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            highlightthickness=0,
            command=lambda m=module_name: coming_soon(m),
        ).pack(pady=10)

        col += 1

        if col > 1:
            col = 0
            row += 1

    # =====================================================
    # Footer
    # =====================================================

    footer = tk.Frame(
        root,
        bg=PRIMARY_COLOR,
        height=28,
    )

    footer.pack(
        side="bottom",
        fill="x",
    )

    tk.Label(
        footer,
        text="Status : Ready",
        bg=PRIMARY_COLOR,
        fg="#FFFFFF",
        font=DEFAULT_FONT,
        anchor="w",
    ).pack(
        side="left",
        padx=10,
    )

    tk.Label(
        footer,
        text="© 2026 OTO Finance",
        bg=PRIMARY_COLOR,
        fg="#DDEBFA",
        font=DEFAULT_FONT,
        anchor="e",
    ).pack(
        side="right",
        padx=10,
    )

    footer.winfo_children()[-1].config(
        text="(c) 2026 OTO Finance"
    )

    logger.info("Launcher loaded successfully.")

    root.mainloop()


if __name__ == "__main__":
    main()
