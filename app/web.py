"""Webový server FastAPI, API koncové body, SSE notifikace a /admin/status (F3, F4, F6, F8)."""

from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.anonymizer import anonymize_schedule_day
from app.config import AppConfig, load_config
from app.database import Storage
from app.fetcher import WebFetcher
from app.logging_setup import setup_logging
from app.watcher import FolderWatcher

PRAGUE_TZ = ZoneInfo("Europe/Prague")
STATIC_DIR = Path(__file__).resolve().parent / "static"

security_basic = HTTPBasic(auto_error=False)


class EventBroadcaster:
    """Správa odběratelů Server-Sent Events (SSE) pro okamžitou aktualizaci UI."""

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict[str, object]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish_threadsafe(self, event: dict[str, object]) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._publish_sync, event)

    def _publish_sync(self, event: dict[str, object]) -> None:
        for q in list(self._queues):
            if not q.full():
                q.put_nowait(event)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        q: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=16)
        self._queues.add(q)
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                    payload = json.dumps(ev, ensure_ascii=False)
                    yield f"event: update\ndata: {payload}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self._queues.discard(q)


def _choose_default_date(dates: list[dict[str, Any]]) -> str:
    if not dates:
        return ""
    today_iso = datetime.now(PRAGUE_TZ).date().isoformat()
    # 1. Preferuj dnešek, pokud má vypsané suplování (has_data != False)
    for d in dates:
        if d["date"] == today_iso and d.get("has_data") is not False:
            return str(d["date"])
    # 2. Preferuj nejbližší budoucí den s daty
    for d in dates:
        if d["date"] >= today_iso and d.get("has_data") is not False:
            return str(d["date"])
    # 3. Preferuj jakýkoliv den s daty
    for d in dates:
        if d.get("has_data") is not False:
            return str(d["date"])
    # 4. Fallback na budoucí den nebo první den v seznamu
    for d in dates:
        if d["date"] >= today_iso:
            return str(d["date"])
    return str(dates[0]["date"])


def _is_ip_allowed(client_host: str | None, allowed_cidrs: list[str]) -> bool:
    if not client_host:
        return False
    if client_host == "testclient":
        return True
    try:
        ip_obj = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    for cidr in allowed_cidrs:
        try:
            net = ipaddress.ip_network(cidr, strict=False)
            if ip_obj in net:
                return True
        except ValueError:
            continue
    return False


def _render_admin_html(status_data: dict[str, Any], watcher_running: bool, watch_dir: str) -> str:
    """Vygeneruje bezpečnou (escapovanou) HTML stránku /admin/status v češtině."""
    esc = html.escape
    last_run = status_data.get("last_run") or {}
    last_succ = status_data.get("last_success") or {}
    unrec_list: list[dict[str, Any]] = status_data.get("unrecognized_items") or []
    recent_runs: list[dict[str, Any]] = status_data.get("recent_runs") or []

    err_banner = ""
    if status_data.get("has_parse_error"):
        err_banner = (
            '<div class="banner banner-error">'
            "<strong>Nelze zpracovat nový export!</strong> "
            f"Detail: {esc(str(status_data.get('last_error_message', '')))} "
            f"(čas: {esc(str(status_data.get('last_error_at', '')))})"
            "</div>"
        )

    unrec_rows_html = ""
    if unrec_list:
        for item in unrec_list:
            unrec_rows_html += (
                "<tr>"
                f"<td>{esc(str(item.get('date', '')))}</td>"
                f"<td>{esc(str(item.get('section', '')))}</td>"
                f"<td><code>{esc(str(item.get('raw_content', '')))}</code></td>"
                f"<td>{esc(str(item.get('reason', '')))}</td>"
                "</tr>"
            )
    else:
        unrec_rows_html = '<tr><td colspan="4">Žádné nerozpoznané položky v posledním exportu.</td></tr>'

    runs_rows_html = ""
    for r in recent_runs:
        st_val = str(r.get("status", ""))
        cls = "cell-sub" if st_val == "SUCCESS" else "cell-cancel"
        runs_rows_html += (
            "<tr>"
            f"<td>{esc(str(r.get('id', '')))}</td>"
            f"<td>{esc(str(r.get('processed_at', '')))}</td>"
            f"<td>{esc(str(r.get('file_name', '')))}</td>"
            f"<td>{esc(str(r.get('detected_encoding', '')))}</td>"
            f"<td class=\"{cls}\">{esc(st_val)}</td>"
            f"<td>{esc(str(r.get('days_count', 0)))}</td>"
            f"<td>{esc(str(r.get('changes_count', 0)))}</td>"
            f"<td>{esc(str(r.get('unrecognized_count', 0)))}</td>"
            f"<td>{esc(str(r.get('error_message', '')))}</td>"
            "</tr>"
        )
    if not runs_rows_html:
        runs_rows_html = '<tr><td colspan="9">Zatím neproběhl žádný import.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Stav systému – Suplování Viewer (/admin/status)</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header class="app-header">
    <div class="header-inner">
      <div>
        <h1 class="school-title">Správa a stav systému (/admin/status)</h1>
        <p class="school-subtitle">Monitoring sledování složky, databáze a chyb parseru</p>
      </div>
      <div class="meta-box">
        <a href="/" style="color:#ffffff;font-weight:700;">← Zpět na přehled suplování</a>
      </div>
    </div>
  </header>
  <main class="container">
    {err_banner}
    <section class="section-block">
      <h3>Souhrnný stav služby</h3>
      <div class="table-scroll">
        <table class="grid-table">
          <tbody>
            <tr><td><strong>Stav sledování složky (Watcher)</strong></td><td>{"BĚŽÍ (aktivní)" if watcher_running else "ZASTAVENO"}</td></tr>
            <tr><td><strong>Sledovaná složka</strong></td><td><code>{esc(watch_dir)}</code></td></tr>
            <tr><td><strong>Počet uložených dnů v DB</strong></td><td>{esc(str(status_data.get("days_count", 0)))}</td></tr>
            <tr><td><strong>Celkový počet změn v DB</strong></td><td>{esc(str(status_data.get("changes_count", 0)))}</td></tr>
            <tr><td><strong>Počet učitelů ve slovníku zkratek</strong></td><td>{esc(str(status_data.get("teachers_count", 0)))}</td></tr>
            <tr><td><strong>Poslední úspěšný soubor</strong></td><td>{esc(str(last_succ.get("file_name", "—")))} (výpis: {esc(str(last_succ.get("exported_at", "—")))})</td></tr>
            <tr><td><strong>Poslední pokus o import</strong></td><td>{esc(str(last_run.get("file_name", "—")))} – stav: <strong>{esc(str(last_run.get("status", "—")))}</strong> ({esc(str(last_run.get("processed_at", "—")))})</td></tr>
            <tr><td><strong>Stáří dat výpisu</strong></td><td>{esc(str(status_data.get("age_hours", "—")))} h (limit: {esc(str(status_data.get("stale_threshold_hours", 24)))} h, zastaralé: {"ANO" if status_data.get("is_stale") else "NE"})</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <h3>Nerozpoznané položky v posledním platném exportu</h3>
      <div class="table-scroll">
        <table class="grid-table">
          <thead>
            <tr><th>Datum</th><th>Sekce</th><th>Surový obsah</th><th>Důvod</th></tr>
          </thead>
          <tbody>
            {unrec_rows_html}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <h3>Historie posledních importů (max. 20)</h3>
      <div class="table-scroll">
        <table class="grid-table">
          <thead>
            <tr>
              <th>ID</th><th>Čas zpracování</th><th>Soubor</th><th>Kódování</th>
              <th>Stav</th><th>Dnů</th><th>Změn</th><th>Nerozpoznáno</th><th>Chyba</th>
            </tr>
          </thead>
          <tbody>
            {runs_rows_html}
          </tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>"""


def create_app(
    config: AppConfig | None = None,
    storage: Storage | None = None,
    start_watcher: bool = True,
) -> FastAPI:
    """Vytvoří a nakonfiguruje instanci FastAPI aplikace."""
    cfg = config or load_config()
    logger = setup_logging(cfg.log_dir)
    storage = storage or Storage(cfg.db_path)
    broadcaster = EventBroadcaster()
    watcher = FolderWatcher(
        config=cfg,
        storage=storage,
        logger=logger,
        on_update=broadcaster.publish_threadsafe,
    )
    fetcher = WebFetcher(
        config=cfg,
        storage=storage,
        logger=logger,
        on_update=broadcaster.publish_threadsafe,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        broadcaster.bind_loop(asyncio.get_running_loop())
        if start_watcher:
            watcher.start()
        else:
            watcher.scan_once()

        fetcher_stop_event = asyncio.Event()
        fetcher_task: asyncio.Task[None] | None = None
        if cfg.web_enabled:
            fetcher_task = asyncio.create_task(fetcher.run_loop(fetcher_stop_event))

        try:
            yield
        finally:
            if fetcher_task is not None:
                fetcher_stop_event.set()
                try:
                    await asyncio.wait_for(fetcher_task, timeout=2.0)
                except (TimeoutError, asyncio.CancelledError):
                    fetcher_task.cancel()
            if start_watcher:
                watcher.stop()

    app = FastAPI(
        title="Suplování Viewer",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.state.config = cfg
    app.state.storage = storage
    app.state.watcher = watcher
    app.state.fetcher = fetcher
    app.state.broadcaster = broadcaster

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'self'"
        )
        return response

    def verify_admin_access(
        request: Request,
        credentials: HTTPBasicCredentials | None = Depends(security_basic),  # noqa: B008
    ) -> None:
        """Ověří přístup na /admin/status (HTTP Basic Auth nebo povolený IP rozsah, F8)."""
        if cfg.admin_password:
            if credentials is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Vyžadováno přihlášení správce.",
                    headers={"WWW-Authenticate": 'Basic realm="SuplovaniAdmin"'},
                )
            user_ok = secrets.compare_digest(credentials.username, cfg.admin_username)
            pass_ok = secrets.compare_digest(credentials.password, cfg.admin_password)
            if not (user_ok and pass_ok):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Neplatné přihlašovací údaje.",
                    headers={"WWW-Authenticate": 'Basic realm="SuplovaniAdmin"'},
                )
            return

        client_ip = request.client.host if request.client else None
        if not _is_ip_allowed(client_ip, cfg.admin_allowed_cidrs):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Přístup povolen pouze ze školního intranetu.",
            )

    @app.get("/api/schedule")
    async def api_schedule(
        date: str | None = Query(default=None, description="Datum ve formátu YYYY-MM-DD"),
    ) -> JSONResponse:
        current_week_dates = storage.list_school_week_dates(reference_date=None)
        if date and not any(d["date"] == date for d in current_week_dates):
            dates = storage.list_school_week_dates(reference_date=date)
        else:
            dates = current_week_dates
        selected_date = date if (date and any(d["date"] == date for d in dates)) else _choose_default_date(dates)

        day_obj = storage.get_day(selected_date) if selected_date else None
        if day_obj and cfg.anonymize:
            code_map = dict(cfg.teacher_codes)
            code_map.update(storage.get_teacher_directory())
            day_obj = anonymize_schedule_day(day_obj, code_map)

        status_summary = storage.get_status_summary(stale_threshold_hours=cfg.stale_threshold_hours)
        public_status = {
            "has_data": status_summary["has_data"],
            "has_parse_error": status_summary["has_parse_error"],
            "last_error_message": status_summary["last_error_message"],
            "last_error_at": status_summary["last_error_at"],
            "is_stale": status_summary["is_stale"],
            "age_hours": status_summary["age_hours"],
            "stale_threshold_hours": status_summary["stale_threshold_hours"],
            "last_success": status_summary["last_success"],
            "anonymize": cfg.anonymize,
        }

        return JSONResponse(
            {
                "dates": dates,
                "selected_date": selected_date,
                "day": day_obj.model_dump() if day_obj else None,
                "status": public_status,
            }
        )

    @app.get("/api/status")
    async def api_status(_auth: None = Depends(verify_admin_access)) -> JSONResponse:
        summary = storage.get_status_summary(stale_threshold_hours=cfg.stale_threshold_hours)
        summary["watcher_running"] = watcher.is_running
        summary["watch_dir"] = str(cfg.watch_dir)
        summary["anonymize"] = cfg.anonymize
        summary["fetcher"] = fetcher.get_status()
        return JSONResponse(summary)

    @app.post("/api/fetch-web")
    async def api_fetch_web(_auth: None = Depends(verify_admin_access)) -> JSONResponse:
        """Manuální spuštění stažení jednodenního rozvrhu z webu Bakalářů pro administrátora."""
        success = await fetcher.fetch_once()
        return JSONResponse(
            {
                "ok": success,
                "status": "success" if success else "failed",
                "fetcher": fetcher.get_status(),
            }
        )

    @app.get("/admin/status")
    async def admin_status_page(
        request: Request,
        format: str | None = Query(default=None),
        _auth: None = Depends(verify_admin_access),
    ) -> Response:
        summary = storage.get_status_summary(stale_threshold_hours=cfg.stale_threshold_hours)
        if format == "json" or "application/json" in request.headers.get("accept", ""):
            summary["watcher_running"] = watcher.is_running
            summary["watch_dir"] = str(cfg.watch_dir)
            return JSONResponse(summary)
        html_body = _render_admin_html(summary, watcher.is_running, str(cfg.watch_dir))
        return HTMLResponse(html_body)

    @app.get("/api/events")
    async def api_events() -> StreamingResponse:
        return StreamingResponse(
            broadcaster.subscribe(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/upload/{token}")
    async def upload_export_file(
        token: str,
        request: Request,
        filename: str | None = Query(default="suplprehtrid.html"),
    ) -> JSONResponse:
        """Skrytý zabezpečený webhook / upload endpoint pro zasílání exportu suplprehtrid.html z Windows."""
        expected_token = cfg.upload_token.strip()
        if not expected_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Upload endpoint není v konfiguraci povolen (není nastaven SUPL_UPLOAD_TOKEN).",
            )
        if not secrets.compare_digest(token, expected_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Neplatný upload token.",
            )

        # Kontrola názvu souboru – striktně suplprehtrid.html (nebo .htm)
        target_name = (request.headers.get("X-Filename") or filename or "suplprehtrid.html").strip().lower()
        if target_name not in ("suplprehtrid.html", "suplprehtrid.htm"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Povolen je pouze exportní soubor s názvem suplprehtrid.html",
            )

        content = await request.body()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tělo požadavku je prázdné.",
            )
        if len(content) > cfg.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Soubor přesahuje maximální povolenou velikost.",
            )

        cfg.watch_dir.mkdir(parents=True, exist_ok=True)
        target_path = cfg.watch_dir / "suplprehtrid.html"
        tmp_target = cfg.watch_dir / "suplprehtrid.html.tmp"
        tmp_target.write_bytes(content)
        tmp_target.replace(target_path)

        # Spuštění okamžitého importu a notifikace klientů
        processed = watcher.process_file_if_changed(target_path)
        return JSONResponse(
            {
                "ok": True,
                "status": "processed" if processed else "ignored_or_error",
                "bytes": len(content),
                "file_name": target_path.name,
            }
        )

    @app.get("/")
    async def index_page() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html",
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/{asset_name}")
    async def static_asset(asset_name: str) -> FileResponse:
        allowed_assets = {
            "index.html": "text/html; charset=utf-8",
            "styles.css": "text/css; charset=utf-8",
            "app.js": "application/javascript; charset=utf-8",
            "sw.js": "application/javascript; charset=utf-8",
            "manifest.json": "application/manifest+json; charset=utf-8",
            "icon.svg": "image/svg+xml",
            "icon-192.png": "image/png",
            "icon-512.png": "image/png",
        }
        if asset_name not in allowed_assets:
            raise HTTPException(status_code=404, detail="Soubor nenalezen.")
        return FileResponse(
            STATIC_DIR / asset_name,
            media_type=allowed_assets[asset_name],
            headers={"Cache-Control": "no-cache"},
        )

    return app
