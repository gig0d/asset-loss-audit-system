from src.anomalies import detect_alerts
from src.audit import load_audit
from src.config import AuditConfig
from src.ingestion import import_csv, load_rejections


def test_same_business_content_different_ids_is_alerted(database, valid_row, make_csv):
    import_csv(make_csv([
        valid_row, {**valid_row, "transaccion_id": "TX-000002", "estado_inspeccion": "PENDIENTE"},
        {**valid_row, "transaccion_id": "TX-000003", "tipo_movimiento": "SALIDA"},
    ]), database)
    alerts = detect_alerts(load_audit(database))
    assert alerts.regla.tolist() == ["TRANSACCION_REPETIDA"] * 2
    assert set(alerts.transaccion_id) == {"TX-000001", "TX-000002"}
    assert alerts.alerta_id.is_unique


def test_excessive_rule_includes_zero_denominator(database, valid_row, make_csv):
    import_csv(make_csv([
        {**valid_row, "cantidad_recibida": "90"},
        {**valid_row, "transaccion_id": "TX-000002", "cantidad_facturada": "0", "cantidad_recibida": "1"},
        {**valid_row, "transaccion_id": "TX-000003", "cantidad_recibida": "95"},
    ]), database)
    alerts = detect_alerts(load_audit(database))
    assert set(alerts.transaccion_id) == {"TX-000001", "TX-000002"}
    assert set(alerts.severidad) == {"ALTA", "CRITICA"}


def test_supplier_recurrence_uses_count_rate_and_minimum_volume(database, valid_row, make_csv):
    rows = [
        {**valid_row, "transaccion_id": f"TX-{index + 1:06d}", "cantidad_recibida": "95" if index < 3 else "100"}
        for index in range(10)
    ]
    import_csv(make_csv(rows), database)
    frame = load_audit(database)
    config = AuditConfig(supplier_rate=0.3)
    assert (detect_alerts(frame, config).regla == "PROVEEDOR_RECURRENTE").sum() == 1
    assert "PROVEEDOR_RECURRENTE" not in set(detect_alerts(frame, AuditConfig(supplier_rate=0.31)).regla)
    assert "PROVEEDOR_RECURRENTE" not in set(detect_alerts(frame.iloc[:9], config).regla)


def test_rejected_duplicate_id_generates_traceable_alert(database, valid_row, make_csv):
    import_csv(make_csv([valid_row, valid_row]), database)
    alerts = detect_alerts(load_audit(database), rejections=load_rejections(database))
    duplicate = alerts.loc[alerts.regla.eq("ID_DUPLICADO")].iloc[0]
    assert duplicate.transaccion_id == "TX-000001"
    assert "Fila 3, lote 1" in duplicate.detalle


def test_empty_input_has_stable_alert_columns(database):
    alerts = detect_alerts(load_audit(database), rejections=load_rejections(database))
    assert alerts.empty
    assert "alerta_id" in alerts.columns
