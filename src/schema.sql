PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS import_batches (
    batch_id INTEGER PRIMARY KEY,
    content_sha256 TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (accepted_count >= 0),
    rejected_count INTEGER NOT NULL DEFAULT 0 CHECK (rejected_count >= 0)
);

CREATE TABLE IF NOT EXISTS transactions (
    transaccion_id TEXT PRIMARY KEY CHECK (
        length(transaccion_id) = 9 AND transaccion_id GLOB 'TX-[0-9][0-9][0-9][0-9][0-9][0-9]'
    ),
    fecha TEXT NOT NULL,
    proveedor TEXT NOT NULL CHECK (length(trim(proveedor)) BETWEEN 1 AND 120),
    producto TEXT NOT NULL CHECK (length(trim(producto)) BETWEEN 1 AND 120),
    cantidad_facturada INTEGER NOT NULL CHECK (cantidad_facturada BETWEEN 0 AND 1000000),
    cantidad_recibida INTEGER NOT NULL CHECK (cantidad_recibida BETWEEN 0 AND 1000000),
    precio_centavos INTEGER NOT NULL CHECK (precio_centavos BETWEEN 1 AND 100000000),
    tipo_movimiento TEXT NOT NULL CHECK (tipo_movimiento IN ('ENTRADA', 'SALIDA')),
    estado_inspeccion TEXT NOT NULL CHECK (estado_inspeccion IN ('APROBADA', 'PENDIENTE', 'RECHAZADA')),
    batch_id INTEGER NOT NULL REFERENCES import_batches(batch_id)
) STRICT;

CREATE TABLE IF NOT EXISTS rejections (
    rejection_id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES import_batches(batch_id),
    row_number INTEGER NOT NULL,
    transaccion_id TEXT,
    code TEXT NOT NULL,
    reason TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    UNIQUE (batch_id, row_number)
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(fecha);
CREATE INDEX IF NOT EXISTS idx_transactions_supplier ON transactions(proveedor);

CREATE VIEW IF NOT EXISTS reconciliation AS
SELECT *,
    cantidad_recibida - cantidad_facturada AS diferencia_cantidad,
    (cantidad_recibida - cantidad_facturada) * precio_centavos AS diferencia_valor_centavos,
    abs(cantidad_recibida - cantidad_facturada) * precio_centavos AS valor_estimado_centavos,
    CASE WHEN tipo_movimiento = 'ENTRADA' THEN 1 ELSE -1 END
        * (cantidad_recibida - cantidad_facturada) AS impacto_inventario,
    CASE WHEN tipo_movimiento = 'ENTRADA' THEN 1 ELSE -1 END
        * cantidad_facturada AS movimiento_esperado,
    CASE WHEN tipo_movimiento = 'ENTRADA' THEN 1 ELSE -1 END
        * cantidad_recibida AS movimiento_observado
FROM transactions;
