from hris.artifact_writer import HRISJobArtifactWriter


def test_hris_ho_job_folder_uses_timestamp_only() -> None:
    assert HRISJobArtifactWriter._job_folder_name(
        "HRIS_HO_20260706_161042"
    ) == "20260706_161042"


def test_hris_branch_job_folder_uses_timestamp_only() -> None:
    assert HRISJobArtifactWriter._job_folder_name(
        "HRIS_BRANCH_20260706_161042"
    ) == "20260706_161042"


def test_hris_timestamp_job_id_remains_unchanged() -> None:
    assert HRISJobArtifactWriter._job_folder_name(
        "20260706_161042"
    ) == "20260706_161042"
