"""Datos exclusivamente ficticios, deterministas y con casos de auditoría forzados."""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from src.validation import CSV_FIELDS

SUPPLIERS = ("Frío Norte (ficticio)", "Huerta Central (ficticio)", "Granos del Valle (ficticio)", "Lácteos Sierra (ficticio)")
PRODUCTS = (("Vegetales congelados", 1850), ("Arroz empacado", 2200), ("Yogur refrigerado", 1250), ("Fruta empacada", 1675))


def generate_sample(output: str | Path, rows: int = 600, seed: int = 42) -> Path:
    """Crea `rows` registros válidos y seis filas inválidas adicionales.

    Usa un RNG local y fechas fijas; no depende del reloj ni del estado global.
    Todos los productos se miden en cajas y todos los precios en USD sintéticos.
    """
    if type(rows) is not int or not 500 <= rows <= 100_000:
        raise ValueError("La muestra debe contener entre 500 y 100000 transacciones válidas.")
    rng = random.Random(seed)
    records = []
    for index in range(rows):
        product, cents = rng.choice(PRODUCTS)
        billed = rng.randint(50, 300)
        change = rng.choices((0, -1, 2, -8, -25, 20), weights=(72, 8, 5, 6, 6, 3))[0]
        records.append({
            "fecha": (date(2026, 1, 1) + timedelta(days=rng.randrange(90))).isoformat(),
            "transaccion_id": f"TX-{index + 1:06d}",
            "proveedor": rng.choice(SUPPLIERS),
            "producto": product,
            "cantidad_facturada": str(billed),
            "cantidad_recibida": str(billed + change),
            "precio_unitario": f"{cents // 100}.{cents % 100:02d}",
            "tipo_movimiento": rng.choice(("ENTRADA", "SALIDA")),
            "estado_inspeccion": rng.choices(("APROBADA", "PENDIENTE", "RECHAZADA"), weights=(85, 12, 3))[0],
        })
    # Recurrencia garantizada, incluso cuando cambian los valores aleatorios.
    for index in range(20):
        records[index].update(
            proveedor=SUPPLIERS[0], cantidad_facturada="100", cantidad_recibida="75",
            fecha=(date(2026, 1, 1) + timedelta(days=index)).isoformat(),
            tipo_movimiento="ENTRADA" if index < 10 else "SALIDA",
        )
    # Mismo contenido comercial con identificadores distintos: se acepta y alerta.
    for original, copies in ((30, (31,)), (40, (41, 42))):
        for index in copies:
            records[index] = {**records[original], "transaccion_id": f"TX-{index + 1:06d}"}
    records[50].update(cantidad_facturada="0", cantidad_recibida="5")
    records[51].update(cantidad_facturada="0", cantidad_recibida="0")
    records[52].update(cantidad_facturada="100", cantidad_recibida="120")
    invalid = [
        dict(records[0]),
        {**records[1], "transaccion_id": "TX-900001", "cantidad_facturada": "-2"},
        {**records[2], "transaccion_id": "ID-INVALIDO"},
        {**records[3], "transaccion_id": "TX-900003", "proveedor": ""},
        {**records[4], "transaccion_id": "TX-900004", "precio_unitario": "NaN"},
        {**records[5], "transaccion_id": "TX-900005", "fecha": "2026-02-30"},
    ]
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records + invalid)
    return path
