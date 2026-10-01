from __future__ import annotations

import hashlib
import json
from pathlib import Path

from shared.update.transaction_store import UpdateTransactionStore
from updater.main import EXIT_ROLLBACK_SUCCEEDED, EXIT_SUCCESS, main


def test_full_simulated_happy_path_success(tmp_path: Path) -> None:
    data_root, app_root, staging = layout(tmp_path, new_health_success=True)
    database = write_data_files(data_root)
    transaction = create_transaction(data_root, app_root, staging)

    code = main(
        [
            "--transaction",
            str(transaction.transaction_path),
            "--shutdown-timeout",
            "5",
            "--health-timeout",
            "5",
        ]
    )

    assert code == EXIT_SUCCESS
    state = json.loads(transaction.transaction_path.read_text(encoding="utf-8"))
    assert state["status"] == "SUCCESS"
    assert (app_root / "app.py").read_text(encoding="utf-8").startswith("import json")
    assert (transaction.transaction_path.parent / "healthcheck_success.json").is_file()
    assert database.read_bytes() == b"database"


def test_full_simulated_failure_path_rolls_back(tmp_path: Path) -> None:
    data_root, app_root, staging = layout(tmp_path, new_health_success=False)
    database = write_data_files(data_root)
    database_hash = sha256(database)
    old_source = (app_root / "app.py").read_text(encoding="utf-8")
    transaction = create_transaction(data_root, app_root, staging)

    code = main(
        [
            "--transaction",
            str(transaction.transaction_path),
            "--shutdown-timeout",
            "5",
            "--health-timeout",
            "1",
        ]
    )

    assert code == EXIT_ROLLBACK_SUCCEEDED
    state = json.loads(transaction.transaction_path.read_text(encoding="utf-8"))
    assert state["status"] == "ROLLED_BACK"
    assert (app_root / "app.py").read_text(encoding="utf-8") == old_source
    assert (data_root / "update" / "failed" / transaction.transaction_id / "application").is_dir()
    assert sha256(database) == database_hash


def layout(tmp_path: Path, *, new_health_success: bool):
    data_root = tmp_path / "data"
    app_root = tmp_path / "app"
    staging = data_root / "update" / "staging" / "v1.1.0"
    staged_app = staging / "application"
    app_root.mkdir(parents=True)
    staged_app.mkdir(parents=True)
    (app_root / "app.py").write_text(old_app_script(), encoding="utf-8")
    (staged_app / "app.py").write_text(new_app_script(success=new_health_success), encoding="utf-8")
    return data_root, app_root, staging


def create_transaction(data_root: Path, app_root: Path, staging: Path):
    store = UpdateTransactionStore(data_root)
    return store.create(
        current_version="1.0.0",
        target_version="1.1.0",
        package_path=data_root / "package.zip",
        package_sha256="abc",
        staging_path=staging,
        application_root=app_root,
        database_backup_path=data_root / "backup" / "database" / "backup.db",
        entry_executable="app.py",
    )


def write_data_files(data_root: Path) -> Path:
    database = data_root / "database" / "OAS-K.db"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"database")
    profile = data_root / "recorder_profiles" / "hris" / "profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text("profile", encoding="utf-8")
    return database


def old_app_script() -> str:
    return (
        "import pathlib, sys\n"
        "if '--post-rollback' in sys.argv:\n"
        "    path = pathlib.Path(sys.argv[sys.argv.index('--update-transaction') + 1])\n"
        "    (path.parent / 'rollback_started.txt').write_text('old', encoding='utf-8')\n"
    )


def new_app_script(*, success: bool) -> str:
    if not success:
        return "import sys; raise SystemExit(3)\n"
    return (
        "import json, pathlib, sys\n"
        "path = pathlib.Path(sys.argv[sys.argv.index('--update-transaction') + 1])\n"
        "payload = {\n"
        "    'transaction_id': json.loads(path.read_text(encoding='utf-8'))['transaction_id'],\n"
        "    'status': 'SUCCESS',\n"
        "    'application_version': '1.1.0',\n"
        "    'checks': {'application_version': True, 'database_open': True},\n"
        "}\n"
        "(path.parent / 'healthcheck_success.json').write_text(json.dumps(payload), encoding='utf-8')\n"
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
