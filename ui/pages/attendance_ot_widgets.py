"""Page-local ttk table, selection and scrolling helpers."""

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from ui.constants import CARD_BACKGROUND, TEXT_PRIMARY, ROYAL_BLUE


LATE_CELL_BLUE = "#3B82F6"
LATE_CELL_ORANGE = "#F59E0B"


def bind_wheel(widget, target):
    def scroll(event):
        delta = getattr(event, "delta", 0)
        num = getattr(event, "num", None)
        if not delta and num not in (4, 5):
            return None
        direction = -1 if delta > 0 or num == 4 else 1
        target.yview_scroll(direction * max(1, abs(int(delta / 120))), "units")
        return "break"

    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        widget.bind(sequence, scroll)


class MultiSelect(ttk.Frame):
    def __init__(self, parent, title):
        super().__init__(parent, style="AttendanceOTSurface.TFrame")
        self.title = title
        self.values = ()
        self.selected = ()
        self.button = ttk.Button(
            self, text=f"{title}: All", command=self.open, style="AttendanceOT.TButton"
        )
        self.button.pack(fill="x", expand=True)

    def set_values(self, values):
        self.values = tuple(values)

    def set_selected(self, values):
        self.selected = tuple(values)
        self.button.configure(
            text=f"{self.title}: {len(self.selected)} selected"
            if self.selected
            else f"{self.title}: All"
        )

    def open(self):
        window = tk.Toplevel(self)
        window.title(self.title + " (multiple selection)")
        window.geometry("420x430")
        window.transient(self.winfo_toplevel())
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        ttk.Label(
            window,
            text="Select one or more. Empty selection = All.",
            style="AttendanceOTBody.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        listing = tk.Listbox(
            window,
            selectmode="multiple",
            exportselection=False,
            font=("Segoe UI", 10),
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            selectbackground=ROYAL_BLUE,
        )
        listing.grid(row=1, column=0, sticky="nsew", padx=(10, 0))
        bar = ttk.Scrollbar(window, orient="vertical", command=listing.yview)
        bar.grid(row=1, column=1, sticky="ns")
        listing.configure(yscrollcommand=bar.set)
        bind_wheel(listing, listing)
        values = tuple(sorted(set(self.values) | set(self.selected)))
        for index, value in enumerate(values):
            listing.insert("end", value)
            if value in self.selected:
                listing.selection_set(index)
        actions = ttk.Frame(window)
        actions.grid(row=2, column=0, pady=10)

        def accept():
            self.set_selected(tuple(values[i] for i in listing.curselection()))
            window.destroy()

        ttk.Button(
            actions, text="Use selection", command=accept, style="AttendanceOT.TButton"
        ).pack(side="left", padx=4)
        ttk.Button(
            actions,
            text="Clear",
            command=lambda: listing.selection_clear(0, "end"),
            style="AttendanceOT.TButton",
        ).pack(side="left", padx=4)
        ttk.Button(
            actions, text="Cancel", command=window.destroy, style="AttendanceOT.TButton"
        ).pack(side="left", padx=4)
        window.grab_set()


class DataTable(ttk.Frame):
    def __init__(
        self,
        parent,
        columns,
        labels=None,
        *,
        hierarchy=False,
        header_colors=None,
    ):
        super().__init__(parent, style="AttendanceOTSurface.TFrame")
        columns = tuple(columns)
        labels = tuple(labels or columns)
        self.header_colors = dict(header_colors or {})
        self.heading_labels = dict(zip(columns, labels))
        self.heading_images = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show="tree headings" if hierarchy else "headings",
            style="AttendanceOT.Treeview",
            selectmode="browse",
            height=8,
        )
        for column, label in zip(columns, labels):
            self.tree.column(column, width=145, minwidth=70, stretch=False)
            color = self.header_colors.get(column)
            if color:
                image = self._heading_image(str(label), color)
                self.heading_images[column] = image
                self.tree.heading(column, text="", image=image, anchor="center")
            else:
                self.tree.heading(column, text=label)
        if hierarchy:
            self.tree.heading("#0", text="Department / Branch / Employee")
            self.tree.column("#0", width=320, minwidth=200, stretch=False)
            for column in columns:
                self.tree.column(column, width=76, anchor="e")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vertical = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.vertical.grid(row=0, column=1, sticky="ns")
        self.horizontal = ttk.Scrollbar(
            self, orient="horizontal", command=self.tree.xview
        )
        self.horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(
            yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set
        )
        bind_wheel(self.tree, self.tree)

    def _heading_image(self, label, background):
        image = Image.new("RGB", (134, 22), background)
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("segoeuib.ttf", 12)
        except OSError:
            font = ImageFont.load_default()
        bounds = draw.textbbox((0, 0), label, font=font)
        x = (image.width - (bounds[2] - bounds[0])) / 2
        y = (image.height - (bounds[3] - bounds[1])) / 2 - bounds[1]
        draw.text((x, y), label, fill="white", font=font)
        return ImageTk.PhotoImage(image, master=self.tree)

    def rows(self, items, columns):
        self.tree.delete(*self.tree.get_children())
        for index, item in enumerate(items):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=tuple(
                    item.get(c) if item.get(c) is not None else "" for c in columns
                ),
            )


class LateMatrixTable(ttk.Frame):
    """Expandable late-count matrix with true per-cell color fills."""

    hierarchy_width = 300
    column_width = 86
    header_height = 34
    row_height = 32

    def __init__(self, parent, columns, *, on_employee_open=None):
        super().__init__(parent, style="AttendanceOTSurface.TFrame")
        self.columns = tuple(columns)
        self.on_employee_open = on_employee_open
        self.groups = ()
        self.expanded = set()
        self.visible_rows = ()
        self.cell_items = {}
        self.cell_text_items = {}
        self._row_hits = []
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            background=CARD_BACKGROUND,
            borderwidth=0,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vertical = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.vertical.grid(row=0, column=1, sticky="ns")
        self.horizontal = ttk.Scrollbar(
            self,
            orient="horizontal",
            command=self.canvas.xview,
        )
        self.horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(
            yscrollcommand=self.vertical.set,
            xscrollcommand=self.horizontal.set,
        )
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Double-1>", self._double_click)
        bind_wheel(self.canvas, self.canvas)
        self._render()

    def set_rows(self, items):
        groups = {}
        for item in items:
            key = (
                item.get("classification") or "UNRESOLVED",
                item.get("group_name") or "(blank)",
            )
            group = groups.setdefault(
                key,
                {
                    "key": key,
                    "label": key[1],
                    "counts": [0] * len(self.columns),
                    "employees": [],
                },
            )
            counts = [int(item.get(column) or 0) for column in self.columns]
            for index, count in enumerate(counts):
                group["counts"][index] += count
            group["employees"].append(
                {
                    "emplid": item.get("emplid") or "",
                    "employee_name": item.get("employee_name") or "",
                    "counts": counts,
                }
            )
        self.groups = tuple(groups.values())
        self.expanded.clear()
        self._render()

    def toggle_group(self, key):
        if key in self.expanded:
            self.expanded.remove(key)
        else:
            self.expanded.add(key)
        self._render()

    def _render(self):
        self.canvas.delete("all")
        self.cell_items.clear()
        self.cell_text_items.clear()
        self._row_hits.clear()
        self._draw_header()
        visible_rows = []
        y = self.header_height
        for group in self.groups:
            group_key = group["key"]
            visible_rows.append(("group", group_key))
            self._draw_row(
                y,
                kind="group",
                key=group_key,
                label=group["label"],
                counts=group["counts"],
                expanded=group_key in self.expanded,
            )
            y += self.row_height
            if group_key in self.expanded:
                for employee in group["employees"]:
                    emplid = employee["emplid"]
                    visible_rows.append(("employee", emplid))
                    label = f"{emplid} — {employee['employee_name']}"
                    self._draw_row(
                        y,
                        kind="employee",
                        key=emplid,
                        label=label,
                        counts=employee["counts"],
                    )
                    y += self.row_height
        self.visible_rows = tuple(visible_rows)
        total_width = self.hierarchy_width + len(self.columns) * self.column_width
        self.canvas.configure(
            scrollregion=(0, 0, total_width, max(y, self.header_height + 1))
        )

    def _draw_header(self):
        self._rectangle(
            0,
            0,
            self.hierarchy_width,
            self.header_height,
            fill="#334155",
            outline="#CBD5E1",
        )
        self.canvas.create_text(
            12,
            self.header_height / 2,
            text="Department / Branch / Employee",
            anchor="w",
            fill="white",
            font=("Segoe UI", 9, "bold"),
        )
        for index, column in enumerate(self.columns):
            x = self.hierarchy_width + index * self.column_width
            self._rectangle(
                x,
                0,
                x + self.column_width,
                self.header_height,
                fill="#334155",
                outline="#CBD5E1",
            )
            self.canvas.create_text(
                x + self.column_width / 2,
                self.header_height / 2,
                text=column,
                fill="white",
                font=("Segoe UI", 9, "bold"),
            )

    def _draw_row(self, y, *, kind, key, label, counts, expanded=False):
        background = CARD_BACKGROUND
        self._rectangle(
            0,
            y,
            self.hierarchy_width,
            y + self.row_height,
            fill=background,
            outline="#CBD5E1",
        )
        if kind == "group":
            prefix = "▼" if expanded else "▶"
            label = f"{prefix}  {label}"
            x = 12
            font = ("Segoe UI", 9, "bold")
        else:
            x = 30
            font = ("Segoe UI", 9)
        self.canvas.create_text(
            x,
            y + self.row_height / 2,
            text=label,
            anchor="w",
            fill=TEXT_PRIMARY,
            font=font,
        )
        row_key = (kind, key)
        for index, count in enumerate(counts):
            cell_x = self.hierarchy_width + index * self.column_width
            fill = self._cell_color(count) if count else background
            rectangle = self._rectangle(
                cell_x,
                y,
                cell_x + self.column_width,
                y + self.row_height,
                fill=fill,
                outline="#CBD5E1",
            )
            self.cell_items[(*row_key, self.columns[index])] = rectangle
            if count:
                text = self.canvas.create_text(
                    cell_x + self.column_width / 2,
                    y + self.row_height / 2,
                    text=str(count),
                    fill="white",
                    font=("Segoe UI", 9, "bold"),
                )
                self.cell_text_items[(*row_key, self.columns[index])] = text
        self._row_hits.append((y, y + self.row_height, kind, key))

    def _rectangle(self, x1, y1, x2, y2, **options):
        return self.canvas.create_rectangle(x1, y1, x2, y2, width=1, **options)

    @staticmethod
    def _cell_color(count):
        return LATE_CELL_ORANGE if int(count) > 10 else LATE_CELL_BLUE

    def _hit(self, event):
        y = self.canvas.canvasy(event.y)
        return next(
            (row for row in self._row_hits if row[0] <= y < row[1]),
            None,
        )

    def _click(self, event):
        hit = self._hit(event)
        if hit and hit[2] == "group":
            self.toggle_group(hit[3])

    def _double_click(self, event):
        hit = self._hit(event)
        if hit and hit[2] == "employee" and self.on_employee_open:
            self.on_employee_open(hit[3])


class ScrollBody(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="AttendanceOTSurface.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background=CARD_BACKGROUND, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=bar.set)
        self.content = ttk.Frame(
            self.canvas, style="AttendanceOTSurface.TFrame", padding=12
        )
        item = self.canvas.create_window(0, 0, anchor="nw", window=self.content)
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfigure(item, width=e.width)
        )
        self.content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        bind_wheel(self.canvas, self.canvas)

    def bind_children(self):
        def visit(widget):
            bind_wheel(widget, self.canvas)
            for child in widget.winfo_children():
                visit(child)

        visit(self.content)
