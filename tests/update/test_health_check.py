from __future__ import annotations

import json
from pathlib import Path

from updater.main import wait_for_health_marker


def test_wrong_health_check_transaction_id_rejected(tmp_path: Path) -> None:
    transaction = tmp_path / "data" / "update" / "transactions" / "tx" / "transaction.json"
    transaction.parent.mkdir(parents=True)
    marker = transaction.parent / "healthcheck_success.json"
    marker.write_text(
        json.dumps(
            {
                "transaction_id": "wrong",
                "status": "SUCCESS",
                "application_version": "1.1.0",
                "checks": {"application_version": True},
            }
        ),
        encoding="utf-8",
    )
    assert not wait_for_health_marker(transaction, "tx", "1.1.0", 0.1)


def test_wrong_application_version_rejected(tmp_path: Path) -> None:
    transaction = tmp_path / "data" / "update" / "transactions" / "tx" / "transaction.json"
    transaction.parent.mkdir(parents=True)
    marker = transaction.parent / "healthcheck_success.json"
    marker.write_text(
        json.dumps(
            {
                "transaction_id": "tx",
                "status": "SUCCESS",
                "application_version": "1.0.0",
                "checks": {"application_version": True},
            }
        ),
        encoding="utf-8",
    )
    assert not wait_for_health_marker(transaction, "tx", "1.1.0", 0.1)
