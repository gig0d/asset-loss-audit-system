import csv
import io

import pytest

from src.database import initialize
from src.validation import CSV_FIELDS


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "test.db"
    initialize(path)
    return path


@pytest.fixture
def valid_row():
    return {
        "fecha": "2026-01-15", "transaccion_id": "TX-000001", "proveedor": "Proveedor de prueba",
        "producto": "Arroz", "cantidad_facturada": "100", "cantidad_recibida": "95",
        "precio_unitario": "12.50", "tipo_movimiento": "ENTRADA", "estado_inspeccion": "APROBADA",
    }


@pytest.fixture
def make_csv():
    def encode(rows):
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")
    return encode
