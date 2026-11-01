"""Contrato CSV estricto. Cantidades en cajas y precios sintéticos en USD."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

CSV_FIELDS = (
    "fecha", "transaccion_id", "proveedor", "producto", "cantidad_facturada",
    "cantidad_recibida", "precio_unitario", "tipo_movimiento", "estado_inspeccion",
)
MOVEMENTS = ("ENTRADA", "SALIDA")
INSPECTIONS = ("APROBADA", "PENDIENTE", "RECHAZADA")
MAX_QUANTITY = 1_000_000
MAX_PRICE = Decimal("1000000.00")


class ValidationError(ValueError):
    """Error de una fila con código estable para exportaciones y alertas."""

    def __init__(self, code: str, reason: str):
        self.code = code
        super().__init__(reason)


def validate_row(raw: dict) -> dict:
    """Normaliza una fila o informa la primera causa de rechazo determinista."""
    if None in raw or any(raw.get(key) is None or not str(raw[key]).strip() for key in CSV_FIELDS):
        raise ValidationError("DATOS_INCOMPLETOS", "Faltan campos o la fila tiene columnas adicionales.")
    row = {key: str(raw[key]).strip() for key in CSV_FIELDS}
    if not re.fullmatch(r"TX-\d{6}", row["transaccion_id"], flags=re.ASCII):
        raise ValidationError("ID_INVALIDO", "El identificador debe cumplir TX-000001 (seis dígitos ASCII).")
    try:
        if date.fromisoformat(row["fecha"]).isoformat() != row["fecha"]:
            raise ValueError
    except ValueError as exc:
        raise ValidationError("FECHA_INVALIDA", "La fecha debe ser válida y usar YYYY-MM-DD.") from exc
    for field in ("proveedor", "producto"):
        if len(row[field]) > 120 or any(ord(char) < 32 for char in row[field]):
            raise ValidationError("TEXTO_INVALIDO", f"{field}: máximo 120 caracteres y sin controles.")
    for field in ("cantidad_facturada", "cantidad_recibida"):
        if not re.fullmatch(r"[0-9]+", row[field]) or len(row[field]) > 7:
            raise ValidationError("CANTIDAD_INVALIDA", f"{field}: se requiere un entero no negativo.")
        row[field] = int(row[field])
        if row[field] > MAX_QUANTITY:
            raise ValidationError("CANTIDAD_INVALIDA", f"{field}: máximo {MAX_QUANTITY} cajas.")
    try:
        price = Decimal(row["precio_unitario"])
        if not price.is_finite() or not 0 < price <= MAX_PRICE or price.as_tuple().exponent < -2:
            raise ValueError
        row["precio_centavos"] = int(price * 100)
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValidationError("PRECIO_INVALIDO", "Precio positivo y finito con hasta dos decimales.") from exc
    if row["tipo_movimiento"] not in MOVEMENTS:
        raise ValidationError("MOVIMIENTO_INVALIDO", "El movimiento debe ser ENTRADA o SALIDA.")
    if row["estado_inspeccion"] not in INSPECTIONS:
        raise ValidationError("INSPECCION_INVALIDA", "Estado permitido: APROBADA, PENDIENTE o RECHAZADA.")
    del row["precio_unitario"]
    return row
