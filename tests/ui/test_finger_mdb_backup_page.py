"""UI contract for the manual Backup MDB monitoring tab."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_backup_mdb_tab_is_manual_background_workflow():
    source = (PROJECT_ROOT / "ui" / "pages" / "finger_monitoring_page.py").read_text(
        encoding="utf-8"
    )

    assert 'self._tab("MONITORING BACKUP MDB")' in source
    assert 'self._button(actions, "Cek Backup", self.check_backup)' in source
    assert "self.services.task_runner.submit(work, on_done=complete)" in source
    assert "self.service.backup_monitoring.scan(" in source
    assert "def refresh_all(self):\n        self.refresh_status(); self.refresh_master(); self.refresh_history()" in source
    assert "self.service.backup_monitoring.export(snapshot, path)" in source
    assert "self.service.backup_monitoring.send_email(snapshot, recipient)" in source
    assert 'self.backup_save_button = self._button(\n            form,' in source
    assert 'self.backup_save_button.grid(row=1, column=4' in source
    assert 'self._button(actions, "Simpan Pengaturan"' not in source
    assert "Nama/pola dipisahkan titik koma" not in source
    assert "Email memakai Recipient Email di Settings" not in source
    assert "self.service.backup_monitoring_settings" in source
    assert "self.service.save_backup_monitoring_settings(" in source
    assert "MDB Wajib Tambahan" not in source
    assert "backup_required_var" not in source
