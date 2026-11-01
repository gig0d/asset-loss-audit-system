"""Importación atómica por archivo, rechazos trazables e idempotencia por SHA-256."""

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.database import connect, initialize
from src.validation import CSV_FIELDS, ValidationError, validate_row


@dataclass(frozen=True)
class ImportResult:
    batch_id: int
    accepted: int
    rejected: int
    already_imported: bool = False


def import_csv(source: str | Path | bytes, database: str | Path, source_name: str | None = None) -> ImportResult:
    """Un mismo contenido no crea transacciones, lotes ni rechazos adicionales.

    Un archivo distinto puede contener IDs ya existentes: esas filas se rechazan.
    Las cabeceras incorrectas o la codificación inválida abortan el archivo completo.
    """
    content = source if isinstance(source, bytes) else Path(source).read_bytes()
    name = source_name or ("upload.csv" if isinstance(source, bytes) else Path(source).name)
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        if reader.fieldnames is None or len(reader.fieldnames) != len(CSV_FIELDS) or set(reader.fieldnames) != set(CSV_FIELDS):
            raise ValueError("El CSV debe contener exactamente las nueve columnas del contrato.")
        # Analizar antes de escribir garantiza que un CSV truncado no produzca un lote parcial.
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError(f"CSV inválido; use UTF-8 y comas: {exc}") from exc
    if not rows:
        raise ValueError("El CSV debe contener al menos una fila de datos.")
    initialize(database)
    digest = hashlib.sha256(content).hexdigest()
    with connect(database) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT batch_id, accepted_count, rejected_count FROM import_batches WHERE content_sha256 = ?", (digest,)
        ).fetchone()
        if existing:
            return ImportResult(*existing, already_imported=True)
        batch_id = connection.execute(
            "INSERT INTO import_batches (content_sha256, source_name) VALUES (?, ?)", (digest, name)
        ).lastrowid
        accepted = rejected = 0
        for row_number, raw in enumerate(rows, start=2):
            try:
                row = validate_row(raw)
                if connection.execute("SELECT 1 FROM transactions WHERE transaccion_id = ?", (row["transaccion_id"],)).fetchone():
                    raise ValidationError("ID_DUPLICADO", "El identificador ya existe en la base de datos o en este archivo.")
                connection.execute(
                    """INSERT INTO transactions (
                        fecha, transaccion_id, proveedor, producto, cantidad_facturada, cantidad_recibida,
                        precio_centavos, tipo_movimiento, estado_inspeccion, batch_id
                    ) VALUES (
                        :fecha, :transaccion_id, :proveedor, :producto, :cantidad_facturada, :cantidad_recibida,
                        :precio_centavos, :tipo_movimiento, :estado_inspeccion, :batch_id
                    )""", {**row, "batch_id": batch_id},
                )
                accepted += 1
            except ValidationError as exc:
                connection.execute(
                    """INSERT INTO rejections (batch_id, row_number, transaccion_id, code, reason, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (batch_id, row_number, raw.get("transaccion_id"), exc.code, str(exc), json.dumps(raw, ensure_ascii=False)),
                )
                rejected += 1
        connection.execute(
            "UPDATE import_batches SET accepted_count = ?, rejected_count = ? WHERE batch_id = ?", (accepted, rejected, batch_id)
        )
    return ImportResult(batch_id, accepted, rejected)


def load_rejections(database: str | Path) -> pd.DataFrame:
    with connect(database) as connection:
        return pd.read_sql_query(
            """SELECT r.*, b.source_name, b.imported_at FROM rejections r
            JOIN import_batches b USING (batch_id) ORDER BY rejection_id""", connection,
        )
