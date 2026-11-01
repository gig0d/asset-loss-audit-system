"""Reglas explicables; sus alertas son indicios y no confirman pérdidas ni robos."""

import json

import pandas as pd

from src.audit import supplier_summary
from src.config import AuditConfig

ALERT_COLUMNS = ("alerta_id", "regla", "severidad", "transaccion_id", "fecha", "proveedor", "producto", "detalle")
BUSINESS_KEY = (
    "fecha", "proveedor", "producto", "cantidad_facturada", "cantidad_recibida", "precio_centavos", "tipo_movimiento",
)


def detect_alerts(frame: pd.DataFrame, config: AuditConfig = AuditConfig(), rejections: pd.DataFrame | None = None) -> pd.DataFrame:
    """Evalúa la selección recibida; la recurrencia usa ese mismo denominador.

    Las repeticiones comerciales ignoran ID e inspección. No prueban duplicidad
    contable: pueden ser operaciones legítimas que requieren revisión documental.
    """
    alerts = []
    for row in frame.loc[frame.clasificacion.isin(("ALTA", "CRITICA"))].itertuples():
        alerts.append({
            "alerta_id": f"EXCESIVA:{row.transaccion_id}", "regla": "DISCREPANCIA_EXCESIVA",
            "severidad": row.clasificacion, "transaccion_id": row.transaccion_id,
            "fecha": row.fecha, "proveedor": row.proveedor, "producto": row.producto,
            "detalle": f"Diferencia de {row.diferencia_cantidad} cajas; clasificación {row.clasificacion}.",
        })
    for row in frame.loc[frame.duplicated(subset=list(BUSINESS_KEY), keep=False)].itertuples():
        alerts.append({
            "alerta_id": f"REPETIDA:{row.transaccion_id}", "regla": "TRANSACCION_REPETIDA",
            "severidad": "ALTA", "transaccion_id": row.transaccion_id,
            "fecha": row.fecha, "proveedor": row.proveedor, "producto": row.producto,
            "detalle": "Contenido comercial idéntico con otro ID; verificar documentos de respaldo.",
        })
    suppliers = supplier_summary(frame)
    recurrent = suppliers.loc[
        suppliers.transacciones.ge(config.supplier_min_transactions)
        & suppliers.casos_revision.ge(config.supplier_min_discrepancies)
        & suppliers.tasa_revision.ge(config.supplier_rate)
    ]
    for row in recurrent.itertuples():
        alerts.append({
            "alerta_id": f"RECURRENTE:{row.proveedor}", "regla": "PROVEEDOR_RECURRENTE", "severidad": "ALTA",
            "transaccion_id": "", "fecha": frame.loc[frame.proveedor.eq(row.proveedor), "fecha"].max(),
            "proveedor": row.proveedor, "producto": "TODOS",
            "detalle": f"{row.casos_revision}/{row.transacciones} operaciones requieren revisión ({row.tasa_revision:.1%}).",
        })
    if rejections is not None:
        for row in rejections.loc[rejections.code.eq("ID_DUPLICADO")].itertuples():
            raw = json.loads(row.raw_json)
            alerts.append({
                "alerta_id": f"RECHAZO:{row.rejection_id}", "regla": "ID_DUPLICADO", "severidad": "ALTA",
                "transaccion_id": row.transaccion_id or "", "fecha": raw.get("fecha", ""),
                "proveedor": raw.get("proveedor", ""), "producto": raw.get("producto", ""),
                "detalle": f"Fila {row.row_number}, lote {row.batch_id}: {row.reason}",
            })
    return pd.DataFrame(alerts, columns=ALERT_COLUMNS).sort_values(["regla", "alerta_id"], ignore_index=True)
