"""Exportaciones UTF-8 con BOM, compatibles con Excel y sin fórmulas ejecutables."""

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.audit import daily_summary, inventory_summary, summarize, supplier_summary
from src.config import AuditConfig


def csv_bytes(frame: pd.DataFrame) -> bytes:
    """Conserva números; neutraliza texto que una hoja de cálculo interpreta como fórmula."""
    safe = frame.copy()
    for column in safe.select_dtypes(include=("object", "string")).columns:
        safe[column] = safe[column].map(
            lambda value: "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
        )
    return safe.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")


def export_reports(frame: pd.DataFrame, alerts: pd.DataFrame, rejections: pd.DataFrame, output: str | Path, config: AuditConfig) -> dict:
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    reports = {
        "resultados.csv": frame, "alertas.csv": alerts, "rechazos.csv": rejections,
        "proveedores.csv": supplier_summary(frame), "tendencias.csv": daily_summary(frame),
        "inventario.csv": inventory_summary(frame),
    }
    for filename, report in reports.items():
        (folder / filename).write_bytes(csv_bytes(report))
    summary = {**summarize(frame), "alertas": len(alerts), "rechazos": len(rejections), "configuracion": asdict(config)}
    (folder / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
