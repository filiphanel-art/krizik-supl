"""Odolný asynchronní web fetcher pro stahování zmeny.aspx z Bakalářů."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from app.config import AppConfig
from app.database import Storage, compute_sha256
from app.parser_web import parse_web_zmeny_html

PRAGUE_TZ = ZoneInfo("Europe/Prague")
ALLOWED_HOSTS = {"klasifikace.skolakrizik.cz"}
BLOCKED_IP_PREFIXES = (
    "127.",
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "192.168.",
    "169.254.",  # Cloud metadata / link-local
    "::1",
    "fc00:",
    "fe80:",
)


class FetchError(Exception):
    """Bezpečnostní nebo konfigurační chyba při stahování webu."""


def validate_web_url(url: str) -> None:
    """Ověří bezpečnost URL (SSRF ochrana, whitelist hostitele a vynucení HTTPS)."""
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise FetchError(f"Nepovolené schéma URL: {parts.scheme!r}. Vyžadováno je výhradně HTTPS.")

    host = (parts.hostname or "").lower()
    if not host or host not in ALLOWED_HOSTS:
        raise FetchError(
            f"Cílový hostitel {host!r} není na whitelistu povolených domén ({ALLOWED_HOSTS})."
        )

    for blocked in BLOCKED_IP_PREFIXES:
        if host.startswith(blocked):
            raise FetchError(f"Cílová adresa {host!r} směřuje do interní nebo privátní sítě (SSRF prevence).")

    if parts.username or parts.password:
        raise FetchError("Uživatelské přihlašovací údaje v URL nejsou povoleny.")

    if parts.port and parts.port != 443:
        raise FetchError(f"Nepovolený port: {parts.port}. Povolen je výhradně port 443.")


class WebFetcher:
    """Asynchronní odolný stahovač změn z webové aplikace Bakalářů."""

    def __init__(
        self,
        config: AppConfig,
        storage: Storage,
        logger: logging.Logger | None = None,
        on_update: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.logger = logger or logging.getLogger("suplovani.fetcher")
        self.on_update = on_update

        self.last_fetch_at: str | None = None
        self.last_status: str = "IDLE"  # IDLE, SUCCESS, ERROR
        self.last_error_message: str = ""
        self.last_hash: str = ""
        self.consecutive_errors: int = 0
        self.is_running: bool = False

    async def fetch_once(self) -> bool:
        """Stáhne a zpracuje aktuální zmeny.aspx z webu Bakalářů bez pádu při chybách."""
        url = self.config.web_url.strip()
        try:
            validate_web_url(url)
        except FetchError as exc:
            self.last_status = "ERROR"
            self.last_error_message = str(exc)
            self.logger.error("Chyba validace URL pro web fetcher: %s", exc)
            return False

        timeout = httpx.Timeout(timeout=10.0, connect=5.0)
        now_iso = datetime.now(PRAGUE_TZ).isoformat(timespec="seconds")
        self.last_fetch_at = now_iso

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "cs,en-US;q=0.7,en;q=0.3",
        }

        content: bytes | None = None
        max_attempts = 3

        async def _validate_request_hook(request: httpx.Request) -> None:
            validate_web_url(str(request.url))

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                event_hooks={"request": [_validate_request_hook]},
            ) as client:
                for attempt in range(1, max_attempts + 1):
                    try:
                        resp = await client.get(url, headers=headers)
                        validate_web_url(str(resp.url))
                        resp.raise_for_status()
                        content = resp.content
                        break

                    except httpx.HTTPStatusError as exc:
                        status_code = exc.response.status_code if exc.response is not None else 0
                        if status_code in (502, 503, 504) and attempt < max_attempts:
                            delay = 1.0 if attempt == 1 else 2.0
                            self.logger.warning(
                                "Bakaláři vrátili HTTP %d, pokus %d/%d. Opakuji za %.1f s...",
                                status_code,
                                attempt,
                                max_attempts,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue

                        self.last_status = "ERROR"
                        self.consecutive_errors += 1
                        if status_code in (502, 503, 504):
                            self.last_error_message = (
                                f"Web Bakalářů je dočasně nedostupný (HTTP {status_code})."
                            )
                            self.logger.warning(
                                "Web Bakalářů vrátil dočasný výpadek HTTP %d: %s (ponecháváme stávající data v DB)",
                                status_code,
                                exc,
                            )
                        else:
                            self.last_error_message = f"HTTP chyba {status_code}: {exc}"
                            self.logger.warning("HTTP chyba při stahování webu Bakalářů: %s", exc)
                        return False

                    except httpx.TimeoutException as exc:
                        if attempt < max_attempts:
                            delay = 1.0 if attempt == 1 else 2.0
                            self.logger.warning(
                                "Timeout při spojení s webem Bakalářů, pokus %d/%d. Opakuji za %.1f s...",
                                attempt,
                                max_attempts,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue

                        self.last_status = "ERROR"
                        self.consecutive_errors += 1
                        self.last_error_message = "Časový limit pro spojení s webem Bakalářů vypršel."
                        self.logger.warning("Timeout při spojení s webem Bakalářů: %s", exc)
                        return False

                    except httpx.RequestError as exc:
                        self.last_status = "ERROR"
                        self.consecutive_errors += 1
                        self.last_error_message = f"Chyba síťového spojení: {exc}"
                        self.logger.warning("Chyba sítě při stahování webu Bakalářů: %s", exc)
                        return False

        except Exception as exc:
            self.last_status = "ERROR"
            self.consecutive_errors += 1
            self.last_error_message = f"Neočekávaná chyba fetcheru: {exc}"
            self.logger.error("Neočekávaná chyba při stahování webu: %s", exc, exc_info=True)
            return False

        if not content:
            self.logger.warning("Web vrátil prázdný obsah.")
            return False

        if len(content) > self.config.max_file_size_bytes:
            self.logger.warning("Odpověď z webu přesáhla limit velikosti (%d B).", len(content))
            return False

        content_hash = compute_sha256(content)
        if content_hash == self.last_hash:
            self.last_status = "SUCCESS"
            self.last_error_message = ""
            self.consecutive_errors = 0
            return True

        # Parsování obsahu
        try:
            merged_codes = dict(self.config.teacher_codes)
            merged_codes.update(self.storage.get_teacher_directory())
            parse_result = parse_web_zmeny_html(content, known_teachers=merged_codes)
        except Exception as exc:
            self.last_status = "ERROR"
            self.consecutive_errors += 1
            self.last_error_message = f"Chyba při parsování HTML z webu: {exc}"
            self.logger.error("Chyba při parsování staženého HTML: %s", exc, exc_info=True)
            return False

        saved_any = False
        for day in parse_result.days:
            day.data_source = "web"
            day.source_label = "Web (klasifikace.skolakrizik.cz)"
            day.fetched_at = now_iso
            saved = self.storage.save_web_day(day, source_hash=content_hash)
            if saved:
                saved_any = True
                if self.on_update:
                    self.on_update({"type": "schedule_update", "date": day.date, "source": "web"})

        self.last_hash = content_hash
        self.last_status = "SUCCESS"
        self.last_error_message = ""
        self.consecutive_errors = 0
        self.logger.info("Úspěšně zpracován webový export zmeny.aspx (uloženo: %s)", saved_any)
        return True

    async def run_loop(self, stop_event: asyncio.Event) -> None:
        """Periodická smyčka pro stahování dat na pozadí."""
        self.is_running = True
        interval = max(60.0, float(self.config.web_poll_interval_seconds))
        self.logger.info("Spuštěn periodický web fetcher s intervalem %.0f s.", interval)

        try:
            while not stop_event.is_set():
                await self.fetch_once()

                # V případě chyb aplikujeme kratší čekání před dalším pokusem (60 s), jinak plný interval
                wait_time = 60.0 if self.last_status == "ERROR" else interval
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=wait_time)
        finally:
            self.is_running = False
            self.logger.info("Periodický web fetcher byl ukončen.")

    def get_status(self) -> dict[str, object]:
        """Vrátí aktuální diagnostický stav fetcheru."""
        return {
            "is_running": self.is_running,
            "web_url": self.config.web_url,
            "poll_interval_seconds": self.config.web_poll_interval_seconds,
            "last_fetch_at": self.last_fetch_at,
            "last_status": self.last_status,
            "last_error_message": self.last_error_message,
            "consecutive_errors": self.consecutive_errors,
        }
