"""Conciliación SQL y clasificación configurable sobre datos ya validados."""

from pathlib import Path

import pandas as pd

from src.config import AuditConfig
from src.database import connect

LEVELS = ("SIN_DIFERENCIA", "TOLERABLE", "MODERADA", "ALTA", "CRITICA")


def classify(billed: int, received: int, config: AuditConfig) -> str:
    """Límites inclusivos; una base cero con diferencia es siempre crítica."""
    difference = abs(received - billed)
    if difference == 0:
        return "SIN_DIFERENCIA"
    if billed == 0:
        return "CRITICA"
    percentage = difference * 100 / billed
    for threshold, level in zip(
        (config.tolerance_pct, config.moderate_pct, config.high_pct), LEVELS[1:4], strict=True
    ):
        if percentage <= threshold:
            return level
    return "CRITICA"


def load_audit(database: str | Path, config: AuditConfig = AuditConfig()) -> pd.DataFrame:
    with connect(database) as connection:
        frame = pd.read_sql_query("SELECT * FROM reconciliation ORDER BY fecha, transaccion_id", connection)
    frame["porcentaje_diferencia"] = [
        abs(received - billed) * 100 / billed if billed else (0.0 if received == 0 else None)
        for billed, received in zip(frame.cantidad_facturada, frame.cantidad_recibida, strict=True)
    ]
    frame["clasificacion"] = [
        classify(billed, received, config)
        for billed, received in zip(frame.cantidad_facturada, frame.cantidad_recibida, strict=True)
    ]
    frame["es_discrepancia"] = frame.diferencia_cantidad.ne(0)
    frame["requiere_revision"] = frame.clasificacion.isin(("MODERADA", "ALTA", "CRITICA"))
    frame["direccion_diferencia"] = frame.diferencia_cantidad.map(lambda value: "FALTANTE" if value < 0 else "SOBRANTE" if value > 0 else "CONFORME")
    frame["precio_unitario"] = frame.precio_centavos / 100
    frame["valor_estimado_usd"] = frame.valor_estimado_centavos / 100
    return frame


def summarize(frame: pd.DataFrame) -> dict:
    """No suma alertas: una misma transacción puede activar varias reglas."""
    return {
        "transacciones_auditadas": len(frame),
        "discrepancias_detectadas": int(frame.es_discrepancia.sum()),
        "casos_para_revision": int(frame.requiere_revision.sum()),
        "valor_estimado_centavos": int(frame.valor_estimado_centavos.sum()),
        "valor_estimado_usd": int(frame.valor_estimado_centavos.sum()) / 100,
        "impacto_neto_inventario_cajas": int(frame.impacto_inventario.sum()),
    }


def supplier_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.groupby("proveedor", as_index=False).agg(
        transacciones=("transaccion_id", "size"),
        discrepancias=("es_discrepancia", "sum"),
        casos_revision=("requiere_revision", "sum"),
        valor_estimado_centavos=("valor_estimado_centavos", "sum"),
    ).assign(tasa_revision=lambda result: result.casos_revision / result.transacciones)


def daily_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.groupby("fecha", as_index=False).agg(
        transacciones=("transaccion_id", "size"), discrepancias=("es_discrepancia", "sum"),
        valor_estimado_centavos=("valor_estimado_centavos", "sum"),
    )


def inventory_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Variación neta por producto, sin asumir un inventario inicial desconocido."""
    return frame.groupby("producto", as_index=False).agg(
        movimiento_esperado=("movimiento_esperado", "sum"),
        movimiento_observado=("movimiento_observado", "sum"),
        diferencia_inventario=("impacto_inventario", "sum"),
        valor_estimado_centavos=("valor_estimado_centavos", "sum"),
    )
