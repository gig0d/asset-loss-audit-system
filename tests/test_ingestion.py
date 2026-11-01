import csv
import io
import json
import sqlite3

import pytest

from src.database import connect
from src.ingestion import import_csv, load_rejections


def table_counts(database):
    with connect(database) as connection:
        return tuple(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("transactions", "import_batches", "rejections"))


def test_mixed_batch_rejects_duplicate_and_keeps_reason(database, valid_row, make_csv):
    bad = {**valid_row, "transaccion_id": "TX-000002", "cantidad_recibida": "-1"}
    result = import_csv(make_csv([valid_row, valid_row, bad]), database)
    assert (result.accepted, result.rejected) == (1, 2)
    rejected = load_rejections(database)
    assert rejected.code.tolist() == ["ID_DUPLICADO", "CANTIDAD_INVALIDA"]
    assert rejected.row_number.tolist() == [3, 4]
    assert json.loads(rejected.iloc[1].raw_json) == bad
    assert all(rejected.reason.str.len() > 10)


def test_same_content_is_idempotent_even_with_another_filename(database, valid_row, make_csv):
    content = make_csv([valid_row, valid_row])
    first = import_csv(content, database, "first.csv")
    second = import_csv(content, database, "renamed.csv")
    assert second.already_imported
    assert (first.batch_id, first.accepted, first.rejected) == (second.batch_id, second.accepted, second.rejected)
    assert table_counts(database) == (1, 1, 1)


def test_existing_id_in_new_batch_is_rejected(database, valid_row, make_csv):
    import_csv(make_csv([valid_row]), database)
    result = import_csv(make_csv([{**valid_row, "cantidad_recibida": "94"}]), database)
    assert (result.accepted, result.rejected) == (0, 1)
    with connect(database) as connection:
        assert connection.execute("SELECT cantidad_recibida FROM transactions").fetchone()[0] == 95


@pytest.mark.parametrize("content", [b"", b"fecha,transaccion_id\n2026-01-01,TX-000001\n", b"\xff\xfeinvalid"])
def test_invalid_file_has_no_partial_import(database, content):
    with pytest.raises(ValueError):
        import_csv(content, database)
    assert table_counts(database) == (0, 0, 0)


def test_malformed_csv_rolls_back_entire_file(database, valid_row, make_csv):
    content = make_csv([valid_row]) + b'"unterminated'
    with pytest.raises(ValueError, match="CSV inválido"):
        import_csv(content, database)
    assert table_counts(database) == (0, 0, 0)


def test_extra_and_missing_cells_are_row_rejections(database, valid_row, make_csv):
    header, row = make_csv([valid_row]).splitlines()
    content = header + b"\n" + row + b",EXTRA\n" + b"2026-01-01,TX-000002\n"
    result = import_csv(content, database)
    assert (result.accepted, result.rejected) == (0, 2)
    assert set(load_rejections(database).code) == {"DATOS_INCOMPLETOS"}


def test_bom_and_header_order_are_supported(database, valid_row, make_csv):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(reversed(valid_row)), lineterminator="\n")
    writer.writeheader()
    writer.writerow(valid_row)
    assert import_csv(b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8"), database).accepted == 1


def test_sql_constraints_block_negative_quantity(database, valid_row, make_csv):
    import_csv(make_csv([valid_row]), database)
    with connect(database) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE transactions SET cantidad_recibida = -1")


def test_database_failure_rolls_back_batch(database, valid_row, make_csv):
    with connect(database) as connection:
        connection.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON transactions BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        import_csv(make_csv([valid_row]), database)
    assert table_counts(database) == (0, 0, 0)
