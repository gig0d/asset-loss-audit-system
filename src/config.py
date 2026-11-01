"""Configuración validada y rutas independientes del directorio de ejecución."""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "assetguard.db"
SAMPLE_CSV = ROOT / "data" / "sample" / "transactions.csv"


@dataclass(frozen=True)
class AuditConfig:
    """Porcentajes expresados en puntos porcentuales, no en fracciones."""

    tolerance_pct: float = 1.0
    moderate_pct: float = 5.0
    high_pct: float = 10.0
    supplier_min_transactions: int = 10
    supplier_min_discrepancies: int = 3
    supplier_rate: float = 0.20

    def __post_init__(self) -> None:
        thresholds = (self.tolerance_pct, self.moderate_pct, self.high_pct)
        if not all(isfinite(value) for value in thresholds):
            raise ValueError("Los umbrales deben ser finitos.")
        if not 0 <= self.tolerance_pct < self.moderate_pct < self.high_pct:
            raise ValueError("Debe cumplirse: 0 <= tolerancia < moderada < alta.")
        counts = (self.supplier_min_transactions, self.supplier_min_discrepancies)
        if any(type(value) is not int or value < 1 for value in counts):
            raise ValueError("Los mínimos de recurrencia deben ser enteros positivos.")
        if not isfinite(self.supplier_rate) or not 0 < self.supplier_rate <= 1:
            raise ValueError("La tasa de recurrencia debe estar entre 0 y 1.")
