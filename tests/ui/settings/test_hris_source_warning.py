from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ui.pages.settings.general_section import GeneralSection


@pytest.mark.parametrize("accepted", [False, True])
def test_same_folder_warns_and_respects_choice(tmp_path, accepted):
    folder = str(tmp_path / "HO")
    section = make_section(folder, folder + "/.", accepted)
    GeneralSection.save_hris_txt_sources(section)
    section.services.dialog_service.confirm.assert_called_once()
    assert section.page.run_task.call_count == int(accepted)
    if accepted:
        section.page.run_task.call_args.args[0]()
        section.services.database_service.save_hris_txt_source_preferences.assert_called_once()


@pytest.mark.parametrize("folders", [("", ""), ("HO", ""), ("HO", "Branch")])
def test_distinct_or_empty_folders_save_without_warning(folders):
    section = make_section(*folders, accepted=False)
    GeneralSection.save_hris_txt_sources(section)
    section.services.dialog_service.confirm.assert_not_called()
    section.page.run_task.assert_called_once()


def make_section(ho, branch, accepted):
    return SimpleNamespace(
        _require_active_database=Mock(return_value="test.db"),
        hris_ho_source_var=Mock(get=Mock(return_value=ho)),
        hris_branch_source_var=Mock(get=Mock(return_value=branch)),
        services=SimpleNamespace(
            dialog_service=Mock(confirm=Mock(return_value=accepted)),
            database_service=Mock(),
        ),
        page=Mock(),
        _apply_hris_txt_sources=Mock(),
        result=Mock(),
    )
