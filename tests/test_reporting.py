import io
import json

import pandas as pd

from src.anomalies import detect_alerts
from src.audit import load_audit
from src.config import AuditConfig
from src.ingestion import import_csv, load_rejections
from src.reporting import csv_bytes, export_reports


def test_csv_is_excel_compatible_and_neutralizes_formula_text():
    source = pd.DataFrame({"texto": ["=1+1", " +SUM(A1)", "@calc", "-formula", "Frío Norte"], "numero": [-5, 2, 3, 4, 5]})
    content = csv_bytes(source)
    assert content.startswith(b"\xef\xbb\xbf")
    parsed = pd.read_csv(io.BytesIO(content))
    assert parsed.texto.tolist() == ["'=1+1", "' +SUM(A1)", "'@calc", "'-formula", "Frío Norte"]
    assert parsed.numero.tolist() == [-5, 2, 3, 4, 5]
    assert source.texto.iloc[0] == "=1+1"


def test_report_export_preserves_exact_values_and_configuration(tmp_path, database, valid_row, make_csv):
    import_csv(make_csv([valid_row, valid_row]), database)
    frame = load_audit(database)
    rejections = load_rejections(database)
    alerts = detect_alerts(frame, rejections=rejections)
    output = tmp_path / "reports"
    summary = export_reports(frame, alerts, rejections, output, AuditConfig())
    assert {path.name for path in output.iterdir()} == {
        "resultados.csv", "alertas.csv", "rechazos.csv", "proveedores.csv", "tendencias.csv", "inventario.csv", "resumen.json",
    }
    assert summary["valor_estimado_centavos"] == 6250
    assert summary["alertas"] == 1
    assert json.loads((output / "resumen.json").read_text(encoding="utf-8")) == summary
    assert pd.read_csv(output / "resultados.csv").valor_estimado_centavos.iloc[0] == 6250
    # La alerta de ID duplicado no incrementa el valor económico.
    assert summary["transacciones_auditadas"] == 1
