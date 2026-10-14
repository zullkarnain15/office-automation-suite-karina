"""Page-local ttk table, selection and scrolling helpers."""

import tkinter as tk
from tkinter import ttk

from ui.theme.attendance_ot import (
    DEFAULT_ATTENDANCE_OT_THEME,
    AttendanceOTTheme,
)
from ui.widgets.table_copy import (
    TreeviewCopyHelper,
    copy_to_clipboard,
    create_copy_menu,
)


_PALETTE = DEFAULT_ATTENDANCE_OT_THEME.palette
ATTENDANCE_OT_CARD = _PALETTE.card
ATTENDANCE_OT_CHALK_BLUE = _PALETTE.chalk_blue
ATTENDANCE_OT_CHALK_PINK = _PALETTE.chalk_pink
ATTENDANCE_OT_CHALK_WHITE = _PALETTE.chalk_white
ATTENDANCE_OT_CHALK_YELLOW = _PALETTE.chalk_yellow
ATTENDANCE_OT_SELECTION = _PALETTE.selection
ATTENDANCE_OT_SURFACE = _PALETTE.surface
ATTENDANCE_OT_TEXT = _PALETTE.ink
LATE_CELL_STANDARD = _PALETTE.chalk_blue
LATE_CELL_HIGH = _PALETTE.chalk_pink


def _theme(value: AttendanceOTTheme | None) -> AttendanceOTTheme:
    return value or DEFAULT_ATTENDANCE_OT_THEME


def install_panel_border(host: tk.Misc, theme: AttendanceOTTheme | None = None):
    """Place a subtle standard border behind a panel's interactive body."""

    palette = _theme(theme).palette
    canvas = tk.Canvas(
        host,
        background=palette.card,
        borderwidth=0,
        highlightthickness=0,
        takefocus=0,
    )
    canvas.place(x=0, y=0, relwidth=1, relheight=1)
    line_width = max(
        1,
        round(float(host.tk.call("tk", "scaling")) / (96.0 / 72.0)),
    )

    def draw(_event=None):
        if not canvas.winfo_exists():
            return
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        canvas.delete("panel-border")
        if width < 8 or height < 8:
            return
        canvas.create_rectangle(
            2,
            2,
            width - 3,
            height - 3,
            outline=palette.ink,
            width=line_width,
            tags=("panel-border",),
            state="disabled",
        )
        canvas.tag_lower("panel-border")

    host.bind("<Configure>", draw, add="+")
    host.after_idle(draw)
    return canvas


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


class KPICard(tk.Frame):
    """Compact KPI card with an optional, consistently aligned icon tile."""

    def __init__(self, parent, *, title, variable, accent, icon=None, theme=None):
        self.theme = _theme(theme)
        super().__init__(
            parent,
            background=self.theme.palette.chalk_white,
            borderwidth=0,
            padx=2,
            pady=2,
        )
        self.border_canvas = install_panel_border(self, self.theme)
        self.accent = accent
        self.body = tk.Frame(
            self,
            background=ATTENDANCE_OT_CARD,
            padx=14,
            pady=12,
        )
        self.body.pack(fill="both", expand=True)
        self.accent_bar = tk.Frame(
            self.body,
            background=accent,
            height=6,
            borderwidth=0,
        )
        self.accent_bar.pack(fill="x", pady=(0, 10))
        self.accent_bar.pack_propagate(False)
        self.content = tk.Frame(self.body, background=ATTENDANCE_OT_CARD)
        self.content.pack(fill="both", expand=True)
        self.icon = icon
        self.icon_label = None
        if icon is not None:
            self.icon_label = tk.Label(
                self.content,
                image=icon,
                background=ATTENDANCE_OT_CARD,
                borderwidth=0,
            )
            self.icon_label.pack(side="left", padx=(0, 14), anchor="center")
        self.text_area = tk.Frame(self.content, background=ATTENDANCE_OT_CARD)
        self.text_area.pack(side="left", fill="both", expand=True)
        self.title_label = tk.Label(
            self.text_area,
            text=title,
            background=ATTENDANCE_OT_CARD,
            foreground=ATTENDANCE_OT_TEXT,
            font=(self.theme.typography.ui_family, 10, "bold"),
        )
        self.title_label.pack(anchor="w")
        self.value_label = tk.Label(
            self.text_area,
            textvariable=variable,
            background=ATTENDANCE_OT_CARD,
            foreground=accent,
            font=(self.theme.typography.ui_family, 15, "bold"),
        )
        self.value_label.pack(anchor="w", pady=(7, 0))


class SimpleTrendPanel(tk.Frame):
    """Lightweight twelve-month bar chart using only Frames and Labels."""

    def __init__(
        self,
        parent,
        months,
        *,
        title="Late Record Trend",
        accent=ATTENDANCE_OT_CHALK_PINK,
        theme=None,
    ):
        self.theme = _theme(theme)
        super().__init__(
            parent,
            background=self.theme.palette.chalk_white,
            borderwidth=0,
            padx=2,
            pady=2,
        )
        self.border_canvas = install_panel_border(self, self.theme)
        self.months = tuple(months)
        self.accent = accent
        self.body = tk.Frame(
            self,
            background=ATTENDANCE_OT_CARD,
            padx=14,
            pady=12,
        )
        self.body.pack(fill="both", expand=True)
        self.title_label = tk.Label(
            self.body,
            text=title,
            background=ATTENDANCE_OT_CARD,
            foreground=ATTENDANCE_OT_TEXT,
            font=self.theme.heading_font,
        )
        self.title_label.pack(anchor="w", pady=(0, 10))
        chart = tk.Frame(self.body, background=ATTENDANCE_OT_CARD)
        chart.pack(fill="x", expand=True)
        self.value_vars = []
        self.bars = []
        for index, month in enumerate(self.months):
            chart.columnconfigure(index, weight=1, uniform="late-trend-month")
            slot = tk.Frame(chart, background=ATTENDANCE_OT_CARD, height=100)
            slot.grid(row=0, column=index, sticky="nsew", padx=2)
            slot.grid_propagate(False)
            slot.rowconfigure(1, weight=1)
            value = tk.StringVar(value="0")
            self.value_vars.append(value)
            tk.Label(
                slot,
                textvariable=value,
                background=ATTENDANCE_OT_CARD,
                foreground=ATTENDANCE_OT_TEXT,
                font=self.theme.body_bold_font,
            ).grid(row=0, column=0)
            bar_area = tk.Frame(
                slot,
                background=ATTENDANCE_OT_CARD,
                height=64,
            )
            bar_area.grid(row=1, column=0, sticky="nsew")
            bar_area.pack_propagate(False)
            bar = tk.Frame(
                bar_area,
                background=accent,
                width=18,
                height=2,
                borderwidth=0,
            )
            bar.pack(side="bottom")
            bar.pack_propagate(False)
            self.bars.append(bar)
            tk.Label(
                slot,
                text=month,
                background=ATTENDANCE_OT_CARD,
                foreground=ATTENDANCE_OT_TEXT,
                font=self.theme.body_bold_font,
            ).grid(row=2, column=0, pady=(4, 0))

    def set_values(self, values):
        values = tuple(max(0, int(value or 0)) for value in values)
        maximum = max(values, default=0)
        for index, variable in enumerate(self.value_vars):
            value = values[index] if index < len(values) else 0
            variable.set(f"{value:,}")
            height = 2 if maximum == 0 else max(2, round(64 * value / maximum))
            self.bars[index].configure(height=height)


class TopFiveBarList(tk.Frame):
    """Reusable ranked list with proportional bars made from native Frames."""

    def __init__(self, parent, *, title, accent, theme=None):
        self.theme = _theme(theme)
        super().__init__(
            parent,
            background=self.theme.palette.chalk_white,
            borderwidth=0,
            padx=2,
            pady=2,
        )
        self.border_canvas = install_panel_border(self, self.theme)
        self.accent = accent
        self.body = tk.Frame(
            self,
            background=ATTENDANCE_OT_CARD,
            padx=14,
            pady=12,
        )
        self.body.pack(fill="both", expand=True)
        self.title_label = tk.Label(
            self.body,
            text=title,
            background=ATTENDANCE_OT_CARD,
            foreground=ATTENDANCE_OT_TEXT,
            font=self.theme.heading_font,
        )
        self.title_label.pack(anchor="w", pady=(0, 10))
        listing = tk.Frame(self.body, background=ATTENDANCE_OT_CARD)
        listing.pack(fill="both", expand=True)
        listing.columnconfigure(1, weight=1)
        self.rows = []
        for index in range(5):
            rank = tk.StringVar(value=f"{index + 1}.")
            name = tk.StringVar(value="—")
            count = tk.StringVar(value="0")
            tk.Label(
                listing,
                textvariable=rank,
                width=3,
                anchor="e",
                background=ATTENDANCE_OT_CARD,
                foreground=ATTENDANCE_OT_TEXT,
                font=(self.theme.typography.ui_family, 10, "bold"),
            ).grid(row=index, column=0, sticky="e", padx=(0, 6), pady=3)
            content = tk.Frame(listing, background=ATTENDANCE_OT_CARD)
            content.grid(row=index, column=1, sticky="ew", pady=3)
            content.columnconfigure(0, weight=1)
            tk.Label(
                content,
                textvariable=name,
                anchor="w",
                background=ATTENDANCE_OT_CARD,
                foreground=ATTENDANCE_OT_TEXT,
                font=(self.theme.typography.ui_family, 10, "bold"),
            ).grid(row=0, column=0, sticky="ew")
            track = tk.Frame(
                content, background=self.theme.palette.chalk_muted, height=7
            )
            track.grid(row=1, column=0, sticky="ew", pady=(2, 0))
            track.grid_propagate(False)
            fill = tk.Frame(track, background=accent, borderwidth=0)
            fill.place(x=0, y=0, relheight=1, relwidth=0)
            tk.Label(
                listing,
                textvariable=count,
                width=7,
                anchor="e",
                background=ATTENDANCE_OT_CARD,
                foreground=accent,
                font=(self.theme.typography.ui_family, 10, "bold"),
            ).grid(row=index, column=2, sticky="e", padx=(8, 0), pady=3)
            self.rows.append({"name": name, "count": count, "fill": fill})

    def set_items(self, items):
        items = tuple(items)[:5]
        maximum = max((int(value or 0) for _name, value in items), default=0)
        for index, row in enumerate(self.rows):
            if index < len(items):
                name, value = items[index]
                value = int(value or 0)
                row["name"].set(str(name or "—"))
                row["count"].set(f"{value:,}")
                width = value / maximum if maximum else 0
            else:
                row["name"].set("—")
                row["count"].set("0")
                width = 0
            row["fill"].place_configure(relwidth=width)


class MultiSelect(ttk.Frame):
    _BUTTON_STYLES = {
        "Branch": "AttendanceOTFilterBranch.TButton",
        "Pay Group": "AttendanceOTFilterPayGroup.TButton",
        "Department": "AttendanceOTFilterDepartment.TButton",
        "Division": "AttendanceOTFilterDivision.TButton",
    }

    def __init__(self, parent, title, *, theme=None):
        self.theme = _theme(theme)
        super().__init__(parent, style="AttendanceOTSurface.TFrame")
        self.title = title
        self.values = ()
        self.selected = ()
        self.button = ttk.Button(
            self,
            text=f"{title}: All",
            command=self.open,
            style=self._BUTTON_STYLES.get(title, "AttendanceOT.TButton"),
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
        window.configure(background=self.theme.palette.surface)
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
            font=(self.theme.typography.ui_family, 10),
            background=ATTENDANCE_OT_CARD,
            foreground=ATTENDANCE_OT_TEXT,
            selectbackground=ATTENDANCE_OT_SURFACE,
            selectforeground=ATTENDANCE_OT_TEXT,
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
        actions = ttk.Frame(window, style="AttendanceOTSurface.TFrame")
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
        theme=None,
        tree_style="AttendanceOT.Treeview",
        frame_style="AttendanceOTSurface.TFrame",
        zebra_stripes=False,
    ):
        self.theme = _theme(theme)
        self.zebra_stripes = zebra_stripes
        super().__init__(parent, style=frame_style)
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
            style=tree_style,
            selectmode="extended",
            height=8,
        )
        if self.zebra_stripes:
            self.tree.tag_configure(
                "detail-even",
                background=self.theme.palette.card,
                foreground=self.theme.palette.ink,
            )
            self.tree.tag_configure(
                "detail-odd",
                background=self.theme.palette.surface,
                foreground=self.theme.palette.ink,
            )
        for column, label in zip(columns, labels):
            self.tree.column(column, width=145, minwidth=70, stretch=False)
            self.tree.heading(column, text=label, anchor="center")
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
        self.copy_helper = TreeviewCopyHelper(
            self.tree,
            heading_labels={
                **self.heading_labels,
                "#0": "Department / Branch / Employee",
            },
        )

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
                tags=(("detail-even" if index % 2 == 0 else "detail-odd",)
                      if self.zebra_stripes else ()),
            )


class LateMatrixTable(ttk.Frame):
    """Expandable late-count matrix with true per-cell color fills."""

    hierarchy_width = 300
    column_width = 86
    header_height = 34
    row_height = 32

    def __init__(self, parent, columns, *, on_employee_open=None, theme=None):
        self.theme = _theme(theme)
        super().__init__(parent, style="AttendanceOTSurface.TFrame")
        self.columns = tuple(columns)
        self.on_employee_open = on_employee_open
        self.groups = ()
        self.expanded = set()
        self.visible_rows = ()
        self.cell_items = {}
        self.cell_text_items = {}
        self._row_hits = []
        self._selected_rows = set()
        self._selection_anchor = None
        self._context_hit = None
        self._context_column = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            background=ATTENDANCE_OT_CARD,
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
        self.canvas.bind("<Button-3>", self._show_copy_menu)
        self.canvas.bind("<Control-c>", self._copy_selected_event)
        self.canvas.bind("<Control-C>", self._copy_selected_event)
        self.copy_menu = create_copy_menu(
            self.canvas,
            {
                "Copy Cell": self.copy_context_cell,
                "Copy Selected Row(s)": self.copy_selected,
                "Copy Selected + Header": lambda: self.copy_selected(
                    include_header=True
                ),
            },
        )
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
        self._selected_rows.clear()
        self._selection_anchor = None
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
        visible_selection_keys = set()
        y = self.header_height
        for group in self.groups:
            group_key = group["key"]
            visible_rows.append(("group", group_key))
            selection_key = ("group", group_key)
            visible_selection_keys.add(selection_key)
            self._draw_row(
                y,
                kind="group",
                key=group_key,
                label=group["label"],
                counts=group["counts"],
                expanded=group_key in self.expanded,
                selection_key=selection_key,
            )
            y += self.row_height
            if group_key in self.expanded:
                for employee_index, employee in enumerate(group["employees"]):
                    emplid = employee["emplid"]
                    visible_rows.append(("employee", emplid))
                    label = f"{emplid} — {employee['employee_name']}"
                    selection_key = ("employee", group_key, employee_index)
                    visible_selection_keys.add(selection_key)
                    self._draw_row(
                        y,
                        kind="employee",
                        key=emplid,
                        label=label,
                        counts=employee["counts"],
                        selection_key=selection_key,
                    )
                    y += self.row_height
        self.visible_rows = tuple(visible_rows)
        self._selected_rows.intersection_update(visible_selection_keys)
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
            fill=ATTENDANCE_OT_SURFACE,
            outline=ATTENDANCE_OT_TEXT,
        )
        self.canvas.create_text(
            12,
            self.header_height / 2,
            text="Department / Branch / Employee",
            anchor="w",
            fill=ATTENDANCE_OT_TEXT,
            font=self.theme.table_heading_font,
        )
        for index, column in enumerate(self.columns):
            x = self.hierarchy_width + index * self.column_width
            self._rectangle(
                x,
                0,
                x + self.column_width,
                self.header_height,
                fill=ATTENDANCE_OT_SURFACE,
                outline=ATTENDANCE_OT_TEXT,
            )
            self.canvas.create_text(
                x + self.column_width / 2,
                self.header_height / 2,
                text=column,
                fill=ATTENDANCE_OT_TEXT,
                font=self.theme.table_heading_font,
            )

    def _draw_row(
        self,
        y,
        *,
        kind,
        key,
        label,
        counts,
        expanded=False,
        selection_key,
    ):
        copy_label = label
        selected = selection_key in self._selected_rows
        background = (
            ATTENDANCE_OT_SELECTION if selected else ATTENDANCE_OT_CARD
        )
        outline = (
            ATTENDANCE_OT_CHALK_BLUE
            if selected
            else ATTENDANCE_OT_TEXT
        )
        self._rectangle(
            0,
            y,
            self.hierarchy_width,
            y + self.row_height,
            fill=background,
            outline=outline,
        )
        if kind == "group":
            prefix = "▼" if expanded else "▶"
            label = f"{prefix}  {label}"
            x = 12
            font = self.theme.body_bold_font
        else:
            x = 30
            font = self.theme.body_font
        self.canvas.create_text(
            x,
            y + self.row_height / 2,
            text=label,
            anchor="w",
            fill=ATTENDANCE_OT_CHALK_WHITE if selected else ATTENDANCE_OT_TEXT,
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
                outline=outline,
            )
            self.cell_items[(*row_key, self.columns[index])] = rectangle
            if count:
                text = self.canvas.create_text(
                    cell_x + self.column_width / 2,
                    y + self.row_height / 2,
                    text=str(count),
                    fill=ATTENDANCE_OT_CARD,
                    font=self.theme.body_bold_font,
                )
                self.cell_text_items[(*row_key, self.columns[index])] = text
        self._row_hits.append(
            (
                y,
                y + self.row_height,
                kind,
                key,
                copy_label,
                tuple(counts),
                selection_key,
            )
        )

    def _rectangle(self, x1, y1, x2, y2, **options):
        return self.canvas.create_rectangle(x1, y1, x2, y2, width=1, **options)

    @staticmethod
    def _cell_color(count):
        return LATE_CELL_HIGH if int(count) > 10 else LATE_CELL_STANDARD

    def _hit(self, event):
        y = self.canvas.canvasy(event.y)
        return next(
            (row for row in self._row_hits if row[0] <= y < row[1]),
            None,
        )

    def _click(self, event):
        hit = self._hit(event)
        if not hit:
            return
        self.canvas.focus_set()
        self._select_hit(
            hit,
            control=bool(event.state & 0x0004),
            shift=bool(event.state & 0x0001),
        )
        if hit[2] == "group":
            self.toggle_group(hit[3])
        else:
            self._render()

    def _double_click(self, event):
        hit = self._hit(event)
        if hit and hit[2] == "employee" and self.on_employee_open:
            self.on_employee_open(hit[3])

    def _select_hit(self, hit, *, control=False, shift=False):
        key = hit[6]
        visible_keys = [row[6] for row in self._row_hits]
        if shift and self._selection_anchor in visible_keys:
            start = visible_keys.index(self._selection_anchor)
            end = visible_keys.index(key)
            selected = set(visible_keys[min(start, end) : max(start, end) + 1])
            if control:
                self._selected_rows.update(selected)
            else:
                self._selected_rows = selected
        elif control:
            if key in self._selected_rows:
                self._selected_rows.remove(key)
            else:
                self._selected_rows.add(key)
        else:
            self._selected_rows = {key}
        self._selection_anchor = key

    def _column_at(self, event_x):
        x = self.canvas.canvasx(event_x)
        if 0 <= x < self.hierarchy_width:
            return -1
        index = int((x - self.hierarchy_width) // self.column_width)
        return index if 0 <= index < len(self.columns) else None

    @staticmethod
    def _hit_values(hit):
        return (hit[4], *hit[5])

    def _selected_hits(self):
        return tuple(hit for hit in self._row_hits if hit[6] in self._selected_rows)

    def copy_selected(self, *, include_header=False):
        hits = self._selected_hits()
        if not hits:
            return False
        rows = []
        if include_header:
            rows.append(("Department / Branch / Employee", *self.columns))
        rows.extend(self._hit_values(hit) for hit in hits)
        return copy_to_clipboard(self.canvas, rows)

    def copy_context_cell(self):
        if self._context_hit is None or self._context_column is None:
            return False
        value = self._hit_values(self._context_hit)[self._context_column + 1]
        return copy_to_clipboard(self.canvas, ((value,),))

    def _copy_selected_event(self, _event=None):
        self.copy_selected()
        return "break"

    def _show_copy_menu(self, event):
        hit = self._hit(event)
        column = self._column_at(event.x)
        self._context_hit = hit if hit is not None and column is not None else None
        self._context_column = column if self._context_hit is not None else None
        if hit is not None and hit[6] not in self._selected_rows:
            self._selected_rows = {hit[6]}
            self._selection_anchor = hit[6]
            self._render()
        self.canvas.focus_set()
        cell_state = "normal" if self._context_hit is not None else "disabled"
        row_state = "normal" if self._selected_hits() else "disabled"
        self.copy_menu.entryconfigure("Copy Cell", state=cell_state)
        self.copy_menu.entryconfigure("Copy Selected Row(s)", state=row_state)
        self.copy_menu.entryconfigure("Copy Selected + Header", state=row_state)
        try:
            self.copy_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.copy_menu.grab_release()
        return "break"


class ScrollBody(ttk.Frame):
    def __init__(self, parent, *, theme=None):
        self.theme = _theme(theme)
        super().__init__(parent, style="AttendanceOTSurface.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            background=ATTENDANCE_OT_SURFACE,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=bar.set)
        self.content = ttk.Frame(
            self.canvas,
            style="AttendanceOTSurface.TFrame",
            padding=12,
        )
        item = self.canvas.create_window(0, 0, anchor="nw", window=self.content)
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(item, width=e.width),
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
