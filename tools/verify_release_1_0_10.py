"""Isolated verification of the actual release ZIP, updater, and frozen app."""
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
import zipfile
from types import CodeType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psutil
import win32con
import win32gui
import win32process
from PyInstaller.archive.readers import CArchiveReader
from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.database_validator import DatabaseValidator
from shared.database.schema_manager import SchemaManager
from shared.storage.path_resolver import resolve_storage_layout
from shared.update import ApplicationUpdateService
from shared.update.transaction_store import UpdateTransactionStore
from ui.constants import APP_TITLE
from outlook.downloader import OutlookComClient


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def dump(path):
    with SQLiteConnectionFactory().connect(path, read_only=True) as connection:
        return tuple(connection.iterdump())


def code_constants(code):
    for value in code.co_consts:
        if isinstance(value, CodeType):
            yield from code_constants(value)
        elif isinstance(value, str):
            yield value


def main():
    release = ROOT / 'dist/release/v1.0.10'
    package = release / 'OAS-K_Update_v1.0.10.zip'
    exe = release / 'application/OAS-K.exe'
    smoke = Path(tempfile.mkdtemp(prefix='release_1_0_10_', dir=ROOT / '.codex_tmp')).resolve()
    assert smoke.is_relative_to((ROOT / '.codex_tmp').resolve())
    app_root = smoke / 'application'
    app_root.mkdir()
    # Use the archived 1.0.9 executable only in the isolated application root.
    old_exe = ROOT / 'dist/release/v1.0.9/application/OAS-K.exe'
    old_bytes = old_exe.read_bytes()
    with zipfile.ZipFile(ROOT / 'dist/release/v1.0.9/OAS-K_Update_v1.0.9.zip') as old_zip:
        old_manifest = json.loads(old_zip.read('manifest.json'))
        assert old_manifest['version'] == '1.0.9'
        assert old_manifest['database_schema_to'] == 4
        assert old_zip.read('application/OAS-K.exe') == old_bytes
    (app_root / 'OAS-K.exe').write_bytes(old_bytes)
    layout = resolve_storage_layout(smoke / 'DataRoot')
    SchemaManager().initialize_database(layout.database_path, '1.0.9', create_parent=True)
    with SQLiteConnectionFactory().connect(layout.database_path) as connection:
        connection.execute(
            'INSERT INTO global_settings '
            '(global_settings_id, output_root, updated_at, updated_by) '
            'VALUES (1, ?, CURRENT_TIMESTAMP, ?)',
            (str(layout.output_root), 'Production schema4 / app1.0.9 fixture'),
        )
        connection.execute(
            "INSERT INTO outlook_settings (outlook_settings_id, mailbox_smtp, "
            "payroll_period, updated_at) VALUES (1, 'fixture@example.com', '09-2026', CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO outlook_sender_master (workflow, sender_email, created_at, updated_at) "
            "VALUES ('HO', 'fixture.sender@example.com', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.commit()
    baseline = dump(layout.database_path)
    for relative in ('output/existing.txt', 'recorder_profiles/hris/existing.json'):
        target = layout.data_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('preserve existing user data', encoding='utf-8')
    preserved = {str(p.relative_to(layout.data_root)): sha(p)
                 for p in layout.data_root.rglob('*') if p.is_file()}

    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        assert set(names) == {'application/', 'manifest.json', 'release_notes.txt', 'checksums.sha256',
                              'application/OAS-K.exe'}, names
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['version'] == '1.0.10'
        assert manifest['minimum_current_version'] == '1.0.9'
        assert (manifest['database_schema_from'], manifest['database_schema_to'],
                manifest['migration_required']) == (4, 4, False)
        assert hashlib.sha256(archive.read('application/OAS-K.exe')).hexdigest() == sha(exe)
    assert package.with_suffix('.zip.sha256').read_text().split()[0] == sha(package)
    bundled = CArchiveReader(str(exe))
    frozen_downloader = bundled.open_embedded_archive('PYZ.pyz').extract('outlook.downloader')
    constants = set(code_constants(frozen_downloader))
    assert OutlookComClient.RECALL_FILTER in constants
    assert {'FILTER_RECALL_ITEMS', 'SKIPPED_RECALL', 'RECALL_ITEMS_EXCLUDED'} <= constants
    embedded_updater = next(n for n in bundled.toc if n.replace('\\', '/') == 'updater/OAS-K-Updater.exe')
    updater = smoke / 'OAS-K-Updater.exe'
    updater.write_bytes(bundled.extract(embedded_updater))
    assert sha(updater) == sha(ROOT / 'dist/updater/OAS-K-Updater.exe')
    forbidden = [n for n in bundled.toc
                 if Path(n).suffix.casefold() in {'.db', '.mdb', '.sqlite', '.sqlite3', '.log'}
                 or any(part.casefold() in {'recorder_profiles', 'backup', 'backups', 'output', 'logs'}
                        for part in n.replace('\\', '/').split('/'))]
    assert not forbidden, forbidden
    assert not any('Templatexx' in n for n in bundled.toc)

    service = ApplicationUpdateService()
    validation = service.validate_package(package, current_version='1.0.9', active_schema_version=4)
    assert validation.valid, validation.errors
    legacy_source = subprocess.check_output(
        ['git', 'show', '3ec6d45:shared/update/package_validator.py'], cwd=ROOT,
    ).decode('utf-8')
    legacy_namespace = {'__name__': 'legacy_package_validator'}
    exec(compile(legacy_source, '<legacy repository validator>', 'exec'), legacy_namespace)
    legacy_validation = legacy_namespace['UpdatePackageValidator'](active_schema_version=4).validate(
        package, current_version='1.0.9',
    )
    assert legacy_validation.valid, legacy_validation.errors
    prepared = service.prepare_update(package, current_version='1.0.9',
                                      data_root=layout.data_root, application_root=app_root)
    assert DatabaseValidator(expected_version=4).validate(prepared.backup_path).is_valid
    assert dump(prepared.backup_path) == baseline
    assert dump(layout.database_path) == baseline
    store = UpdateTransactionStore(layout.data_root)
    transaction = store.load(prepared.transaction_path)
    store.save(replace(transaction, source_process_id=None))
    ui_observed = False
    launched = None
    try:
        with (smoke / 'updater_console.txt').open('w', encoding='utf-8') as log:
            result = subprocess.run(
                [str(updater), '--transaction', str(prepared.transaction_path),
                 '--shutdown-timeout', '5', '--health-timeout', '120'],
                cwd=smoke, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=150,
            )
        state = json.loads(prepared.transaction_path.read_text())
        if state.get('new_process_id'):
            launched = psutil.Process(state['new_process_id'])
        assert result.returncode == 0, (result.returncode, state)
        assert state['status'] == 'SUCCESS', state
        health = json.loads((prepared.transaction_path.parent / 'healthcheck_success.json').read_text())
        assert health['application_version'] == '1.0.10'
        assert health['database_schema_version'] == 4
        assert all(health['checks'].values()), health
        # Wait for the actual frozen Tk shell, then close only this smoke app.
        deadline = time.monotonic() + 30
        windows = []
        while time.monotonic() < deadline and not windows:
            own_pids = {launched.pid} | {p.pid for p in launched.children(recursive=True)}
            def collect(hwnd, unused):
                if (win32process.GetWindowThreadProcessId(hwnd)[1] in own_pids
                        and win32gui.GetClassName(hwnd) == 'TkTopLevel'
                        and win32gui.GetWindowText(hwnd) == APP_TITLE):
                    windows.append(hwnd)
            win32gui.EnumWindows(collect, None)
            if not windows:
                time.sleep(0.25)
        assert windows, 'Frozen application did not create the OAS-K Tk shell'
        ui_observed = True
        for hwnd in windows:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        launched.wait(timeout=20)
        assert sha(app_root / 'OAS-K.exe') == sha(exe)
        assert (Path(state['rollback_path']) / 'application/OAS-K.exe').read_bytes() == old_bytes
        assert dump(layout.database_path) == baseline
        assert DatabaseValidator(expected_version=4).validate(layout.database_path).is_valid
        assert all(sha(layout.data_root / rel) == digest for rel, digest in preserved.items())
        report = dict(
            status='PASS', version='1.0.10', minimum_current_version='1.0.9',
            database_schema_from=4, database_schema_to=4, migration_required=False,
            package_sha256=sha(package), executable_sha256=sha(exe),
            updater_sha256=sha(updater), zip_entries=names,
            frozen_recall_filter_verified=True,
            valid_pre_update_backup=True, entire_database_preserved=True,
            existing_output_and_profiles_preserved=True, frozen_updater_exit_code=result.returncode,
            frozen_healthcheck=health, frozen_ui_shell_observed=ui_observed,
            legacy_validator_commit='3ec6d45', legacy_validator_accepted=True,
            old_application_fixture='Archived 1.0.9 EXE with synthetic schema4 database',
            old_executable_sha256=sha(old_exe),
            smoke_directory=str(smoke),
        )
        (release / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
    finally:
        if launched is not None:
            try:
                processes = launched.children(recursive=True) + [launched]
                for process in processes:
                    if process.is_running():
                        process.terminate()
            except psutil.NoSuchProcess:
                pass


if __name__ == '__main__':
    main()
