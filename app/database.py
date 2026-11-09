"""SQLite úložiště pro Suplování Viewer."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date as dt_date
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.models import (
    AbsentClass,
    AbsentTeacher,
    AbsentTeacherHour,
    ChangeType,
    ClassChange,
    ClassSupervision,
    ClosedRoom,
    ParseResult,
    ScheduleDay,
    UnrecognizedItem,
)
from app.parser import build_derived_teachers

PRAGUE_TZ = ZoneInfo("Europe/Prague")
CZECH_DAY_NAMES = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"]


def compute_school_week_dates(
    reference_date: dt_date | datetime | str | None = None,
    stored_days: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Vypočítá 6denní školní okno s offsety [0, 1, 2, 3, 4, 7] (Po, Út, St, Čt, Pá a Po příštího týdne).
    Pro víkendový den (sobota, neděle) vezme následující pondělí.
    Každý den obsahuje pole has_data: bool.
    """
    if reference_date is None:
        today = datetime.now(PRAGUE_TZ).date()
        stored_date_strs: list[str] = []
        if stored_days:
            if isinstance(stored_days, list):
                for item in stored_days:
                    if isinstance(item, dict) and "date" in item:
                        stored_date_strs.append(str(item["date"]))
                    elif hasattr(item, "date"):
                        stored_date_strs.append(str(item.date))
                    elif isinstance(item, str):
                        stored_date_strs.append(item)
            elif isinstance(stored_days, dict):
                stored_date_strs = [str(k) for k in stored_days]

        if stored_date_strs and not any(d >= today.isoformat() for d in stored_date_strs):
            ref_date = datetime.fromisoformat(max(stored_date_strs)).date()
        else:
            ref_date = today
    elif isinstance(reference_date, str):
        ref_date = datetime.fromisoformat(reference_date).date()
    elif isinstance(reference_date, datetime):
        ref_date = reference_date.date()
    elif isinstance(reference_date, dt_date):
        ref_date = reference_date
    else:
        ref_date = datetime.now(PRAGUE_TZ).date()

    # Pro víkend (sobota=5, neděle=6) vezmeme následující pondělí
    weekday = ref_date.weekday()
    if weekday == 5:
        monday = ref_date + timedelta(days=2)
    elif weekday == 6:
        monday = ref_date + timedelta(days=1)
    else:
        monday = ref_date - timedelta(days=weekday)

    # Vytvoření mapy existujících uložených dnů
    stored_map: dict[str, dict[str, Any]] = {}
    if stored_days:
        if isinstance(stored_days, list):
            for item in stored_days:
                if isinstance(item, dict) and "date" in item:
                    stored_map[str(item["date"])] = item
                elif hasattr(item, "date"):
                    stored_map[str(item.date)] = item.model_dump() if hasattr(item, "model_dump") else dict(item)
                elif isinstance(item, str):
                    stored_map[item] = {"date": item}
        elif isinstance(stored_days, dict):
            for k, v in stored_days.items():
                if isinstance(v, dict):
                    stored_map[str(k)] = v
                else:
                    stored_map[str(k)] = {"date": str(k)}

    offsets = [0, 1, 2, 3, 4, 7]
    result: list[dict[str, Any]] = []
    for off in offsets:
        cur_date = monday + timedelta(days=off)
        iso_str = cur_date.isoformat()
        day_name = CZECH_DAY_NAMES[cur_date.weekday()]

        if iso_str in stored_map:
            entry = dict(stored_map[iso_str])
            entry["date"] = iso_str
            if not entry.get("day_name"):
                entry["day_name"] = day_name
            entry["has_data"] = True
        else:
            entry = {
                "date": iso_str,
                "day_name": day_name,
                "week_label": "",
                "exported_at": "",
                "exported_at_display": "",
                "updated_at": "",
                "data_source": "",
                "source_label": "",
                "fetched_at": "",
                "has_data": False,
            }
        result.append(entry)

    return result


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS import_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    detected_encoding TEXT NOT NULL DEFAULT '',
    exported_at TEXT NOT NULL DEFAULT '',
    processed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT NOT NULL DEFAULT '',
    days_count INTEGER NOT NULL DEFAULT 0,
    changes_count INTEGER NOT NULL DEFAULT 0,
    unrecognized_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS schedule_days (
    date TEXT PRIMARY KEY,
    day_name TEXT NOT NULL,
    week_label TEXT NOT NULL DEFAULT '',
    school_name TEXT NOT NULL DEFAULT '',
    exported_at TEXT NOT NULL DEFAULT '',
    exported_at_display TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    source_import_id INTEGER,
    data_source TEXT NOT NULL DEFAULT 'file',
    source_label TEXT NOT NULL DEFAULT 'Soubor (Bakaláři export)',
    fetched_at TEXT NOT NULL DEFAULT '',
    source_hash TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (source_import_id) REFERENCES import_runs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS class_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    class_name TEXT NOT NULL,
    hour_from INTEGER NOT NULL,
    hour_to INTEGER NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    group_name TEXT NOT NULL DEFAULT '',
    room TEXT NOT NULL DEFAULT '',
    room_changed INTEGER NOT NULL DEFAULT 0,
    change_type TEXT NOT NULL,
    change_type_raw TEXT NOT NULL DEFAULT '',
    sub_teacher TEXT NOT NULL DEFAULT '',
    sub_teacher_changed INTEGER NOT NULL DEFAULT 0,
    orig_teacher_code TEXT NOT NULL DEFAULT '',
    orig_teacher_resolved TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    paired_hour INTEGER,
    paired_change_id INTEGER,
    raw_row_text TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (date) REFERENCES schedule_days(date) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS absent_classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    class_name TEXT NOT NULL,
    hours_json TEXT NOT NULL,
    FOREIGN KEY (date) REFERENCES schedule_days(date) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS absent_teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    teacher_full_name TEXT NOT NULL,
    teacher_normalized_name TEXT NOT NULL,
    teacher_code TEXT NOT NULL DEFAULT '',
    hours_json TEXT NOT NULL,
    FOREIGN KEY (date) REFERENCES schedule_days(date) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS closed_rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    room_name TEXT NOT NULL,
    hours_json TEXT NOT NULL,
    FOREIGN KEY (date) REFERENCES schedule_days(date) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS class_supervisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    class_name TEXT NOT NULL,
    hour_from INTEGER NOT NULL,
    hour_to INTEGER NOT NULL,
    teachers_text TEXT NOT NULL,
    raw_text TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (date) REFERENCES schedule_days(date) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teacher_directory (
    code TEXT PRIMARY KEY,
    normalized_name TEXT NOT NULL,
    full_name_with_titles TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unrecognized_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER,
    date TEXT NOT NULL DEFAULT '',
    section TEXT NOT NULL DEFAULT '',
    raw_content TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (import_id) REFERENCES import_runs(id) ON DELETE CASCADE
);
"""


def compute_sha256(data: bytes) -> str:
    """Spočítá SHA-256 otisk souboru."""
    return hashlib.sha256(data).hexdigest()


class Storage:
    """Správa SQLite databáze pro suplování."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(schedule_days)").fetchall()}
            if "data_source" not in cols:
                conn.execute("ALTER TABLE schedule_days ADD COLUMN data_source TEXT NOT NULL DEFAULT 'file'")
            if "source_label" not in cols:
                conn.execute(
                    "ALTER TABLE schedule_days ADD COLUMN source_label TEXT NOT NULL DEFAULT 'Soubor (Bakaláři export)'"
                )
            if "fetched_at" not in cols:
                conn.execute("ALTER TABLE schedule_days ADD COLUMN fetched_at TEXT NOT NULL DEFAULT ''")
            if "source_hash" not in cols:
                conn.execute("ALTER TABLE schedule_days ADD COLUMN source_hash TEXT NOT NULL DEFAULT ''")

    def get_teacher_directory(self) -> dict[str, str]:
        """Vrátí uložený slovník zkratek učitelů (code -> 'Příjmení Jméno')."""
        with self._connect() as conn:
            rows = conn.execute("SELECT code, normalized_name FROM teacher_directory").fetchall()
            return {str(r["code"]): str(r["normalized_name"]) for r in rows}

    def get_last_successful_hash(self) -> str | None:
        """Vrátí SHA-256 posledního úspěšně naimportovaného souboru."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT file_hash FROM import_runs WHERE status = 'SUCCESS' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return str(row["file_hash"]) if row else None

    def save_parse_result(
        self,
        result: ParseResult,
        file_hash: str,
        file_size: int,
        retention_days: int = 14,
        reference_date: dt_date | None = None,
    ) -> int:
        """Uloží zparsovaný výsledek v jedné atomické transakci a promazává starou historii."""
        now_iso = datetime.now(PRAGUE_TZ).isoformat(timespec="seconds")
        total_changes = sum(len(d.class_changes) for d in result.days)
        total_unrec = len(result.unrecognized)

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO import_runs (
                    file_name, file_hash, file_size, detected_encoding,
                    exported_at, processed_at, status, error_message,
                    days_count, changes_count, unrecognized_count
                ) VALUES (?, ?, ?, ?, ?, ?, 'SUCCESS', '', ?, ?, ?)
                """,
                (
                    result.file_name,
                    file_hash,
                    file_size,
                    result.detected_encoding,
                    result.exported_at,
                    now_iso,
                    len(result.days),
                    total_changes,
                    total_unrec,
                ),
            )
            import_id = int(cur.lastrowid or 0)

            # Aktualizace slovníku učitelů
            for code, norm_name in result.teacher_directory.items():
                full_titles = result.teacher_titles.get(norm_name, "")
                cur.execute(
                    """
                    INSERT INTO teacher_directory (code, normalized_name, full_name_with_titles, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(code) DO UPDATE SET
                        normalized_name = excluded.normalized_name,
                        full_name_with_titles = CASE
                            WHEN excluded.full_name_with_titles != '' THEN excluded.full_name_with_titles
                            ELSE teacher_directory.full_name_with_titles
                        END,
                        updated_at = excluded.updated_at
                    """,
                    (code, norm_name, full_titles, now_iso),
                )

            # Uložení jednotlivých dnů (přepíše předchozí verzi téhož dne)
            for day in result.days:
                existing = cur.execute(
                    "SELECT data_source, exported_at, fetched_at FROM schedule_days WHERE date = ?",
                    (day.date,),
                ).fetchone()
                if (day.data_source != "web") and existing and str(existing["data_source"] or "") == "web":
                    web_ts = str(existing["fetched_at"] or existing["exported_at"] or "")
                    file_ts = str(day.exported_at or result.exported_at or "")
                    if not (file_ts and web_ts and file_ts > web_ts):
                        continue

                cur.execute("DELETE FROM schedule_days WHERE date = ?", (day.date,))
                cur.execute(
                    """
                    INSERT INTO schedule_days (
                        date, day_name, week_label, school_name,
                        exported_at, exported_at_display, updated_at, source_import_id,
                        data_source, source_label, fetched_at, source_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        day.date,
                        day.day_name,
                        day.week_label,
                        day.school_name or result.school_name,
                        day.exported_at or result.exported_at,
                        day.exported_at_display,
                        now_iso,
                        import_id,
                        day.data_source or "file",
                        day.source_label or "Soubor (Bakaláři export)",
                        day.fetched_at or "",
                        file_hash,
                    ),
                )

                # Nepřítomné třídy
                for ac in day.absent_classes:
                    cur.execute(
                        "INSERT INTO absent_classes (date, class_name, hours_json) VALUES (?, ?, ?)",
                        (day.date, ac.class_name, json.dumps(ac.hours, ensure_ascii=False)),
                    )

                # Nepřítomní učitelé
                for at in day.absent_teachers:
                    hours_serialized = {
                        str(h): cell.model_dump() for h, cell in at.hours.items()
                    }
                    cur.execute(
                        """
                        INSERT INTO absent_teachers (
                            date, teacher_full_name, teacher_normalized_name, teacher_code, hours_json
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            day.date,
                            at.teacher_full_name,
                            at.teacher_normalized_name,
                            at.teacher_code,
                            json.dumps(hours_serialized, ensure_ascii=False),
                        ),
                    )

                # Místnosti mimo provoz
                for cr in day.closed_rooms:
                    cur.execute(
                        "INSERT INTO closed_rooms (date, room_name, hours_json) VALUES (?, ?, ?)",
                        (day.date, cr.room_name, json.dumps(cr.hours, ensure_ascii=False)),
                    )

                # Pedagogické dohledy
                for sup in day.supervisions:
                    cur.execute(
                        """
                        INSERT INTO class_supervisions (
                            date, class_name, hour_from, hour_to, teachers_text, raw_text
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            day.date,
                            sup.class_name,
                            sup.hour_from,
                            sup.hour_to,
                            sup.teachers_text,
                            sup.raw_text,
                        ),
                    )

                # Změny v rozvrzích tříd
                inserted_changes: list[tuple[int, ClassChange]] = []
                for ch in day.class_changes:
                    cur.execute(
                        """
                        INSERT INTO class_changes (
                            date, class_name, hour_from, hour_to, subject, group_name,
                            room, room_changed, change_type, change_type_raw,
                            sub_teacher, sub_teacher_changed, orig_teacher_code,
                            orig_teacher_resolved, note, paired_hour, raw_row_text
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            day.date,
                            ch.class_name,
                            ch.hour_from,
                            ch.hour_to,
                            ch.subject,
                            ch.group_name,
                            ch.room,
                            1 if ch.room_changed else 0,
                            ch.change_type.value,
                            ch.change_type_raw,
                            ch.sub_teacher,
                            1 if ch.sub_teacher_changed else 0,
                            ch.orig_teacher_code,
                            ch.orig_teacher_resolved,
                            ch.note,
                            ch.paired_hour,
                            ch.raw_row_text,
                        ),
                    )
                    inserted_changes.append((int(cur.lastrowid or 0), ch))

                # Propojení paired_change_id u přesunů
                for db_id, ch in inserted_changes:
                    if ch.paired_hour is not None:
                        for other_id, other_ch in inserted_changes:
                            if (
                                other_id != db_id
                                and other_ch.class_name == ch.class_name
                                and other_ch.hour_from == ch.paired_hour
                                and other_ch.paired_hour == ch.hour_from
                            ):
                                cur.execute(
                                    "UPDATE class_changes SET paired_change_id = ? WHERE id = ?",
                                    (other_id, db_id),
                                )
                                break

            # Uložení nerozpoznaných položek
            for unrec in result.unrecognized:
                cur.execute(
                    """
                    INSERT INTO unrecognized_items (
                        import_id, date, section, raw_content, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        import_id,
                        unrec.date,
                        unrec.section,
                        unrec.raw_content,
                        unrec.reason,
                        now_iso,
                    ),
                )

        self.cleanup_old_days(retention_days=retention_days, reference_date=reference_date)
        return import_id

    def save_web_day(self, day: ScheduleDay, source_hash: str) -> bool:
        """Uloží jediný den z webu (hybridní slučování).

        Webový import zmeny.aspx je pro daný den autoritativním zdrojem v reálném čase.
        Aktualizuje výhradně tento 1 den a ostatní dny týdne ponechává nedotčené.
        """
        now_iso = datetime.now(PRAGUE_TZ).isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.cursor()
            # Smaže výhradně tento 1 daný den
            cur.execute("DELETE FROM schedule_days WHERE date = ?", (day.date,))

            source_label = day.source_label or "Web"
            cur.execute(
                """
                INSERT INTO schedule_days (
                    date, day_name, week_label, school_name,
                    exported_at, exported_at_display, updated_at, source_import_id,
                    data_source, source_label, fetched_at, source_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'web', ?, ?, ?)
                """,
                (
                    day.date,
                    day.day_name,
                    day.week_label,
                    day.school_name,
                    day.exported_at or now_iso,
                    day.exported_at_display,
                    now_iso,
                    source_label,
                    day.fetched_at or now_iso,
                    source_hash,
                ),
            )

            for ac in day.absent_classes:
                cur.execute(
                    "INSERT INTO absent_classes (date, class_name, hours_json) VALUES (?, ?, ?)",
                    (day.date, ac.class_name, json.dumps(ac.hours, ensure_ascii=False)),
                )

            for at in day.absent_teachers:
                hours_serialized = {str(h): cell.model_dump() for h, cell in at.hours.items()}
                cur.execute(
                    """
                    INSERT INTO absent_teachers (
                        date, teacher_full_name, teacher_normalized_name, teacher_code, hours_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        day.date,
                        at.teacher_full_name,
                        at.teacher_normalized_name,
                        at.teacher_code,
                        json.dumps(hours_serialized, ensure_ascii=False),
                    ),
                )

            for cr in day.closed_rooms:
                cur.execute(
                    "INSERT INTO closed_rooms (date, room_name, hours_json) VALUES (?, ?, ?)",
                    (day.date, cr.room_name, json.dumps(cr.hours, ensure_ascii=False)),
                )

            for sup in day.supervisions:
                cur.execute(
                    """
                    INSERT INTO class_supervisions (
                        date, class_name, hour_from, hour_to, teachers_text, raw_text
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        day.date,
                        sup.class_name,
                        sup.hour_from,
                        sup.hour_to,
                        sup.teachers_text,
                        sup.raw_text,
                    ),
                )

            inserted_changes: list[tuple[int, ClassChange]] = []
            for ch in day.class_changes:
                cur.execute(
                    """
                    INSERT INTO class_changes (
                        date, class_name, hour_from, hour_to, subject, group_name,
                        room, room_changed, change_type, change_type_raw,
                        sub_teacher, sub_teacher_changed, orig_teacher_code,
                        orig_teacher_resolved, note, paired_hour, raw_row_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        day.date,
                        ch.class_name,
                        ch.hour_from,
                        ch.hour_to,
                        ch.subject,
                        ch.group_name,
                        ch.room,
                        1 if ch.room_changed else 0,
                        ch.change_type.value,
                        ch.change_type_raw,
                        ch.sub_teacher,
                        1 if ch.sub_teacher_changed else 0,
                        ch.orig_teacher_code,
                        ch.orig_teacher_resolved,
                        ch.note,
                        ch.paired_hour,
                        ch.raw_row_text,
                    ),
                )
                inserted_changes.append((int(cur.lastrowid or 0), ch))

            for db_id, ch in inserted_changes:
                if ch.paired_hour is not None:
                    for other_id, other_ch in inserted_changes:
                        if (
                            other_id != db_id
                            and other_ch.class_name == ch.class_name
                            and other_ch.hour_from == ch.paired_hour
                            and other_ch.paired_hour == ch.hour_from
                        ):
                            cur.execute(
                                "UPDATE class_changes SET paired_change_id = ? WHERE id = ?",
                                (other_id, db_id),
                            )
            return True


    def record_failed_import(
        self,
        file_name: str,
        file_hash: str,
        file_size: int,
        error_message: str,
    ) -> int:
        """Zaznamená selhání parseru bez přepsání posledních platných dat (F6)."""
        now_iso = datetime.now(PRAGUE_TZ).isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO import_runs (
                    file_name, file_hash, file_size, detected_encoding,
                    exported_at, processed_at, status, error_message,
                    days_count, changes_count, unrecognized_count
                ) VALUES (?, ?, ?, '', '', ?, 'ERROR', ?, 0, 0, 0)
                """,
                (file_name, file_hash, file_size, now_iso, error_message),
            )
            return int(cur.lastrowid or 0)

    def cleanup_old_days(
        self,
        retention_days: int = 14,
        reference_date: dt_date | None = None,
    ) -> int:
        """Smaže dny starší než retention_days (F5)."""
        ref = reference_date or datetime.now(PRAGUE_TZ).date()
        cutoff = (ref - timedelta(days=retention_days)).isoformat()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM schedule_days WHERE date < ?", (cutoff,))
            return int(cur.rowcount or 0)

    def list_available_dates(self) -> list[dict[str, str]]:
        """Vrátí seznam dostupných dnů v databázi seřazený vzestupně podle data."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date, day_name, week_label, exported_at, exported_at_display, updated_at,
                       data_source, source_label, fetched_at
                FROM schedule_days
                ORDER BY date ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def list_school_week_dates(
        self, reference_date: dt_date | datetime | str | None = None
    ) -> list[dict[str, Any]]:
        """Vrátí 6denní školní okno (Po-Pá + následující Po) s příznakem has_data."""
        stored_days = self.list_available_dates()
        return compute_school_week_dates(reference_date=reference_date, stored_days=stored_days)


    def get_day(self, target_date: str) -> ScheduleDay | None:
        """Načte kompletní data pro vybraný den (YYYY-MM-DD)."""
        with self._connect() as conn:
            day_row = conn.execute(
                "SELECT * FROM schedule_days WHERE date = ?", (target_date,)
            ).fetchone()
            if not day_row:
                return None

            ac_rows = conn.execute(
                "SELECT * FROM absent_classes WHERE date = ? ORDER BY id ASC", (target_date,)
            ).fetchall()
            absent_classes = [
                AbsentClass(
                    class_name=str(r["class_name"]),
                    hours={int(k): str(v) for k, v in json.loads(str(r["hours_json"])).items()},
                )
                for r in ac_rows
            ]

            at_rows = conn.execute(
                "SELECT * FROM absent_teachers WHERE date = ? ORDER BY id ASC", (target_date,)
            ).fetchall()
            absent_teachers = [
                AbsentTeacher(
                    teacher_full_name=str(r["teacher_full_name"]),
                    teacher_normalized_name=str(r["teacher_normalized_name"]),
                    teacher_code=str(r["teacher_code"]),
                    hours={
                        int(k): AbsentTeacherHour.model_validate(v)
                        for k, v in json.loads(str(r["hours_json"])).items()
                    },
                )
                for r in at_rows
            ]

            cr_rows = conn.execute(
                "SELECT * FROM closed_rooms WHERE date = ? ORDER BY id ASC", (target_date,)
            ).fetchall()
            closed_rooms = [
                ClosedRoom(
                    room_name=str(r["room_name"]),
                    hours={int(k): str(v) for k, v in json.loads(str(r["hours_json"])).items()},
                )
                for r in cr_rows
            ]

            sup_rows = conn.execute(
                "SELECT * FROM class_supervisions WHERE date = ? ORDER BY id ASC", (target_date,)
            ).fetchall()
            supervisions = [
                ClassSupervision(
                    class_name=str(r["class_name"]),
                    hour_from=int(r["hour_from"]),
                    hour_to=int(r["hour_to"]),
                    teachers_text=str(r["teachers_text"]),
                    raw_text=str(r["raw_text"]),
                )
                for r in sup_rows
            ]

            ch_rows = conn.execute(
                "SELECT * FROM class_changes WHERE date = ? ORDER BY id ASC", (target_date,)
            ).fetchall()
            class_changes = [
                ClassChange(
                    id=int(r["id"]),
                    date=str(r["date"]),
                    class_name=str(r["class_name"]),
                    hour_from=int(r["hour_from"]),
                    hour_to=int(r["hour_to"]),
                    subject=str(r["subject"]),
                    group_name=str(r["group_name"]),
                    room=str(r["room"]),
                    room_changed=bool(r["room_changed"]),
                    change_type=ChangeType(str(r["change_type"])),
                    change_type_raw=str(r["change_type_raw"]),
                    sub_teacher=str(r["sub_teacher"]),
                    sub_teacher_changed=bool(r["sub_teacher_changed"]),
                    orig_teacher_code=str(r["orig_teacher_code"]),
                    orig_teacher_resolved=str(r["orig_teacher_resolved"]),
                    note=str(r["note"]),
                    paired_hour=int(r["paired_hour"]) if r["paired_hour"] is not None else None,
                    paired_change_id=(
                        int(r["paired_change_id"]) if r["paired_change_id"] is not None else None
                    ),
                    raw_row_text=str(r["raw_row_text"]),
                )
                for r in ch_rows
            ]

            import_id = day_row["source_import_id"]
            unrec_rows = conn.execute(
                "SELECT * FROM unrecognized_items WHERE date = ? AND (? IS NULL OR import_id = ?) ORDER BY id ASC",
                (target_date, import_id, import_id),
            ).fetchall()
            unrecognized = [
                UnrecognizedItem(
                    date=str(r["date"]),
                    section=str(r["section"]),
                    raw_content=str(r["raw_content"]),
                    reason=str(r["reason"]),
                )
                for r in unrec_rows
            ]

            code_map = {
                str(r["code"]): str(r["normalized_name"])
                for r in conn.execute("SELECT code, normalized_name FROM teacher_directory").fetchall()
            }

            sched_day = ScheduleDay(
                date=str(day_row["date"]),
                day_name=str(day_row["day_name"]),
                week_label=str(day_row["week_label"]),
                school_name=str(day_row["school_name"]),
                exported_at=str(day_row["exported_at"]),
                exported_at_display=str(day_row["exported_at_display"]),
                data_source=str(day_row["data_source"] or "file"),
                source_label=str(day_row["source_label"] or "Soubor (Bakaláři export)"),
                fetched_at=str(day_row["fetched_at"] or ""),
                absent_classes=absent_classes,
                absent_teachers=absent_teachers,
                closed_rooms=closed_rooms,
                class_changes=class_changes,
                supervisions=supervisions,
                unrecognized=unrecognized,
            )
            sched_day.derived_teachers = build_derived_teachers(sched_day, code_map)
            return sched_day

    def get_status_summary(self, stale_threshold_hours: float = 24.0) -> dict[str, Any]:
        """Vrátí kompletní stav úložiště a posledních importů pro UI a /admin/status."""
        with self._connect() as conn:
            last_run = conn.execute(
                "SELECT * FROM import_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            last_success = conn.execute(
                "SELECT * FROM import_runs WHERE status = 'SUCCESS' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            recent_runs = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM import_runs ORDER BY id DESC LIMIT 20"
                ).fetchall()
            ]
            days_count = int(
                conn.execute("SELECT COUNT(*) FROM schedule_days").fetchone()[0]
            )
            changes_count = int(
                conn.execute("SELECT COUNT(*) FROM class_changes").fetchone()[0]
            )
            teachers_count = int(
                conn.execute("SELECT COUNT(*) FROM teacher_directory").fetchone()[0]
            )

            latest_success_id = int(last_success["id"]) if last_success else None
            unrec_rows = (
                conn.execute(
                    "SELECT * FROM unrecognized_items WHERE import_id = ? ORDER BY id ASC",
                    (latest_success_id,),
                ).fetchall()
                if latest_success_id is not None
                else []
            )

            has_parse_error = bool(last_run and last_run["status"] == "ERROR")
            last_error_message = str(last_run["error_message"]) if has_parse_error and last_run else ""
            last_error_at = str(last_run["processed_at"]) if has_parse_error and last_run else ""

            exported_at_iso = str(last_success["exported_at"]) if last_success else ""
            processed_at_iso = str(last_success["processed_at"]) if last_success else ""

            is_stale = True
            age_hours: float | None = None
            ref_ts = exported_at_iso or processed_at_iso
            if ref_ts:
                try:
                    dt_ref = datetime.fromisoformat(ref_ts)
                    if dt_ref.tzinfo is None:
                        dt_ref = dt_ref.replace(tzinfo=PRAGUE_TZ)
                    delta = datetime.now(PRAGUE_TZ) - dt_ref
                    age_hours = round(delta.total_seconds() / 3600.0, 2)
                    is_stale = age_hours > stale_threshold_hours
                except ValueError:
                    is_stale = True

            return {
                "has_data": days_count > 0,
                "days_count": days_count,
                "changes_count": changes_count,
                "teachers_count": teachers_count,
                "last_success": dict(last_success) if last_success else None,
                "last_run": dict(last_run) if last_run else None,
                "has_parse_error": has_parse_error,
                "last_error_message": last_error_message,
                "last_error_at": last_error_at,
                "is_stale": is_stale,
                "age_hours": age_hours,
                "stale_threshold_hours": stale_threshold_hours,
                "unrecognized_items": [dict(r) for r in unrec_rows],
                "recent_runs": recent_runs,
            }
