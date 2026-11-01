import pytest

from src.audit import classify, inventory_summary, load_audit, summarize
from src.config import AuditConfig
from src.ingestion import import_csv


@pytest.mark.parametrize(("billed", "received", "expected"), [
    (100, 100, "SIN_DIFERENCIA"), (100, 99, "TOLERABLE"),
    (100, 98, "MODERADA"), (100, 95, "MODERADA"),
    (100, 94, "ALTA"), (100, 90, "ALTA"), (100, 89, "CRITICA"),
    (100, 111, "CRITICA"), (0, 0, "SIN_DIFERENCIA"), (0, 1, "CRITICA"),
])
def test_classification_boundaries(billed, received, expected):
    assert classify(billed, received, AuditConfig()) == expected


def test_custom_thresholds_change_classification():
    assert classify(100, 97, AuditConfig(tolerance_pct=3)) == "TOLERABLE"


def test_exact_money_and_inventory_signs(database, valid_row, make_csv):
    rows = [
        {**valid_row, "cantidad_recibida": "97", "precio_unitario": "0.29"},
        {**valid_row, "transaccion_id": "TX-000002", "cantidad_recibida": "98", "precio_unitario": "0.29", "tipo_movimiento": "SALIDA"},
        {**valid_row, "transaccion_id": "TX-000003", "cantidad_recibida": "104", "precio_unitario": "0.29"},
    ]
    import_csv(make_csv(rows), database)
    audit = load_audit(database)
    assert audit.diferencia_cantidad.tolist() == [-3, -2, 4]
    assert audit.diferencia_valor_centavos.tolist() == [-87, -58, 116]
    assert audit.impacto_inventario.tolist() == [-3, 2, 4]
    summary = summarize(audit)
    assert summary["valor_estimado_centavos"] == 261
    assert summary["valor_estimado_usd"] == 2.61
    assert summary["impacto_neto_inventario_cajas"] == 3
    stock = inventory_summary(audit).iloc[0]
    assert (stock.movimiento_esperado, stock.movimiento_observado, stock.diferencia_inventario) == (100, 103, 3)


def test_tolerable_difference_is_counted_but_does_not_require_review(database, valid_row, make_csv):
    import_csv(make_csv([{**valid_row, "cantidad_recibida": "99"}]), database)
    summary = summarize(load_audit(database))
    assert summary["discrepancias_detectadas"] == 1
    assert summary["casos_para_revision"] == 0
    assert summary["valor_estimado_centavos"] == 1250


def test_empty_database_can_be_audited(database):
    audit = load_audit(database)
    assert audit.empty
    assert summarize(audit)["valor_estimado_centavos"] == 0
