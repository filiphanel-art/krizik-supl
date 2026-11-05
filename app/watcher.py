"""Sledování sdílené složky s exporty (watchdog + záložní polling pro SMB/CIFS)."""

from __future__ import annotations

import fnmatch
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from app.config import AppConfig
from app.database import Storage, compute_sha256
from app.parser import ParseError, parse_suplovani_html


def is_safe_child_path(base_dir: Path, candidate: Path) -> bool:
    """Ověří, že soubor leží uvnitř sledované složky (ochrana proti path traversal a symlinkům mimo složku)."""
    try:
        resolved_base = base_dir.resolve()
        resolved_candidate = candidate.resolve()
        return resolved_candidate.is_relative_to(resolved_base)
    except OSError:
        return False


def wait_for_file_stability(
    file_path: Path,
    stability_seconds: float = 2.0,
    check_interval: float = 0.25,
    max_wait_seconds: float = 30.0,
) -> bool:
    """Čeká, dokud velikost a mtime souboru nejsou stabilní po dobu stability_seconds (F1)."""
    if stability_seconds <= 0:
        return file_path.is_file()

    start_time = time.monotonic()
    stable_since: float | None = None
    last_sig: tuple[int, int] | None = None

    while (time.monotonic() - start_time) <= max_wait_seconds:
        try:
            st = file_path.stat()
        except OSError:
            return False

        if st.st_size == 0:
            stable_since = None
            last_sig = None
            time.sleep(check_interval)
            continue

        sig = (st.st_size, st.st_mtime_ns)
        now = time.monotonic()
        if sig == last_sig:
            if stable_since is not None and (now - stable_since) >= stability_seconds:
                return True
        else:
            last_sig = sig
            stable_since = now

        time.sleep(min(check_interval, stability_seconds / 2.0))

    return False


class _ExportEventHandler(FileSystemEventHandler):
    """Watchdog handler reagující na vytvoření, změnu nebo přesun HTML souboru."""

    def __init__(self, watcher: FolderWatcher) -> None:
        super().__init__()
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher.notify_candidate(Path(str(event.src_path)))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher.notify_candidate(Path(str(event.src_path)))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            dest_path = getattr(event, "dest_path", None)
            if dest_path:
                self._watcher.notify_candidate(Path(str(dest_path)))


class FolderWatcher:
    """Kombinuje událostní sledování (watchdog) se záložním pollingem pro SMB/CIFS."""

    def __init__(
        self,
        config: AppConfig,
        storage: Storage,
        logger: logging.Logger | None = None,
        on_update: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.logger = logger or logging.getLogger("suplovani")
        self.on_update = on_update

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._observer: BaseObserver | None = None
        self._poll_thread: threading.Thread | None = None

        # Evidujeme naposledy zpracovaný otisk (mtime_ns, size, sha256) pro každý soubor
        self._processed_files: dict[str, tuple[int, int, str]] = {}
        self.is_running: bool = False
        self.last_scan_at: float | None = None

    def _matches_pattern(self, path: Path) -> bool:
        name = path.name.lower()
        if name.startswith(".") or name.endswith((".tmp", ".part", ".crdownload")):
            return False
        return fnmatch.fnmatch(name, self.config.file_pattern.lower())

    def notify_candidate(self, path: Path) -> None:
        """Vyvoláno z watchdogu při změně souboru – probudí pracovní vlákno."""
        if self._matches_pattern(path):
            self._wake_event.set()

    def scan_once(self) -> int:
        """Prohledá sledovanou složku a zpracuje nové nebo změněné exporty. Vrátí počet zpracovaných."""
        watch_dir = self.config.watch_dir
        self.last_scan_at = time.time()
        if not watch_dir.exists() or not watch_dir.is_dir():
            return 0

        try:
            candidates = [
                p
                for p in watch_dir.iterdir()
                if p.is_file()
                and self._matches_pattern(p)
                and is_safe_child_path(watch_dir, p)
            ]
        except OSError as exc:
            self.logger.warning(
                "Nelze načíst obsah sledované složky",
                extra={"structured_data": {"error": str(exc)}},
            )
            return 0

        # Seřadíme od nejstaršího po nejnovější podle mtime, aby nejnovější soubor měl poslední slovo
        candidates.sort(key=lambda p: p.stat().st_mtime_ns if p.exists() else 0)

        # Odstranění záznamů o smazaných souborech z paměti
        current_names = {p.name for p in candidates}
        for old_name in list(self._processed_files.keys()):
            if old_name not in current_names:
                del self._processed_files[old_name]

        processed_count = 0
        for file_path in candidates:
            if self.process_file_if_changed(file_path):
                processed_count += 1

        return processed_count

    def process_file_if_changed(self, file_path: Path) -> bool:
        """Zkontroluje stabilitu souboru a zpracuje jej, pokud se změnil."""
        with self._lock:
            if not is_safe_child_path(self.config.watch_dir, file_path):
                self.logger.error(
                    "Zablokován pokus o čtení souboru mimo sledovanou složku",
                    extra={"structured_data": {"file_name": file_path.name}},
                )
                return False

            try:
                st_initial = file_path.stat()
            except OSError:
                return False

            prev = self._processed_files.get(file_path.name)
            if prev and prev[0] == st_initial.st_mtime_ns and prev[1] == st_initial.st_size:
                return False

            # Počkej na dokončení zápisu (stabilní velikost a mtime po dobu stability_seconds)
            if not wait_for_file_stability(
                file_path, stability_seconds=self.config.stability_seconds
            ):
                self.logger.warning(
                    "Soubor není stabilní nebo byl smazán během zápisu",
                    extra={"structured_data": {"file_name": file_path.name}},
                )
                return False

            try:
                st = file_path.stat()
                if st.st_size > self.config.max_file_size_bytes:
                    file_hash = f"oversize-{st.st_size}-{st.st_mtime_ns}"
                    if prev and prev[2] == file_hash:
                        return False
                    msg = (
                        f"Soubor {file_path.name} překračuje maximální povolenou velikost "
                        f"({st.st_size} B > {self.config.max_file_size_bytes} B)."
                    )
                    self.storage.record_failed_import(file_path.name, file_hash, st.st_size, msg)
                    self._processed_files[file_path.name] = (st.st_mtime_ns, st.st_size, file_hash)
                    self.logger.error(
                        "Nelze zpracovat nový export – překročena velikost",
                        extra={"structured_data": {"file_name": file_path.name, "size": st.st_size}},
                    )
                    if self.on_update:
                        self.on_update({"status": "ERROR", "file_name": file_path.name})
                    return True

                raw_bytes = file_path.read_bytes()
            except OSError as exc:
                self.logger.error(
                    "Chyba při čtení exportovaného souboru",
                    extra={"structured_data": {"file_name": file_path.name, "error": str(exc)}},
                )
                return False

            file_hash = compute_sha256(raw_bytes)
            if prev and prev[2] == file_hash:
                self._processed_files[file_path.name] = (st.st_mtime_ns, st.st_size, file_hash)
                return False

            known_teachers = dict(self.config.teacher_codes)
            known_teachers.update(self.storage.get_teacher_directory())

            try:
                result = parse_suplovani_html(
                    raw_bytes,
                    file_name=file_path.name,
                    known_teachers=known_teachers,
                    max_size_bytes=self.config.max_file_size_bytes,
                )
                self.storage.save_parse_result(
                    result,
                    file_hash=file_hash,
                    file_size=len(raw_bytes),
                    retention_days=self.config.retention_days,
                )
                self._processed_files[file_path.name] = (st.st_mtime_ns, st.st_size, file_hash)
                self.logger.info(
                    "Export suplování úspěšně zpracován",
                    extra={
                        "structured_data": {
                            "file_name": file_path.name,
                            "encoding": result.detected_encoding,
                            "days_count": len(result.days),
                            "changes_count": sum(len(d.class_changes) for d in result.days),
                            "unrecognized_count": len(result.unrecognized),
                        }
                    },
                )
                if self.on_update:
                    self.on_update(
                        {
                            "status": "SUCCESS",
                            "file_name": file_path.name,
                            "exported_at": result.exported_at,
                        }
                    )
                return True

            except (ParseError, Exception) as exc:
                err_msg = f"Nelze zpracovat nový export ({file_path.name}): {exc}"
                self.storage.record_failed_import(
                    file_name=file_path.name,
                    file_hash=file_hash,
                    file_size=len(raw_bytes),
                    error_message=err_msg,
                )
                self._processed_files[file_path.name] = (st.st_mtime_ns, st.st_size, file_hash)
                self.logger.error(
                    "Nelze zpracovat nový export – zachována poslední platná data",
                    extra={
                        "structured_data": {
                            "file_name": file_path.name,
                            "error": str(exc),
                        }
                    },
                )
                if self.on_update:
                    self.on_update(
                        {"status": "ERROR", "file_name": file_path.name, "error": err_msg}
                    )
                return True

    def start(self) -> None:
        """Spustí watchdog observer i záložní polling vlákno."""
        if self.is_running:
            return
        self._stop_event.clear()
        self.config.watch_dir.mkdir(parents=True, exist_ok=True)

        # Úvodní synchronní sken při startu
        self.scan_once()

        try:
            observer = Observer()
            observer.schedule(
                _ExportEventHandler(self),
                str(self.config.watch_dir),
                recursive=False,
            )
            observer.daemon = True
            observer.start()
            self._observer = observer
        except Exception as exc:
            self.logger.warning(
                "Watchdog observer nelze spustit, běží záložní polling",
                extra={"structured_data": {"error": str(exc)}},
            )
            self._observer = None

        self._poll_thread = threading.Thread(
            target=self._poll_loop, name="suplovani-watcher-poll", daemon=True
        )
        self._poll_thread.start()
        self.is_running = True

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            self._wake_event.wait(timeout=self.config.poll_interval_seconds)
            self._wake_event.clear()
            if self._stop_event.is_set():
                break
            self.scan_once()

    def stop(self) -> None:
        """Zastaví sledování složky."""
        self._stop_event.set()
        self._wake_event.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=3.0)
            self._observer = None
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=3.0)
            self._poll_thread = None
        self.is_running = False
