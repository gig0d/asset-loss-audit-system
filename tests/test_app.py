from streamlit.testing.v1 import AppTest

import src.config as config
from src.database import connect
from src.generator import generate_sample


def prepare_app(tmp_path, monkeypatch):
    database = tmp_path / "dashboard.db"
    sample = generate_sample(tmp_path / "sample.csv")
    monkeypatch.setattr(config, "DEFAULT_DB", database)
    monkeypatch.setattr(config, "SAMPLE_CSV", sample)
    return AppTest.from_file(str(config.ROOT / "app.py"), default_timeout=30), database


def test_dashboard_demo_filters_and_idempotence(tmp_path, monkeypatch):
    app, database = prepare_app(tmp_path, monkeypatch)
    app.run()
    assert not app.exception
    assert len(app.metric) == 0
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].value == "600"
    assert app.metric[1].value == "188"
    assert app.metric[2].value == "USD 38,586.75"
    app.button[0].click().run()
    assert not app.exception
    with connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM import_batches").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM rejections").fetchone()[0] == 6
    supplier_filter = next(widget for widget in app.multiselect if widget.label == "Proveedor")
    supplier_filter.set_value([]).run()
    assert not app.exception
    assert app.metric[0].value == "0"


def test_dashboard_validates_thresholds(tmp_path, monkeypatch):
    app, _ = prepare_app(tmp_path, monkeypatch)
    app.run()
    tolerance = next(widget for widget in app.number_input if widget.label == "Tolerancia (%)")
    tolerance.set_value(6.0).run()
    assert not app.exception
    assert any("tolerancia < moderada < alta" in message.value for message in app.error)
