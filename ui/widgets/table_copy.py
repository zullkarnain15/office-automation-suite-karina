"""Read-only clipboard actions for tabular Tk widgets."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable, Mapping, Sequence
from tkinter import ttk

from ui.constants import CARD_BACKGROUND, ROYAL_BLUE, TEXT_PRIMARY


def format_tsv(rows: Iterable[Iterable[object]]) -> str:
    """Return rows as tab-separated text suitable for pasting into Excel."""

    return "\n".join(
        "\t".join("" if value is None else str(value) for value in row)
        for row in rows
    )


def copy_to_clipboard(widget: tk.Misc, rows: Iterable[Iterable[object]]) -> bool:
    """Write tabular text through Tk's native clipboard integration."""

    text = format_tsv(rows)
    if not text:
        return False
    widget.clipboard_clear()
    widget.clipboard_append(text)
    widget.update_idletasks()
    return True


def create_copy_menu(
    widget: tk.Misc, commands: Mapping[str, Callable[[], object]]
) -> tk.Menu:
    """Create the consistently styled three-action table copy menu."""

    menu = tk.Menu(
        widget,
        tearoff=False,
        background=CARD_BACKGROUND,
        foreground=TEXT_PRIMARY,
        activebackground=ROYAL_BLUE,
        activeforeground="white",
        font=("Segoe UI", 9),
    )
    for label in ("Copy Cell", "Copy Selected Row(s)", "Copy Selected + Header"):
        menu.add_command(label=label, command=commands[label])
    return menu


class TreeviewCopyHelper:
    """Attach read-only TSV copy behavior to an existing ``ttk.Treeview``."""

    def __init__(
        self,
        tree: ttk.Treeview,
        *,
        heading_labels: Mapping[str, object] | None = None,
    ) -> None:
        self.tree = tree
        self.heading_labels = dict(heading_labels or {})
        self._context_row = ""
        self._context_column = ""
        self.menu = create_copy_menu(
            tree,
            {
                "Copy Cell": self.copy_context_cell,
                "Copy Selected Row(s)": self.copy_selected,
                "Copy Selected + Header": lambda: self.copy_selected(
                    include_header=True
                ),
            },
        )
        tree.bind("<Control-c>", self._copy_selected_event, add="+")
        tree.bind("<Control-C>", self._copy_selected_event, add="+")
        tree.bind("<Button-3>", self._show_menu, add="+")

    def _shows_tree_column(self) -> bool:
        return "tree" in tuple(self.tree["show"])

    def visible_columns(self) -> tuple[str, ...]:
        display = tuple(self.tree["displaycolumns"])
        data_columns = tuple(self.tree["columns"])
        columns = data_columns if display == ("#all",) else display
        return ("#0", *columns) if self._shows_tree_column() else columns

    def selected_rows(self) -> tuple[str, ...]:
        selected = set(self.tree.selection())

        def displayed(parent: str = ""):
            for item in self.tree.get_children(parent):
                yield item
                yield from displayed(item)

        return tuple(item for item in displayed() if item in selected)

    def row_values(
        self, item: str, columns: Sequence[str] | None = None
    ) -> tuple[object, ...]:
        columns = tuple(columns or self.visible_columns())
        return tuple(
            self.tree.item(item, "text")
            if column == "#0"
            else self.tree.set(item, column)
            for column in columns
        )

    def header_values(
        self, columns: Sequence[str] | None = None
    ) -> tuple[object, ...]:
        columns = tuple(columns or self.visible_columns())
        return tuple(
            self.heading_labels.get(column) or self.tree.heading(column, "text")
            for column in columns
        )

    def copy_selected(self, *, include_header: bool = False) -> bool:
        items = self.selected_rows()
        if not items:
            return False
        columns = self.visible_columns()
        rows: list[tuple[object, ...]] = []
        if include_header:
            rows.append(self.header_values(columns))
        rows.extend(self.row_values(item, columns) for item in items)
        return copy_to_clipboard(self.tree, rows)

    def copy_context_cell(self) -> bool:
        if not self._context_row or not self._context_column:
            return False
        value = self.row_values(self._context_row, (self._context_column,))[0]
        return copy_to_clipboard(self.tree, ((value,),))

    def prepare_context(self, x: int, y: int) -> tuple[str, str]:
        """Resolve a right-click target and update menu command states."""

        row = self.tree.identify_row(y)
        column_token = self.tree.identify_column(x)
        region = self.tree.identify_region(x, y)
        columns = self.visible_columns()
        column = ""
        if region in {"cell", "tree"} and column_token:
            index = int(column_token[1:])
            if self._shows_tree_column():
                if index < len(columns):
                    column = columns[index]
            elif index and index <= len(columns):
                column = columns[index - 1]
        self._context_row = row if row and column else ""
        self._context_column = column if row and column else ""

        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
            self.tree.focus(row)

        has_cell = bool(self._context_row and self._context_column)
        has_rows = bool(self.selected_rows())
        self.menu.entryconfigure("Copy Cell", state="normal" if has_cell else "disabled")
        row_state = "normal" if has_rows else "disabled"
        self.menu.entryconfigure("Copy Selected Row(s)", state=row_state)
        self.menu.entryconfigure("Copy Selected + Header", state=row_state)
        return self._context_row, self._context_column

    def _copy_selected_event(self, _event=None):
        self.copy_selected()
        return "break"

    def _show_menu(self, event):
        self.prepare_context(event.x, event.y)
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
        return "break"
