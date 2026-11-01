import csv
import random

import pytest

from src.anomalies import detect_alerts
from src.audit import load_audit
from src.generator import generate_sample
from src.ingestion import import_csv, load_rejections


def test_fixed_seed_is_reproducible_without_affecting_global_rng(tmp_path):
    state = random.getstate()
    first = generate_sample(tmp_path / "first.csv")
    second = generate_sample(tmp_path / "second.csv")
    third = generate_sample(tmp_path / "third.csv", seed=43)
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() != third.read_bytes()
    assert random.getstate() == state
    with first.open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 606


def test_sample_produces_all_rule_types_and_known_rejections(tmp_path, database):
    sample = generate_sample(tmp_path / "sample.csv")
    result = import_csv(sample, database)
    assert (result.accepted, result.rejected) == (600, 6)
    rejections = load_rejections(database)
    assert set(rejections.code) == {"ID_DUPLICADO", "CANTIDAD_INVALIDA", "ID_INVALIDO", "DATOS_INCOMPLETOS", "PRECIO_INVALIDO", "FECHA_INVALIDA"}
    alerts = detect_alerts(load_audit(database), rejections=rejections)
    assert set(alerts.regla) == {"DISCREPANCIA_EXCESIVA", "TRANSACCION_REPETIDA", "PROVEEDOR_RECURRENTE", "ID_DUPLICADO"}


@pytest.mark.parametrize("rows", [499, 100001])
def test_invalid_sample_size_is_rejected(tmp_path, rows):
    with pytest.raises(ValueError):
        generate_sample(tmp_path / "sample.csv", rows=rows)
