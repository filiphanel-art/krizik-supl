"""Unit testy pro sledování složky a SQLite úložiště (Fáze 3)."""

from __future__ import annotations

import threading
import time
from datetime import date
from pathlib import Path

from app.config import AppConfig
from app.database import Storage
from app.watcher import FolderWatcher, is_safe_child_path

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_gradual_write_overwrite_and_delete(tmp_path: Path) -> None:
    """Test sledování složky: soubor se zapisuje postupně, přepíše se poškozeným/novým a smaže se."""
    watch_dir = tmp_path / "exports"
    watch_dir.mkdir()
    db_path = tmp_path / "db" / "supl.db"

    cfg = AppConfig(
        watch_dir=watch_dir,
        db_path=db_path,
        poll_interval_seconds=1.0,
        stability_seconds=0.3,
        retention_days=30,
    )
    storage = Storage(db_path)
    events: list[dict[str, object]] = []
    watcher = FolderWatcher(cfg, storage, on_update=lambda ev: events.append(ev))

    sample_bytes = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    target_file = watch_dir / "suplprehtrid.html"

    # 1) Postupný zápis souboru po částech (simulace pomalého SMB zápisu)
    half = len(sample_bytes) // 2

    def gradual_writer() -> None:
        with open(target_file, "wb") as f:
            f.write(sample_bytes[:half])
            f.flush()
            time.sleep(0.15)
            f.write(sample_bytes[half:])
            f.flush()

    writer_thread = threading.Thread(target=gradual_writer)
    writer_thread.start()
    time.sleep(0.05)
    # Během zápisu počká watcher na stabilitu a po dopsání zpracuje kompletní soubor
    processed = watcher.scan_once()
    writer_thread.join()

    assert processed == 1
    assert len(storage.list_available_dates()) == 5
    status = storage.get_status_summary()
    assert status["has_data"] is True
    assert status["has_parse_error"] is False
    assert events[-1]["status"] == "SUCCESS"

    # Opakovaný sken beze změny souboru nic nezpracovává
    assert watcher.scan_once() == 0

    # 2) Přepsání souboru poškozeným HTML -> F6: zachová poslední platná data a nahlásí chybu
    time.sleep(0.05)
    target_file.write_bytes(b"<html><body>ROZBITE HTML BEZ TABULKY</body></html>")
    processed_err = watcher.scan_once()
    assert processed_err == 1

    # Poslední platná data (5 dnů) musí zůstat neporušená!
    assert len(storage.list_available_dates()) == 5
    monday = storage.get_day("2026-11-02")
    assert monday is not None
    assert len(monday.class_changes) == 8

    status_after_err = storage.get_status_summary()
    assert status_after_err["has_parse_error"] is True
    assert "Nelze zpracovat nový export" in status_after_err["last_error_message"]

    # 3) Přepsání druhým platným vzorkem (cp1250, 9. 11. 2026) -> přidá nový den a vyčistí chybový stav
    time.sleep(0.05)
    cp1250_bytes = (FIXTURES_DIR / "supl_cp1250_vymena.html").read_bytes()
    target_file.write_bytes(cp1250_bytes)
    assert watcher.scan_once() == 1

    assert len(storage.list_available_dates()) == 6
    status_recovered = storage.get_status_summary()
    assert status_recovered["has_parse_error"] is False

    # 4) Smazání souboru ve sledované složce nesmí smazat uložená data v databázi
    target_file.unlink()
    assert watcher.scan_once() == 0
    assert len(storage.list_available_dates()) == 6


def test_retention_cleanup_deletes_old_days(tmp_path: Path) -> None:
    """Ověří automatické mazání dnů starších než retention_days (F5)."""
    db_path = tmp_path / "supl.db"
    storage = Storage(db_path)

    from app.parser import parse_suplovani_html

    res = parse_suplovani_html((SAMPLES_DIR / "suplprehtrid.html").read_bytes())
    # Uložíme s referenčním datem 6. 11. 2026 a retencí 14 dní -> zůstane všech 5 dnů (2.-6. 11.)
    storage.save_parse_result(
        res, file_hash="h1", file_size=100, retention_days=14, reference_date=date(2026, 11, 6)
    )
    assert len(storage.list_available_dates()) == 5

    # Nyní posuneme referenční datum na 18. 11. 2026 s retencí 14 dní (cutoff = 2026-11-04)
    deleted = storage.cleanup_old_days(retention_days=14, reference_date=date(2026, 11, 18))
    assert deleted == 2  # 2026-11-02 a 2026-11-03 smazány
    remaining = [d["date"] for d in storage.list_available_dates()]
    assert remaining == ["2026-11-04", "2026-11-05", "2026-11-06"]


def test_path_traversal_protection(tmp_path: Path) -> None:
    """Ověří ochranu proti path traversal a symlinkům vedoucím mimo sledovanou složku."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    outside_file = tmp_path / "secret.html"
    outside_file.write_text("secret", encoding="utf-8")

    inside_file = watch_dir / "valid.html"
    inside_file.write_text("valid", encoding="utf-8")

    assert is_safe_child_path(watch_dir, inside_file) is True
    assert is_safe_child_path(watch_dir, outside_file) is False
    assert is_safe_child_path(watch_dir, watch_dir / ".." / "secret.html") is False
