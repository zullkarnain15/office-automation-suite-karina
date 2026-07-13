from hris.diagnostics import HRISDiagnosticPackWriter


def test_diagnostic_redaction_preserves_nested_step_structure() -> None:
    writer = HRISDiagnosticPackWriter()

    result = writer._redact_mapping(
        {
            "assisted_steps": [
                {
                    "step_name": "upload",
                    "action": "click",
                }
            ],
            "nested": {
                "status": "SUBMITTED",
                "access_token": "secret-value",
            },
        }
    )

    assert result["assisted_steps"] == [
        {
            "step_name": "upload",
            "action": "click",
        }
    ]
    assert result["nested"]["status"] == "SUBMITTED"
    assert result["nested"]["access_token"] == "<REDACTED>"
