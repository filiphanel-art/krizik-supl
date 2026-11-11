"""Generování anonymizovaného statického exportu (HTML + JSON) do složky dist/ (F7)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import re
import shutil
from pathlib import Path

from app.anonymizer import anonymize_schedule_day
from app.config import AppConfig
from app.database import Storage
from app.fetcher import WebFetcher
from app.watcher import FolderWatcher

STATIC_SRC_DIR = Path(__file__).resolve().parent / "static"
logger = logging.getLogger("suplovani.static_export")


def export_static_site(
    config: AppConfig,
    output_dir: Path = Path("./dist"),
    fetch_online: bool = False,
) -> dict[str, int]:
    """Vygeneruje kompletní statickou a 100% anonymizovanou verzi webu do složky dist/."""
    storage = Storage(config.db_path)

    if fetch_online and config.web_enabled:
        try:
            fetcher = WebFetcher(config, storage, logger=logger)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(lambda: asyncio.run(fetcher.fetch_once(fetch_past_week=True))).result()
            else:
                asyncio.run(fetcher.fetch_once(fetch_past_week=True))
        except Exception as exc:
            logger.warning("Online stahování před statickým exportem selhalo: %s", exc)

    # Pokud jsou ve sledované složce soubory, nejprve je načteme (s nulovým čekáním na stabilitu při CLI exportu)
    cli_cfg = config.model_copy(update={"stability_seconds": 0.0})
    watcher = FolderWatcher(config=cli_cfg, storage=storage)
    watcher.scan_once()

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Zkopíruj statické soubory PWA
    for asset in (
        "styles.css",
        "app.js",
        "manifest.json",
        "sw.js",
        "icon.svg",
        "icon-192.png",
        "icon-512.png",
    ):
        src = STATIC_SRC_DIR / asset
        if src.is_file():
            shutil.copy2(src, output_dir / asset)

    # Vytvoř static-mode.js a uprav index.html pro načtení static-mode.js před app.js
    (output_dir / "static-mode.js").write_text(
        "window.__STATIC_EXPORT__ = true;\n", encoding="utf-8"
    )
    index_html = (STATIC_SRC_DIR / "index.html").read_text(encoding="utf-8")
    index_html, injected = re.subn(
        r'<script src="app\.js[^"]*"></script>',
        lambda m: '<script src="static-mode.js"></script>\n  ' + m.group(0),
        index_html,
        count=1,
    )
    if injected != 1:
        raise RuntimeError("Nelze vložit static-mode.js do index.html (nenalezen script app.js).")
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")

    # Načti řadu školního týdne (Po-Pá + Po)
    dates = storage.list_school_week_dates()
    code_map = dict(config.teacher_codes)
    code_map.update(storage.get_teacher_directory())

    exported_days = 0
    total_changes = 0
    all_available = storage.list_available_dates()
    dates_to_export = {d["date"] for d in dates if d.get("has_data")}.union(d["date"] for d in all_available)
    for d_str in sorted(dates_to_export):
        day_obj = storage.get_day(d_str)
        if day_obj is None:
            continue
        anon_day = anonymize_schedule_day(day_obj, code_map)
        day_json_path = data_dir / f"day-{d_str}.json"
        day_json_path.write_text(
            json.dumps(anon_day.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        exported_days += 1
        total_changes += len(anon_day.class_changes)

    status_summary = storage.get_status_summary(stale_threshold_hours=config.stale_threshold_hours)
    last_succ = status_summary.get("last_success")
    anon_last_succ = None
    if isinstance(last_succ, dict):
        anon_last_succ = {
            "exported_at": last_succ.get("exported_at", ""),
            "processed_at": last_succ.get("processed_at", ""),
            "days_count": last_succ.get("days_count", 0),
        }

    index_payload = {
        "dates": dates,
        "status": {
            "has_data": exported_days > 0,
            "has_parse_error": False,
            "last_error_message": "",
            "last_error_at": "",
            "is_stale": status_summary["is_stale"],
            "age_hours": status_summary["age_hours"],
            "stale_threshold_hours": status_summary["stale_threshold_hours"],
            "last_success": anon_last_succ,
            "anonymize": True,
        },
    }
    (data_dir / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"days": exported_days, "changes": total_changes}
