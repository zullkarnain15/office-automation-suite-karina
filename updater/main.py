"""Standalone OAS-K updater CLI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from updater.application_replacer import (
    ApplicationReplacementError,
    backup_application,
    replace_application,
)
from updater.process_waiter import request_graceful_exit, wait_for_exit
from updater.rollback_service import restore_previous_application
from updater.updater_logger import configure_logger

EXIT_SUCCESS = 0
EXIT_INVALID_TRANSACTION = 10
EXIT_OLD_PROCESS_TIMEOUT = 11
EXIT_BACKUP_FAILED = 12
EXIT_REPLACEMENT_FAILED = 13
EXIT_NEW_APPLICATION_LAUNCH_FAILED = 14
EXIT_HEALTH_CHECK_FAILED = 15
EXIT_ROLLBACK_SUCCEEDED = 16
EXIT_ROLLBACK_FAILED = 17
EXIT_UNEXPECTED_ERROR = 18

TERMINAL_STATUSES = {"SUCCESS", "ROLLED_BACK", "FAILED", "CANCELLED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply a staged OAS-K update.")
    parser.add_argument("--transaction", required=True, type=Path)
    parser.add_argument("--wait-pid", type=int)
    parser.add_argument("--shutdown-timeout", type=float, default=60.0)
    parser.add_argument("--health-timeout", type=float, default=90.0)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--python-executable", type=Path)
    args = parser.parse_args(argv)

    transaction = None
    logger = configure_logger(args.log_path)
    try:
        transaction = load_transaction(args.transaction)
        if args.log_path is None and transaction.get("log_path"):
            logger = configure_logger(transaction["log_path"])
        logger.info("Updater started transaction=%s", transaction["transaction_id"])
        data_root = data_root_from_transaction_path(args.transaction)
        update_status(args.transaction, transaction, "WAITING_FOR_SHUTDOWN")
        if not wait_for_exit(args.wait_pid or transaction.get("source_process_id"), args.shutdown_timeout):
            update_status(args.transaction, transaction, "FAILED", "Old process shutdown timeout.")
            logger.error("Old process timeout.")
            return EXIT_OLD_PROCESS_TIMEOUT

        update_status(args.transaction, transaction, "BACKING_UP_APPLICATION")
        try:
            backup_application(
                application_root=Path(transaction["application_root"]),
                rollback_path=Path(transaction["rollback_path"]),
                data_root=data_root,
                entry_executable=transaction["entry_executable"],
            )
        except Exception as exc:
            update_status(args.transaction, transaction, "FAILED", safe_error(exc))
            logger.exception("Application backup failed.")
            return EXIT_BACKUP_FAILED

        update_status(args.transaction, transaction, "APPLYING")
        try:
            replace_application(
                application_root=Path(transaction["application_root"]),
                staged_application_path=Path(transaction["staged_application_path"]),
                rollback_path=Path(transaction["rollback_path"]),
                data_root=data_root,
                entry_executable=transaction["entry_executable"],
            )
        except Exception as exc:
            logger.exception("Replacement failed; requesting rollback.")
            return rollback(args.transaction, transaction, data_root, safe_error(exc), args.python_executable)

        update_status(args.transaction, transaction, "APPLICATION_REPLACED")
        update_status(args.transaction, transaction, "STARTING_NEW_APPLICATION")
        new_process = launch_application(
            Path(transaction["application_root"]),
            transaction["entry_executable"],
            "--post-update",
            args.transaction,
            args.python_executable,
        )
        if new_process is None:
            return rollback(
                args.transaction,
                transaction,
                data_root,
                "New application launch failed.",
                args.python_executable,
                launch_old=False,
            )
        update_status(
            args.transaction,
            transaction,
            "HEALTHCHECK_PENDING",
            new_process_id=new_process.pid,
        )
        marker = wait_for_health_marker(
            args.transaction,
            transaction["transaction_id"],
            transaction["target_version"],
            args.health_timeout,
        )
        if not marker:
            request_graceful_exit(new_process.pid)
            return rollback(
                args.transaction,
                transaction,
                data_root,
                "Health check failed or timed out.",
                args.python_executable,
            )
        update_status(args.transaction, transaction, "SUCCESS")
        logger.info("Update succeeded.")
        return EXIT_SUCCESS
    except InvalidTransactionError as exc:
        logger.error("Invalid transaction: %s", exc)
        return EXIT_INVALID_TRANSACTION
    except Exception as exc:
        logger.exception("Unexpected updater error.")
        if transaction is not None:
            try:
                update_status(args.transaction, transaction, "FAILED", safe_error(exc))
            except Exception:
                pass
        return EXIT_UNEXPECTED_ERROR


def rollback(
    transaction_path: Path,
    transaction: dict,
    data_root: Path,
    reason: str,
    python_executable: Path | None,
    *,
    launch_old: bool = True,
) -> int:
    logger = configure_logger(transaction.get("log_path"))
    update_status(transaction_path, transaction, "ROLLBACK_REQUESTED", reason)
    update_status(transaction_path, transaction, "ROLLBACK_IN_PROGRESS", reason)
    try:
        restore_previous_application(
            application_root=Path(transaction["application_root"]),
            rollback_path=Path(transaction["rollback_path"]),
            data_root=data_root,
            entry_executable=transaction["entry_executable"],
        )
        if launch_old:
            launch_application(
                Path(transaction["application_root"]),
                transaction["entry_executable"],
                "--post-rollback",
                transaction_path,
                python_executable,
            )
        update_status(transaction_path, transaction, "ROLLED_BACK", reason)
        logger.info("Rollback succeeded.")
        return EXIT_ROLLBACK_SUCCEEDED
    except Exception as exc:
        update_status(transaction_path, transaction, "FAILED", safe_error(exc))
        logger.exception("Rollback failed.")
        return EXIT_ROLLBACK_FAILED


def launch_application(
    application_root: Path,
    entry_executable: str,
    mode: str,
    transaction_path: Path,
    python_executable: Path | None,
) -> subprocess.Popen | None:
    executable = application_root / entry_executable
    if not executable.is_file():
        return None
    if executable.suffix.casefold() == ".py":
        command = [str(python_executable or sys.executable), str(executable), mode]
    else:
        command = [str(executable), mode]
    command.extend(["--update-transaction", str(transaction_path)])
    try:
        return subprocess.Popen(command, cwd=application_root)
    except OSError:
        return None


def wait_for_health_marker(
    transaction_path: Path,
    transaction_id: str,
    target_version: str,
    timeout_seconds: float,
) -> bool:
    marker = transaction_path.parent / "healthcheck_success.json"
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if marker.is_file():
            try:
                payload = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return False
            return (
                payload.get("transaction_id") == transaction_id
                and payload.get("application_version") == target_version
                and payload.get("status") == "SUCCESS"
                and all(bool(value) for value in payload.get("checks", {}).values())
            )
        time.sleep(0.25)
    return False


def load_transaction(path: Path) -> dict:
    if path.name != "transaction.json":
        raise InvalidTransactionError("Transaction filename invalid.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidTransactionError(str(exc)) from exc
    required = {
        "transaction_id",
        "status",
        "target_version",
        "staged_application_path",
        "application_root",
        "rollback_path",
        "entry_executable",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise InvalidTransactionError("Missing fields: " + ", ".join(missing))
    if payload["status"] in TERMINAL_STATUSES:
        raise InvalidTransactionError("Transaction already terminal.")
    return payload


def update_status(
    path: Path,
    transaction: dict,
    status: str,
    last_error: str | None = None,
    *,
    new_process_id: int | None = None,
) -> None:
    transaction["status"] = status
    transaction["updated_at"] = datetime.now().replace(microsecond=0).isoformat()
    if last_error is not None:
        transaction["last_error"] = last_error[:500]
    if new_process_id is not None:
        transaction["new_process_id"] = new_process_id
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(transaction, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)
    configure_logger(transaction.get("log_path")).info("Status -> %s", status)


def data_root_from_transaction_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        transactions = resolved.parents[1]
        update_root = transactions.parent
        if transactions.name != "transactions" or update_root.name != "update":
            raise IndexError
        return update_root.parent
    except IndexError as exc:
        raise InvalidTransactionError("Transaction path layout invalid.") from exc


def safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:500]


class InvalidTransactionError(Exception):
    pass


if __name__ == "__main__":
    raise SystemExit(main())
