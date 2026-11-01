"""Interfaz reproducible: python -m src.cli --help."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.anomalies import detect_alerts
from src.audit import load_audit
from src.config import DEFAULT_DB, ROOT, SAMPLE_CSV, AuditConfig
from src.database import initialize
from src.generator import generate_sample
from src.ingestion import import_csv, load_rejections
from src.reporting import export_reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AssetGuard: simulación local de auditoría de mercancía.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generar CSV reproducible con casos demostrables.")
    generate.add_argument("--output", type=Path, default=SAMPLE_CSV)
    generate.add_argument("--rows", type=int, default=600)
    generate.add_argument("--seed", type=int, default=42)
    ingest = subparsers.add_parser("import", help="Importar y validar un archivo CSV.")
    ingest.add_argument("csv", type=Path)
    ingest.add_argument("--db", type=Path, default=DEFAULT_DB)
    for name, help_text in (("audit", "Conciliar y exportar informes."), ("demo", "Generar, importar y auditar la demostración.")):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--db", type=Path, default=DEFAULT_DB)
        command.add_argument("--output", type=Path, default=ROOT / "data" / "exports")
        command.add_argument("--tolerance", type=float, default=1.0)
        command.add_argument("--moderate", type=float, default=5.0)
        command.add_argument("--high", type=float, default=10.0)
        command.add_argument("--supplier-min", type=int, default=10)
        command.add_argument("--recurrence-min", type=int, default=3)
        command.add_argument("--recurrence-rate", type=float, default=0.20)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            print(generate_sample(args.output, args.rows, args.seed))
            return 0
        if args.command == "import":
            print(json.dumps(asdict(import_csv(args.csv, args.db)), ensure_ascii=False, indent=2))
            return 0
        config = AuditConfig(args.tolerance, args.moderate, args.high, args.supplier_min, args.recurrence_min, args.recurrence_rate)
        if args.command == "demo":
            generate_sample(SAMPLE_CSV)
            result = import_csv(SAMPLE_CSV, args.db)
            print(json.dumps({"importacion": asdict(result)}, ensure_ascii=False))
        initialize(args.db)
        frame = load_audit(args.db, config)
        rejections = load_rejections(args.db)
        alerts = detect_alerts(frame, config, rejections)
        summary = export_reports(frame, alerts, rejections, args.output, config)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
