import json

import pytest

from src.cli import main


def test_cli_generate_import_audit_workflow(tmp_path, capsys):
    sample = tmp_path / "movements.csv"
    database = tmp_path / "cli.db"
    exports = tmp_path / "exports"
    assert main(["generate", "--output", str(sample)]) == 0
    capsys.readouterr()
    assert main(["import", str(sample), "--db", str(database)]) == 0
    imported = json.loads(capsys.readouterr().out)
    assert (imported["accepted"], imported["rejected"]) == (600, 6)
    assert main(["audit", "--db", str(database), "--output", str(exports), "--tolerance", "2"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["transacciones_auditadas"] == 600
    assert summary["configuracion"]["tolerance_pct"] == 2
    assert (exports / "alertas.csv").is_file()


def test_cli_reports_input_error_without_traceback(tmp_path, capsys):
    with pytest.raises(SystemExit) as result:
        main(["import", str(tmp_path / "missing.csv"), "--db", str(tmp_path / "test.db")])
    assert result.value.code == 2
    assert "Error:" in capsys.readouterr().err
