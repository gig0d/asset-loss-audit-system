import pytest

from src.config import AuditConfig
from src.validation import ValidationError, validate_row


def test_normalizes_strings_and_exact_price(valid_row):
    normalized = validate_row({**valid_row, "proveedor": "  Proveedor de prueba  ", "precio_unitario": "0.29"})
    assert normalized["proveedor"] == "Proveedor de prueba"
    assert normalized["precio_centavos"] == 29
    assert normalized["cantidad_recibida"] == 95


@pytest.mark.parametrize(("field", "value", "code"), [
    ("transaccion_id", "TX-123", "ID_INVALIDO"),
    ("transaccion_id", "TX-１２３４５６", "ID_INVALIDO"),
    ("transaccion_id", "TX-000001' OR 1=1", "ID_INVALIDO"),
    ("cantidad_facturada", "-1", "CANTIDAD_INVALIDA"),
    ("cantidad_recibida", "-2", "CANTIDAD_INVALIDA"),
    ("cantidad_recibida", "1.5", "CANTIDAD_INVALIDA"),
    ("cantidad_recibida", "NaN", "CANTIDAD_INVALIDA"),
    ("cantidad_recibida", "1000001", "CANTIDAD_INVALIDA"),
    ("precio_unitario", "-1", "PRECIO_INVALIDO"),
    ("precio_unitario", "0", "PRECIO_INVALIDO"),
    ("precio_unitario", "NaN", "PRECIO_INVALIDO"),
    ("precio_unitario", "Infinity", "PRECIO_INVALIDO"),
    ("precio_unitario", "1.001", "PRECIO_INVALIDO"),
    ("precio_unitario", "1000000.01", "PRECIO_INVALIDO"),
    ("fecha", "2026-02-30", "FECHA_INVALIDA"),
    ("fecha", "20260115", "FECHA_INVALIDA"),
    ("fecha", "15/01/2026", "FECHA_INVALIDA"),
    ("proveedor", "", "DATOS_INCOMPLETOS"),
    ("producto", None, "DATOS_INCOMPLETOS"),
    ("proveedor", "a" * 121, "TEXTO_INVALIDO"),
    ("proveedor", "Una\nlínea", "TEXTO_INVALIDO"),
    ("tipo_movimiento", "TRANSFERENCIA", "MOVIMIENTO_INVALIDO"),
    ("estado_inspeccion", "DESCONOCIDO", "INSPECCION_INVALIDA"),
])
def test_rejects_invalid_values(valid_row, field, value, code):
    with pytest.raises(ValidationError) as error:
        validate_row({**valid_row, field: value})
    assert error.value.code == code


@pytest.mark.parametrize("missing", ["fecha", "transaccion_id", "proveedor", "producto", "cantidad_facturada", "cantidad_recibida", "precio_unitario", "tipo_movimiento", "estado_inspeccion"])
def test_all_fields_are_required(valid_row, missing):
    del valid_row[missing]
    with pytest.raises(ValidationError, match="Faltan campos"):
        validate_row(valid_row)


@pytest.mark.parametrize("kwargs", [
    {"tolerance_pct": -1}, {"tolerance_pct": 5}, {"high_pct": 4},
    {"moderate_pct": float("nan")}, {"high_pct": float("inf")},
    {"supplier_rate": 0}, {"supplier_rate": 1.1},
    {"supplier_min_transactions": 0}, {"supplier_min_discrepancies": 1.5},
])
def test_invalid_config_is_rejected(kwargs):
    with pytest.raises(ValueError):
        AuditConfig(**kwargs)
