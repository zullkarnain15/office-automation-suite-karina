"""Clipboard contracts for read-only ATT & OT tables."""

from __future__ import annotations

from tkinter import ttk

from ui.pages.attendance_ot_widgets import LateMatrixTable
from ui.widgets.table_copy import TreeviewCopyHelper, format_tsv


def test_format_tsv_uses_tabs_and_newlines() -> None:
    assert format_tsv((("NIK", "Name"), ("10001", "Budi"))) == (
        "NIK\tName\n10001\tBudi"
    )


def test_treeview_copy_uses_visible_row_and_column_order(tk_root) -> None:
    tree = ttk.Treeview(
        tk_root,
        columns=("nik", "name", "status"),
        displaycolumns=("name", "nik"),
        show="headings",
        selectmode="extended",
    )
    tree.heading("nik", text="NIK")
    tree.heading("name", text="")
    tree.heading("status", text="Status")
    tree.insert("", "end", iid="first", values=("10001", "Budi", "LATE"))
    tree.insert("", "end", iid="second", values=("10002", "Ani", "ON_TIME"))
    helper = TreeviewCopyHelper(tree, heading_labels={"name": "Name"})

    tree.selection_set(("second", "first"))

    assert helper.copy_selected(include_header=True) is True
    assert tk_root.clipboard_get() == "Name\tNIK\nBudi\t10001\nAni\t10002"
    assert tree.bind("<Control-c>")
    assert tree.bind("<F2>") == ""
    assert tree.bind("<Double-1>") == ""


def test_treeview_context_copy_targets_clicked_cell_and_updates_menu(
    tk_root, monkeypatch
) -> None:
    tree = ttk.Treeview(
        tk_root,
        columns=("nik", "name"),
        show="headings",
        selectmode="extended",
    )
    tree.insert("", "end", iid="first", values=("10001", "Budi"))
    tree.insert("", "end", iid="second", values=("10002", "Ani"))
    helper = TreeviewCopyHelper(tree, heading_labels={"nik": "NIK", "name": "Name"})
    tree.selection_set("first")
    monkeypatch.setattr(tree, "identify_row", lambda _y: "second")
    monkeypatch.setattr(tree, "identify_column", lambda _x: "#2")
    monkeypatch.setattr(tree, "identify_region", lambda _x, _y: "cell")

    assert helper.prepare_context(10, 10) == ("second", "name")
    assert tree.selection() == ("second",)
    assert helper.copy_context_cell() is True
    assert tk_root.clipboard_get() == "Ani"

    tree.selection_remove(*tree.selection())
    monkeypatch.setattr(tree, "identify_row", lambda _y: "")
    monkeypatch.setattr(tree, "identify_column", lambda _x: "")
    monkeypatch.setattr(tree, "identify_region", lambda _x, _y: "nothing")
    helper.prepare_context(10, 10)

    assert helper.menu.entrycget("Copy Cell", "state") == "disabled"
    assert helper.menu.entrycget("Copy Selected Row(s)", "state") == "disabled"
    assert helper.menu.entrycget("Copy Selected + Header", "state") == "disabled"


def test_late_matrix_copies_multiple_visible_rows_and_cell(tk_root) -> None:
    matrix = LateMatrixTable(tk_root, ("Jan", "Total"))
    matrix.set_rows(
        (
            {
                "classification": "HO",
                "group_name": "Finance",
                "emplid": "10001",
                "employee_name": "Budi",
                "Jan": 2,
                "Total": 2,
            },
        )
    )
    matrix.toggle_group(("HO", "Finance"))
    group_hit, employee_hit = matrix._row_hits
    matrix._select_hit(group_hit)
    matrix._select_hit(employee_hit, control=True)
    matrix._render()

    assert matrix.copy_selected(include_header=True) is True
    assert tk_root.clipboard_get() == (
        "Department / Branch / Employee\tJan\tTotal\n"
        "Finance\t2\t2\n"
        "10001 — Budi\t2\t2"
    )

    matrix._context_hit = matrix._row_hits[1]
    matrix._context_column = 0
    assert matrix.copy_context_cell() is True
    assert tk_root.clipboard_get() == "2"
