"""Verifica que los resultados publicados correspondan al CSV versionado."""

import hashlib
import json

from src.anomalies import detect_alerts
from src.audit import load_audit, summarize
from src.config import ROOT, SAMPLE_CSV
from src.generator import generate_sample
from src.ingestion import import_csv, load_rejections
from src.reporting import csv_bytes


def test_committed_reference_is_reproducible(tmp_path, database):
    expected = json.loads((ROOT / "data/sample/expected_summary.json").read_text(encoding="utf-8"))
    generated = generate_sample(tmp_path / "regenerated.csv", seed=expected["semilla"])
    assert generated.read_bytes() == SAMPLE_CSV.read_bytes()
    assert hashlib.sha256(generated.read_bytes()).hexdigest() == expected["sha256_csv"]
    imported = import_csv(generated, database)
    assert imported.accepted + imported.rejected == expected["filas_csv"]
    frame = load_audit(database)
    assert summarize(frame) == {key: expected[key] for key in summarize(frame)}
    rejections = load_rejections(database)
    alerts = detect_alerts(frame, rejections=rejections)
    assert len(alerts) == expected["alertas"]
    assert alerts.regla.value_counts().to_dict() == expected["alertas_por_regla"]
    assert frame.clasificacion.value_counts().to_dict() == expected["clasificaciones"]
    assert rejections.code.value_counts().to_dict() == expected["motivos_rechazo"]
    example_ids = ["TX-000001", "TX-000011", "TX-000031", "TX-000032", "TX-000051", "TX-000052", "TX-000053"]
    assert csv_bytes(frame.loc[frame.transaccion_id.isin(example_ids)]) == (ROOT / "data/sample/example_results.csv").read_bytes()
