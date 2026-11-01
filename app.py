"""Dashboard local de AssetGuard. Ejecutar con `streamlit run app.py`."""

from datetime import date

import streamlit as st

from src.anomalies import detect_alerts
from src.audit import daily_summary, inventory_summary, load_audit, summarize, supplier_summary
from src.config import DEFAULT_DB, SAMPLE_CSV, AuditConfig
from src.database import initialize
from src.generator import generate_sample
from src.ingestion import import_csv, load_rejections
from src.reporting import csv_bytes


def main() -> None:
    st.set_page_config(page_title="AssetGuard · Auditoría local", page_icon="🛡️", layout="wide")
    st.markdown("""
        <style>
        .block-container {padding-top: 2rem; max-width: 1500px;}
        [data-testid="stMetric"] {border: 1px solid #dce5eb; border-radius: 12px; padding: 1rem;}
        [data-testid="stMetricLabel"] {color: #52677d;}
        </style>
        """, unsafe_allow_html=True)
    st.title("AssetGuard")
    st.caption("ASSET LOSS AUDIT SYSTEM · PORTAFOLIO DE INGENIERÍA DE DATOS")
    st.markdown("Auditoría local de entradas y salidas de mercancía: **conciliar, detectar y documentar**.")
    st.info("Simulación con datos ficticios. Las discrepancias son casos por investigar; no representan robos confirmados ni el uso de este sistema por una empresa real.")
    initialize(DEFAULT_DB)

    with st.sidebar:
        st.header("Centro de auditoría")
        st.caption("SQLite local · Sin cuentas externas")
        if st.button("Cargar demostración", type="primary", use_container_width=True):
            if not SAMPLE_CSV.exists():
                generate_sample(SAMPLE_CSV)
            result = import_csv(SAMPLE_CSV, DEFAULT_DB)
            st.success(
                f"Lote ya procesado: {result.accepted} aceptadas, {result.rejected} rechazadas. Sin cambios."
                if result.already_imported else f"Importadas: {result.accepted}. Rechazadas: {result.rejected}."
            )
        with st.expander("Importar otro CSV"):
            st.caption("UTF-8, separado por comas y con las nueve columnas del README. Cantidades en cajas; precios en USD.")
            upload = st.file_uploader("Archivo de movimientos", type=["csv"])
            if st.button("Importar CSV", disabled=upload is None):
                try:
                    result = import_csv(upload.getvalue(), DEFAULT_DB, upload.name)
                    st.success(
                        "Este archivo ya fue procesado; no se añadieron registros."
                        if result.already_imported else f"Aceptadas: {result.accepted}. Rechazadas: {result.rejected}."
                    )
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
        with st.expander("Umbrales y reglas"):
            tolerance = st.number_input("Tolerancia (%)", min_value=0.0, value=1.0, step=0.5)
            moderate = st.number_input("Límite moderado (%)", min_value=0.1, value=5.0, step=0.5)
            high = st.number_input("Límite alto (%)", min_value=0.2, value=10.0, step=0.5)
            supplier_min = st.number_input("Mínimo de operaciones por proveedor", min_value=1, value=10, step=1)
            recurrence_min = st.number_input("Mínimo de casos para recurrencia", min_value=1, value=3, step=1)
            rate = st.number_input("Tasa mínima de recurrencia (%)", min_value=1.0, max_value=100.0, value=20.0, step=1.0)
            st.caption("ALTA o CRÍTICA generan alerta excesiva. Recurrencia: casos MODERADA, ALTA o CRÍTICA / operaciones seleccionadas.")
    try:
        config = AuditConfig(tolerance, moderate, high, supplier_min, recurrence_min, rate / 100)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    audit = load_audit(DEFAULT_DB, config)
    if audit.empty:
        st.subheader("Comienza con una auditoría reproducible")
        st.write("Selecciona **Cargar demostración** en el panel lateral para analizar 600 operaciones ficticias y revisar seis filas rechazadas. También puedes importar un CSV con el contrato documentado.")
        st.stop()
    rejections = load_rejections(DEFAULT_DB)
    with st.sidebar:
        st.divider()
        st.subheader("Selección de movimientos")
        suppliers = sorted(audit.proveedor.unique())
        chosen_suppliers = st.multiselect("Proveedor", suppliers, default=suppliers)
        chosen_movements = st.multiselect("Tipo de movimiento", ["ENTRADA", "SALIDA"], default=["ENTRADA", "SALIDA"])
        chosen_inspections = st.multiselect("Inspección", ["APROBADA", "PENDIENTE", "RECHAZADA"], default=["APROBADA", "PENDIENTE", "RECHAZADA"])
        first = date.fromisoformat(audit.fecha.min())
        last = date.fromisoformat(audit.fecha.max())
        dates = st.date_input("Rango de fechas", value=(first, last), min_value=first, max_value=last, format="YYYY-MM-DD")
    if len(dates) != 2:
        st.info("Completa las dos fechas del rango para consultar los resultados.")
        st.stop()
    selected = audit.loc[
        audit.proveedor.isin(chosen_suppliers)
        & audit.tipo_movimiento.isin(chosen_movements)
        & audit.estado_inspeccion.isin(chosen_inspections)
        & audit.fecha.between(dates[0].isoformat(), dates[1].isoformat())
    ].copy()
    visible_rejections = rejections.loc[rejections.transaccion_id.isin(selected.transaccion_id)]
    alerts = detect_alerts(selected, config, visible_rejections)
    metrics = summarize(selected)
    st.caption(f"Selección: {dates[0].isoformat()} → {dates[1].isoformat()} · {len(chosen_suppliers)} proveedores · Moneda de simulación: USD · Unidad: cajas")
    cards = st.columns(4)
    cards[0].metric("Transacciones auditadas", f"{metrics['transacciones_auditadas']:,}")
    cards[1].metric("Discrepancias detectadas", f"{metrics['discrepancias_detectadas']:,}")
    cards[2].metric("Valor estimado por investigar", f"USD {metrics['valor_estimado_usd']:,.2f}")
    cards[3].metric("Casos para revisión", f"{metrics['casos_para_revision']:,}")
    st.caption("El valor estimado suma diferencias absolutas × precio unitario, incluidas las tolerables. Cada transacción se cuenta una vez; faltantes y sobrantes no se compensan.")
    overview, operations, alert_tab, rejected_tab = st.tabs(["Resumen y tendencias", "Conciliación", "Alertas", "Rechazos de importación"])
    with overview:
        if selected.empty:
            st.info("No hay operaciones para estos filtros.")
        else:
            left, right = st.columns(2)
            daily = daily_summary(selected)
            by_supplier = supplier_summary(selected)
            with left:
                st.subheader("Discrepancias por fecha")
                st.line_chart(daily, x="fecha", y="discrepancias", color="#087e8b")
            with right:
                st.subheader("Valor estimado por proveedor (USD)")
                st.bar_chart(by_supplier.assign(valor_usd=by_supplier.valor_estimado_centavos / 100), x="proveedor", y="valor_usd", color="#087e8b")
            st.subheader("Comparación por proveedor")
            st.dataframe(by_supplier, hide_index=True, use_container_width=True)
            st.subheader("Variación de inventario por producto")
            st.caption("Entrada: +cantidad; salida: −cantidad. Se muestra variación de movimientos, no existencias finales: no se conoce el inventario inicial.")
            st.dataframe(inventory_summary(selected), hide_index=True, use_container_width=True)
    with operations:
        st.subheader("Resultados de conciliación")
        st.caption("Diferencia = recibida − facturada. En salidas, ‘recibida’ representa lo efectivamente recibido por el destino y equivale a lo despachado en esta simulación.")
        st.dataframe(selected, hide_index=True, use_container_width=True)
        st.download_button("Descargar resultados CSV", csv_bytes(selected), "resultados.csv", "text/csv")
    with alert_tab:
        st.subheader(f"Alertas explicables · {len(alerts)}")
        st.caption("Las reglas se evalúan sobre la selección actual. Los intentos de ID duplicado se muestran cuando su ID está seleccionado. Varias alertas pueden corresponder a una operación.")
        left, right = st.columns(2)
        rules = left.multiselect("Regla de alerta", sorted(alerts.regla.unique()), default=sorted(alerts.regla.unique()))
        severities = right.multiselect("Severidad", sorted(alerts.severidad.unique()), default=sorted(alerts.severidad.unique()))
        visible_alerts = alerts.loc[alerts.regla.isin(rules) & alerts.severidad.isin(severities)]
        st.dataframe(visible_alerts, hide_index=True, use_container_width=True)
        st.download_button("Descargar alertas CSV", csv_bytes(visible_alerts), "alertas.csv", "text/csv")
    with rejected_tab:
        st.subheader(f"Historial completo de rechazos · {len(rejections)}")
        st.caption("Incluye todos los lotes, independientemente de los filtros de movimientos. El JSON conserva la fila original y el motivo explica el rechazo. Reimportar el mismo archivo no duplica este historial.")
        st.dataframe(rejections, hide_index=True, use_container_width=True)
        st.download_button("Descargar rechazos CSV", csv_bytes(rejections), "rechazos.csv", "text/csv")
    st.divider()
    st.caption("AssetGuard · Proyecto de portafolio de Giovanny Alvarado Barrantes · Reglas deterministas, resultados verificables y ejecución local.")


if __name__ == "__main__":
    main()
