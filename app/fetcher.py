"""Odolný asynchronní web fetcher pro stahování zmeny.aspx z Bakalářů."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import AppConfig
from app.database import Storage, compute_sha256
from app.parser_web import parse_web_zmeny_html

PRAGUE_TZ = ZoneInfo("Europe/Prague")
ALLOWED_HOSTS = {
    "klasifikace.skolakrizik.cz",
    "suplovani.skolakrizik.cz",
}
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


def extract_asp_form_inputs(
    html_content: str | bytes,
    button_name: str = "ButtonNext",
) -> tuple[str, dict[str, str]]:
    """Extrahuje action URL a hodnoty formulářových polí ASP.NET pro odeslání tlačítka."""
    if not html_content:
        return "", {}

    soup = BeautifulSoup(html_content, "lxml")
    form = soup.find("form")
    if not isinstance(form, Tag):
        return "", {}

    action = str(form.get("action") or "").strip()
    data: dict[str, str] = {}
    button_found = False
    button_key = ""
    button_val = ""

    def _matches_button(n: str, target: str) -> bool:
        if not target:
            return False
        return n == target or n.endswith(f"${target}") or n.endswith(f":{target}")

    for tag in form.find_all(["input", "select", "textarea"]):
        name = tag.get("name")
        if not name or not isinstance(name, str):
            continue

        tag_name = tag.name.lower()
        tag_type = str(tag.get("type") or "text").lower()

        if tag_name == "input" and tag_type in ("submit", "button", "image"):
            if _matches_button(name, button_name):
                button_found = True
                button_key = name
                button_val = str(tag.get("value") or "")
            continue

        if tag_name == "button":
            if _matches_button(name, button_name):
                button_found = True
                button_key = name
                button_val = str(tag.get("value") or "")
            continue

        if tag_type in ("checkbox", "radio") and not tag.has_attr("checked"):
            continue

        if tag_name == "textarea":
            data[name] = tag.get_text()
            continue

        if tag_name == "select":
            selected = tag.find("option", selected=True) or tag.find("option")
            data[name] = str(selected.get("value", "")) if isinstance(selected, Tag) else ""
            continue

        val = tag.get("value")
        data[name] = str(val) if val is not None else ""

    if button_found and button_key:
        data[button_key] = button_val

    # Vyhledání DevExpress ASPxClientDateEdit inicializace se stateObject a rawValue
    html_str = html_content.decode("utf-8", errors="replace") if isinstance(html_content, bytes) else str(html_content)
    m = re.search(
        r"ASPx\.createControl\(\s*ASPxClientDateEdit\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*,.*?(?:'stateObject'|\"stateObject\")\s*:\s*\{\s*(?:'rawValue'|\"rawValue\")\s*:\s*['\"]?(\d+)['\"]?",
        html_str,
        re.DOTALL,
    )
    if m:
        unique_id = m.group(2) or m.group(1)
        raw_val = m.group(3)
        state_key = f"{unique_id}$State"
        if state_key not in data and raw_val:
            data[state_key] = f'{{"rawValue":"{raw_val}","useMinDateInsteadOfNull":false}}'

    return action, data


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

        fetch_url = url
        parts = urlsplit(url)
        if (parts.hostname or "").lower() == "suplovani.skolakrizik.cz" and parts.path.rstrip("/") == "/next/zmeny.aspx":
            fetch_url = "https://suplovani.skolakrizik.cz/"

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
                resp = None
                for attempt in range(1, max_attempts + 1):
                    try:
                        resp = await client.get(fetch_url, headers=headers)
                        validate_web_url(str(resp.url))
                        if resp.status_code == 404 and "suplovani.skolakrizik.cz" in fetch_url:
                            self.logger.warning(
                                "suplovani.skolakrizik.cz vrátil 404, zkouším https://klasifikace.skolakrizik.cz/next/zmeny.aspx"
                            )
                            fetch_url = "https://klasifikace.skolakrizik.cz/next/zmeny.aspx"
                            resp = await client.get(fetch_url, headers=headers)
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

                if not content:
                    self.logger.warning("Web vrátil prázdný obsah.")
                    return False

                if len(content) > self.config.max_file_size_bytes:
                    self.logger.warning("Odpověď z webu přesáhla limit velikosti (%d B).", len(content))
                    return False

                content_hash = compute_sha256(content)

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
                host = urlsplit(self.config.web_url).hostname or "web"
                last_date = ""
                for day in parse_result.days:
                    day.data_source = "web"
                    day.source_label = f"Web ({host})"
                    day.fetched_at = now_iso
                    saved = self.storage.save_web_day(day, source_hash=content_hash)
                    if saved:
                        saved_any = True
                        if self.on_update:
                            self.on_update({"type": "schedule_update", "date": day.date, "source": "web"})
                    if day.date > last_date:
                        last_date = day.date

                # Dopředné stahování až 3 následujících publikovaných dnů
                max_forward_days: int = 3
                current_html: bytes | str = content
                current_url: str = str(resp.url) if resp is not None else fetch_url

                for forward_step in range(max_forward_days):
                    try:
                        action_rel, form_data = extract_asp_form_inputs(current_html, button_name="ButtonNext")
                        btn_found = any(
                            k == "ButtonNext" or k.endswith("$ButtonNext") or k.endswith(":ButtonNext")
                            for k in form_data
                        )
                        if not btn_found:
                            self.logger.info("Tlačítko ButtonNext chybí v HTML, ukončuji dopředné stahování.")
                            break

                        post_url = urljoin(current_url, action_rel or current_url)
                        validate_web_url(post_url)

                        resp_next = await client.post(post_url, data=form_data, headers=headers)
                        validate_web_url(str(resp_next.url))
                        resp_next.raise_for_status()
                        next_content = resp_next.content

                        if not next_content or len(next_content) > self.config.max_file_size_bytes:
                            self.logger.warning(
                                "Odpověď dopředného dne %d je prázdná nebo přesahuje limit.",
                                forward_step + 1,
                            )
                            break

                        parse_result_next = parse_web_zmeny_html(next_content, known_teachers=merged_codes)
                        if not parse_result_next.days:
                            self.logger.warning("Dopředný den %d neobsahoval žádné dny.", forward_step + 1)
                            break

                        day_next = parse_result_next.days[0]
                        if day_next.date <= last_date:
                            self.logger.info(
                                "Dopředný den nepřekročil datum %s (vráceno %s), konec publikovaných změn.",
                                last_date,
                                day_next.date,
                            )
                            break

                        day_next.data_source = "web"
                        day_next.source_label = f"Web ({host})"
                        day_next.fetched_at = now_iso
                        next_hash = compute_sha256(next_content)
                        saved_next = self.storage.save_web_day(day_next, source_hash=next_hash)
                        if saved_next:
                            saved_any = True
                            if self.on_update:
                                self.on_update({"type": "schedule_update", "date": day_next.date, "source": "web"})

                        last_date = day_next.date
                        current_html = next_content
                        current_url = str(resp_next.url)

                    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                        self.logger.warning(
                            "Síťová chyba při dopředném stahování dne %d: %s (ponecháváme dosavadní dny v DB)",
                            forward_step + 1,
                            exc,
                        )
                        break
                    except Exception as exc:
                        self.logger.warning(
                            "Chyba při zpracování dopředného dne %d: %s",
                            forward_step + 1,
                            exc,
                        )
                        break

                self.last_hash = content_hash
                self.last_status = "SUCCESS"
                self.last_error_message = ""
                self.consecutive_errors = 0
                self.logger.info("Úspěšně zpracován webový export zmeny.aspx (uloženo: %s)", saved_any)
                return True

        except Exception as exc:
            self.last_status = "ERROR"
            self.consecutive_errors += 1
            self.last_error_message = f"Neočekávaná chyba fetcheru: {exc}"
            self.logger.error("Neočekávaná chyba při stahování webu: %s", exc, exc_info=True)
            return False

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
