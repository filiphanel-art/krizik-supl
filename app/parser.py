"""Parser HTML exportů z programu Bakaláři – Suplování (FastReport 5.0)."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag
from charset_normalizer import from_bytes

from app.models import (
    AbsentClass,
    AbsentTeacher,
    AbsentTeacherHour,
    ChangeType,
    ClassChange,
    ClassSupervision,
    ClosedRoom,
    DerivedTeacherEntry,
    ParseResult,
    ScheduleDay,
    TeacherHourStatus,
    UnrecognizedItem,
)

PRAGUE_TZ = ZoneInfo("Europe/Prague")

CZECH_CHARS = set("áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ")
MOJIBAKE_MARKERS = {"\ufffd", "Ĺ", "Ä", "Ă", "Ë", "Ĺľ", "Ĺˇ", "ÄŤ", "Ĺ™"}

DATE_HEADER_RE = re.compile(
    r"^(?:(Pondělí|Úterý|Středa|Čtvrtek|Pátek|Sobota|Neděle)\s+)?"
    r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})$",
    re.IGNORECASE,
)
EXPORT_DATE_RE = re.compile(
    r"datum\s+výpisu:\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\s*,\s*(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)
HOUR_SINGLE_RE = re.compile(r"^(\d{1,2})\.\s*hod$", re.IGNORECASE)
HOUR_RANGE_RE = re.compile(r"^(\d{1,2})\.\s*-\s*(\d{1,2})\.\s*hod$", re.IGNORECASE)
ACTION_SPAN_RE = re.compile(
    r"^(\d{1,2})\.\s*-\s*(\d{1,2})\.\s*hod\s*(?:\((.+)\)|-\s*(.+)|(.+))?$",
    re.IGNORECASE,
)
SUPERVISION_RE = re.compile(
    r"^(\d{1,2})\.\s*-\s*(\d{1,2})\.\s*hod\s*-\s*(.+)$",
    re.IGNORECASE,
)
MOVE_TARGET_RE = re.compile(r"^(?:na|z)\s+(\d{1,2})\.\s*hod$", re.IGNORECASE)
TEACHER_CODE_RE = re.compile(r"^[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýžA-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ0-9]{0,3}$")

ACADEMIC_TITLES = {
    "ing",
    "mgr",
    "bc",
    "bca",
    "rndr",
    "phdr",
    "paeddr",
    "mudr",
    "judr",
    "doc",
    "prof",
    "phd",
    "ph",
    "d",
    "csc",
    "dis",
    "thdr",
    "mga",
}

GREY_CLASSES = {"s14", "s15", "s18", "s22", "s24", "s28", "s29", "s30"}


class ParseError(Exception):
    """Chyba při parsování neplatného nebo poškozeného HTML souboru."""


def _score_czech_text(text: str) -> int:
    """Ohodnotí kvalitu dekódovaného českého textu."""
    score = sum(3 for ch in text if ch in CZECH_CHARS)
    keywords = ("Suplování", "týden", "Nepřítomní", "učitelé", "tříd", "rozvrzích", "výpisu")
    for kw in keywords:
        if kw in text:
            score += 50
    for bad in MOJIBAKE_MARKERS:
        if bad in text:
            score -= 25
    return score


def detect_and_decode(raw_bytes: bytes, max_size_bytes: int = 10 * 1024 * 1024) -> tuple[str, str]:
    """Bezpečně detekuje kódování (UTF-8, windows-1250, iso-8859-2) a dekóduje HTML."""
    if not raw_bytes:
        raise ParseError("Vstupní soubor je prázdný.")
    if len(raw_bytes) > max_size_bytes:
        raise ParseError(
            f"Velikost souboru ({len(raw_bytes)} B) překračuje povolený limit ({max_size_bytes} B)."
        )

    # 1. Kontrola BOM
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return raw_bytes.decode("utf-8-sig"), "utf-8-sig"
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw_bytes.decode("utf-16"), "utf-16"

    # 2. Pokus o striktní UTF-8
    try:
        utf8_text = raw_bytes.decode("utf-8", errors="strict")
        if _score_czech_text(utf8_text) >= 0:
            return utf8_text, "utf-8"
    except UnicodeDecodeError:
        pass

    # 3. Kandidátní středoevropská kódování + charset-normalizer
    candidates: list[tuple[int, str, str]] = []
    for enc in ("cp1250", "iso-8859-2"):
        try:
            decoded = raw_bytes.decode(enc, errors="strict")
            candidates.append((_score_czech_text(decoded), enc, decoded))
        except UnicodeDecodeError:
            continue

    cn_match = from_bytes(raw_bytes).best()
    if cn_match is not None:
        cn_text = str(cn_match)
        cn_enc = cn_match.encoding or "unknown"
        candidates.append((_score_czech_text(cn_text), cn_enc, cn_text))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, best_enc, best_text = candidates[0]
        if best_score > -100:
            return best_text, best_enc

    # Poslední záchrana: cp1250 s nahrazením chyb
    return raw_bytes.decode("cp1250", errors="replace"), "cp1250"


def normalize_teacher_full_name(full_name: str) -> str:
    """Převede 'Ing. Miloš Kodad' nebo 'Ing. Zdeněk Novák Ph.D.' na 'Kodad Miloš' / 'Novák Zdeněk'."""
    cleaned = re.sub(r"[,]", " ", full_name).strip()
    tokens = cleaned.split()
    name_parts: list[str] = []
    for tok in tokens:
        stripped = tok.strip(".").lower()
        if stripped in ACADEMIC_TITLES or tok.lower() in {"ph.d.", "cs.c.", "di.s."}:
            continue
        name_parts.append(tok)

    if len(name_parts) >= 2:
        # V sekci Nepřítomní učitelé je pořadí Jméno Příjmení (např. Miloš Kodad -> Kodad Miloš)
        surname = name_parts[-1]
        given = " ".join(name_parts[:-1])
        return f"{surname} {given}"
    return cleaned


def _clean_cell_text(td: Tag) -> str:
    """Vrátí očištěný text buňky bez pevných mezer (&nbsp;)."""
    raw = td.get_text(separator=" ", strip=True)
    return raw.replace("\xa0", " ").strip()


def _cell_classes(td: Tag) -> set[str]:
    """Vrátí množinu CSS tříd buňky."""
    cls = td.get("class")
    if isinstance(cls, list):
        return {str(c) for c in cls}
    if isinstance(cls, str):
        return set(cls.split())
    return set()


def _strip_parens(val: str) -> str:
    """Odstraní vnější kulaté závorky, např. '(P7)' -> 'P7'."""
    val = val.strip()
    if val.startswith("(") and val.endswith(")") and len(val) >= 2:
        return val[1:-1].strip()
    return val


def _classify_change_type(
    raw_type: str,
    room_changed: bool,
    sub_teacher_changed: bool,
    orig_teacher_code: str,
) -> ChangeType:
    """Převede surový text typu změny na normalizovaný ChangeType."""
    low = raw_type.strip().lower()
    if low == "supluje":
        return ChangeType.SUPLOVANI
    if low == "odpadá":
        return ChangeType.ODPADA
    if low in ("spojí", "spojeno"):
        return ChangeType.SPOJENO
    if low == "navíc":
        return ChangeType.NAVIC
    if low == "výměna":
        return ChangeType.VYMENA
    if low.startswith("přesun"):
        if ">>" in low or "na " in low:
            return ChangeType.PRESUN_NA
        if "<<" in low or "z " in low:
            return ChangeType.PRESUN_Z
        return ChangeType.PRESUN_NA
    if low == "změna":
        if room_changed or (not orig_teacher_code and not sub_teacher_changed):
            return ChangeType.ZMENA_UCEBNY
        return ChangeType.OSTATNI
    return ChangeType.OSTATNI


def _pair_moves_in_day(day: ScheduleDay) -> None:
    """Spáruje záznamy 'přesun >>' (na X. hod) a 'přesun <<' (z Y. hod) v rámci téže třídy a dne."""
    by_class: dict[str, list[ClassChange]] = {}
    for ch in day.class_changes:
        if ch.change_type in (ChangeType.PRESUN_NA, ChangeType.PRESUN_Z):
            by_class.setdefault(ch.class_name, []).append(ch)

    for _cls_name, moves in by_class.items():
        sources = [m for m in moves if m.change_type == ChangeType.PRESUN_NA]
        targets = [m for m in moves if m.change_type == ChangeType.PRESUN_Z]
        for src in sources:
            m_src = MOVE_TARGET_RE.match(src.note)
            target_hour = int(m_src.group(1)) if m_src else None
            for tgt in targets:
                if tgt.paired_hour is not None:
                    continue
                m_tgt = MOVE_TARGET_RE.match(tgt.note)
                source_hour = int(m_tgt.group(1)) if m_tgt else None
                if (
                    target_hour == tgt.hour_from
                    and source_hour == src.hour_from
                    and (not src.subject or not tgt.subject or src.subject == tgt.subject)
                ):
                    src.paired_hour = tgt.hour_from
                    tgt.paired_hour = src.hour_from
                    if not src.sub_teacher and tgt.sub_teacher:
                        src.sub_teacher = tgt.sub_teacher
                    if not src.room and tgt.room:
                        src.room = tgt.room
                    break


def _correlate_teachers(days: list[ScheduleDay]) -> tuple[dict[str, str], dict[str, str]]:
    """Odvodí slovník zkratek učitelů (code -> 'Příjmení Jméno') křížovou kontrolou dat."""
    code_to_name: dict[str, str] = {}
    name_to_titles: dict[str, str] = {}

    for day in days:
        for at in day.absent_teachers:
            name_to_titles[at.teacher_normalized_name] = at.teacher_full_name

        # Mapování (hour, sub_code) z Nepřítomných učitelů a (hour, orig_code, sub_teacher) ze Změn
        for hour in range(1, 11):
            changes_at_hour = [
                ch
                for ch in day.class_changes
                if ch.hour_from <= hour <= ch.hour_to
                and ch.orig_teacher_code
                and ch.change_type in (ChangeType.SUPLOVANI, ChangeType.SPOJENO, ChangeType.ODPADA)
            ]
            absent_at_hour = [
                (at, at.hours[hour])
                for at in day.absent_teachers
                if hour in at.hours
                and at.hours[hour].status
                in (TeacherHourStatus.ABSENT_SUBSTITUTED, TeacherHourStatus.ABSENT_CANCELLED)
            ]

            # 1) Spárování suplující zkratky (např. Vl) se jménem suplujícího (Valtr Pavel)
            # a původního učitele (Ing. Miloš Kodad) s původní zkratkou (Ko)
            sub_changes = [
                ch for ch in changes_at_hour if ch.sub_teacher and ch.orig_teacher_code
            ]
            sub_absents = [
                (at, cell)
                for at, cell in absent_at_hour
                if cell.status == TeacherHourStatus.ABSENT_SUBSTITUTED
            ]

            if len(sub_changes) == 1 and len(sub_absents) == 1:
                ch = sub_changes[0]
                at, cell = sub_absents[0]
                code_to_name.setdefault(cell.sub_teacher_code, ch.sub_teacher)
                code_to_name.setdefault(ch.orig_teacher_code, at.teacher_normalized_name)
                at.teacher_code = ch.orig_teacher_code
            else:
                # Více suplování v téže hodině: spáruj podle shodného prvního písmene příjmení
                for ch in sub_changes:
                    matching_abs = [
                        (at, cell)
                        for at, cell in sub_absents
                        if at.teacher_normalized_name[:1].upper()
                        == ch.orig_teacher_code[:1].upper()
                        and ch.sub_teacher[:1].upper() == cell.sub_teacher_code[:1].upper()
                    ]
                    if len(matching_abs) == 1:
                        at, cell = matching_abs[0]
                        code_to_name.setdefault(cell.sub_teacher_code, ch.sub_teacher)
                        code_to_name.setdefault(ch.orig_teacher_code, at.teacher_normalized_name)
                        if not at.teacher_code:
                            at.teacher_code = ch.orig_teacher_code

            # 2) Spárování odpadlých hodin ('..') s původní zkratkou
            canc_changes = [
                ch for ch in changes_at_hour if ch.change_type == ChangeType.ODPADA
            ]
            canc_absents = [
                (at, cell)
                for at, cell in absent_at_hour
                if cell.status == TeacherHourStatus.ABSENT_CANCELLED
            ]
            if len(canc_changes) == 1 and len(canc_absents) == 1:
                ch = canc_changes[0]
                at, _cell = canc_absents[0]
                code_to_name.setdefault(ch.orig_teacher_code, at.teacher_normalized_name)
                if not at.teacher_code:
                    at.teacher_code = ch.orig_teacher_code
            else:
                for ch in canc_changes:
                    matching_canc = [
                        (at, cell)
                        for at, cell in canc_absents
                        if at.teacher_normalized_name[:1].upper()
                        == ch.orig_teacher_code[:1].upper()
                    ]
                    if len(matching_canc) == 1:
                        at, _cell = matching_canc[0]
                        code_to_name.setdefault(ch.orig_teacher_code, at.teacher_normalized_name)
                        if not at.teacher_code:
                            at.teacher_code = ch.orig_teacher_code

    # Doplnění odvozených jmen do záznamů dnů
    name_to_code = {v: k for k, v in code_to_name.items()}
    for day in days:
        for at in day.absent_teachers:
            if not at.teacher_code and at.teacher_normalized_name in name_to_code:
                at.teacher_code = name_to_code[at.teacher_normalized_name]
            for cell in at.hours.values():
                if cell.sub_teacher_code and cell.sub_teacher_code in code_to_name:
                    cell.sub_teacher_resolved = code_to_name[cell.sub_teacher_code]

        for ch in day.class_changes:
            if ch.orig_teacher_code and ch.orig_teacher_code in code_to_name:
                ch.orig_teacher_resolved = code_to_name[ch.orig_teacher_code]

    return code_to_name, name_to_titles


def build_derived_teachers(
    day: ScheduleDay, code_to_name: dict[str, str]
) -> list[DerivedTeacherEntry]:
    """Sestaví odvozený pohled podle učitelů ze změn tříd a pedagogických dohledů."""
    entries: list[DerivedTeacherEntry] = []
    name_to_code = {v: k for k, v in code_to_name.items()}

    for ch in day.class_changes:
        if ch.change_type == ChangeType.CELODENNI_AKCE:
            continue

        # 1) Aktivní / suplující / změněný učitel (sloupec 6)
        if ch.sub_teacher:
            t_code = name_to_code.get(ch.sub_teacher, "")
            if ch.change_type == ChangeType.SUPLOVANI:
                role = "supluje"
            elif ch.change_type == ChangeType.SPOJENO:
                role = "spojuje"
            elif ch.change_type == ChangeType.NAVIC:
                role = "navíc"
            elif ch.change_type in (ChangeType.PRESUN_NA, ChangeType.PRESUN_Z):
                role = "přesun"
            elif ch.change_type == ChangeType.ZMENA_UCEBNY:
                role = "změna učebny"
            else:
                role = ch.change_type_raw or "změna"

            counterpart = ""
            if ch.orig_teacher_resolved:
                counterpart = f"{ch.orig_teacher_resolved} ({ch.orig_teacher_code})"
            elif ch.orig_teacher_code:
                counterpart = f"({ch.orig_teacher_code})"

            # U přesunu nechceme duplikovat tutéž informaci dvakrát bez kontextu, ale obě hodiny jsou pro učitele důležité
            entries.append(
                DerivedTeacherEntry(
                    teacher_key=ch.sub_teacher,
                    teacher_display=f"{ch.sub_teacher} ({t_code})" if t_code else ch.sub_teacher,
                    teacher_code=t_code,
                    role=role,
                    hour_from=ch.hour_from,
                    hour_to=ch.hour_to,
                    class_name=ch.class_name,
                    subject=ch.subject,
                    group_name=ch.group_name,
                    room=ch.room,
                    change_type=ch.change_type,
                    change_type_raw=ch.change_type_raw,
                    counterpart_teacher=counterpart,
                    note=ch.note,
                )
            )

        # 2) Původní (nepřítomný) učitel (sloupec 7 v závorce)
        if ch.orig_teacher_code:
            orig_name = ch.orig_teacher_resolved or code_to_name.get(ch.orig_teacher_code, "")
            t_key = orig_name if orig_name else f"({ch.orig_teacher_code})"
            t_disp = (
                f"{orig_name} ({ch.orig_teacher_code})"
                if orig_name
                else f"Zkratka {ch.orig_teacher_code}"
            )
            entries.append(
                DerivedTeacherEntry(
                    teacher_key=t_key,
                    teacher_display=t_disp,
                    teacher_code=ch.orig_teacher_code,
                    role="chybí (zastoupen)" if ch.sub_teacher else "chybí (odpadá)",
                    hour_from=ch.hour_from,
                    hour_to=ch.hour_to,
                    class_name=ch.class_name,
                    subject=ch.subject,
                    group_name=ch.group_name,
                    room=ch.room,
                    change_type=ch.change_type,
                    change_type_raw=ch.change_type_raw,
                    counterpart_teacher=ch.sub_teacher,
                    note=ch.note,
                )
            )

    # 3) Pedagogické dohledy u tříd
    for sup in day.supervisions:
        for raw_t in sup.teachers_text.split(","):
            t_name = raw_t.strip()
            if not t_name:
                continue
            t_code = name_to_code.get(t_name, "")
            entries.append(
                DerivedTeacherEntry(
                    teacher_key=t_name,
                    teacher_display=f"{t_name} ({t_code})" if t_code else t_name,
                    teacher_code=t_code,
                    role="dohled",
                    hour_from=sup.hour_from,
                    hour_to=sup.hour_to,
                    class_name=sup.class_name,
                    subject="Dohled",
                    change_type=ChangeType.CELODENNI_AKCE,
                    change_type_raw="dohled",
                    note=f"Pedagogický dohled ({sup.hour_from}.–{sup.hour_to}. hod)",
                )
            )

    entries.sort(key=lambda e: (e.teacher_key.lower(), e.hour_from, e.class_name))
    return entries


def parse_suplovani_html(
    raw_bytes: bytes,
    file_name: str = "export.html",
    known_teachers: dict[str, str] | None = None,
    max_size_bytes: int = 10 * 1024 * 1024,
) -> ParseResult:
    """Zpracuje surové bajty HTML exportu Bakaláři – Suplování a vrátí ParseResult."""
    html_text, detected_encoding = detect_and_decode(raw_bytes, max_size_bytes=max_size_bytes)

    soup = BeautifulSoup(html_text, "lxml")
    tables = soup.find_all("table")
    if not tables:
        raise ParseError("HTML soubor neobsahuje žádnou tabulku (<table>).")

    days_by_date: dict[str, ScheduleDay] = {}
    days_order: list[str] = []
    global_unrecognized: list[UnrecognizedItem] = []
    global_exported_at = ""
    global_school_name = ""

    current_day: ScheduleDay | None = None
    current_section: str | None = None
    current_class_name: str = ""

    for table in tables:
        rows = table.find_all("tr")
        for tr in rows:
            tds = tr.find_all("td")
            if not tds:
                continue

            texts = [_clean_cell_text(td) for td in tds]
            if not any(texts):
                continue

            # 1) Detekce řádku hlavičky dne: "Suplování:" | "Pondělí 2. 11. 2026" | "(2. týden)"
            if texts[0].startswith("Suplování"):
                date_str_raw = texts[1] if len(texts) > 1 else ""
                week_raw = _strip_parens(texts[2]) if len(texts) > 2 else ""
                m_date = DATE_HEADER_RE.match(date_str_raw)
                if not m_date:
                    rec = UnrecognizedItem(
                        date=current_day.date if current_day else "",
                        section="Hlavička dne",
                        raw_content=" | ".join(t for t in texts if t),
                        reason=f"Nerozpoznaný formát data v nadpisu: {date_str_raw!r}",
                    )
                    global_unrecognized.append(rec)
                    continue

                day_name = m_date.group(1) or ""
                d_num, m_num, y_num = int(m_date.group(2)), int(m_date.group(3)), int(m_date.group(4))
                try:
                    iso_date = f"{y_num:04d}-{m_num:02d}-{d_num:02d}"
                    datetime(y_num, m_num, d_num)
                except ValueError as exc:
                    raise ParseError(f"Neplatné datum v hlavičce: {date_str_raw!r}") from exc

                if iso_date in days_by_date:
                    current_day = days_by_date[iso_date]
                else:
                    current_day = ScheduleDay(
                        date=iso_date,
                        day_name=day_name,
                        week_label=week_raw,
                    )
                    days_by_date[iso_date] = current_day
                    days_order.append(iso_date)

                current_section = None
                current_class_name = ""
                continue

            # 2) Detekce podhlavičky se školou a "datum výpisu: 5. 11. 2026, 08:26"
            joined_row = " | ".join(t for t in texts if t)
            if "datum výpisu" in joined_row.lower():
                school_part = texts[0] if len(texts) > 1 else ""
                export_part = texts[-1]
                m_exp = EXPORT_DATE_RE.search(export_part)
                exp_iso = ""
                exp_disp = export_part.strip()
                if m_exp:
                    ed, em, ey, eh, emin = (int(g) for g in m_exp.groups())
                    dt = datetime(ey, em, ed, eh, emin, tzinfo=PRAGUE_TZ)
                    exp_iso = dt.isoformat()
                    exp_disp = f"{ed}. {em}. {ey} {eh:02d}:{emin:02d}"
                if school_part and not global_school_name:
                    global_school_name = school_part
                if exp_iso and not global_exported_at:
                    global_exported_at = exp_iso
                if current_day is not None:
                    if school_part:
                        current_day.school_name = school_part
                    if exp_iso:
                        current_day.exported_at = exp_iso
                        current_day.exported_at_display = exp_disp
                continue

            # Pokud ještě nemáme aktivní den, zaznamenej jako nerozpoznané
            if current_day is None:
                global_unrecognized.append(
                    UnrecognizedItem(
                        section="Mimo blok dne",
                        raw_content=joined_row,
                        reason="Řádek před prvním nadpisem Suplování",
                    )
                )
                continue

            # 3) Přepnutí sekce
            first_cell = texts[0]
            if first_cell in (
                "Nepřítomné třídy",
                "Nepřítomní učitelé",
                "Místnosti mimo provoz",
                "Změny v rozvrzích tříd",
                "Pedagogické dohledy u tříd",
            ):
                current_section = first_cell
                current_class_name = ""
                continue

            # Ošetření prázdné sekce s textem "nejsou" / "žádné"
            if len([t for t in texts if t]) == 1 and first_cell.lower() in (
                "nejsou",
                "žádné",
                "žádné změny",
                "-",
            ):
                continue

            # 4) Zpracování řádku podle aktivní sekce
            if current_section == "Nepřítomné třídy":
                if len(tds) == 11 and first_cell:
                    hours_map: dict[int, str] = {}
                    for h_idx in range(1, 11):
                        val = texts[h_idx]
                        if val:
                            hours_map[h_idx] = val
                    current_day.absent_classes.append(
                        AbsentClass(class_name=first_cell, hours=hours_map)
                    )
                else:
                    current_day.unrecognized.append(
                        UnrecognizedItem(
                            date=current_day.date,
                            section=current_section,
                            raw_content=joined_row,
                            reason="Neočekávaný počet buněk v sekci Nepřítomné třídy",
                        )
                    )

            elif current_section == "Nepřítomní učitelé":
                if len(tds) == 11 and first_cell:
                    norm_name = normalize_teacher_full_name(first_cell)
                    t_hours: dict[int, AbsentTeacherHour] = {}
                    for h_idx in range(1, 11):
                        cell_val = texts[h_idx]
                        if not cell_val:
                            continue
                        if cell_val == "-":
                            t_hours[h_idx] = AbsentTeacherHour(
                                hour=h_idx, raw=cell_val, status=TeacherHourStatus.ABSENT_FREE
                            )
                        elif cell_val == "..":
                            t_hours[h_idx] = AbsentTeacherHour(
                                hour=h_idx, raw=cell_val, status=TeacherHourStatus.ABSENT_CANCELLED
                            )
                        elif TEACHER_CODE_RE.match(cell_val):
                            t_hours[h_idx] = AbsentTeacherHour(
                                hour=h_idx,
                                raw=cell_val,
                                status=TeacherHourStatus.ABSENT_SUBSTITUTED,
                                sub_teacher_code=cell_val,
                            )
                        else:
                            t_hours[h_idx] = AbsentTeacherHour(
                                hour=h_idx, raw=cell_val, status=TeacherHourStatus.UNRECOGNIZED
                            )
                            current_day.unrecognized.append(
                                UnrecognizedItem(
                                    date=current_day.date,
                                    section=current_section,
                                    raw_content=f"{first_cell} [{h_idx}. hod]: {cell_val}",
                                    reason=f"Nerozpoznaný symbol v mřížce nepřítomných učitelů: {cell_val!r}",
                                )
                            )
                    current_day.absent_teachers.append(
                        AbsentTeacher(
                            teacher_full_name=first_cell,
                            teacher_normalized_name=norm_name,
                            hours=t_hours,
                        )
                    )
                else:
                    current_day.unrecognized.append(
                        UnrecognizedItem(
                            date=current_day.date,
                            section=current_section,
                            raw_content=joined_row,
                            reason="Neočekávaný formát řádku v sekci Nepřítomní učitelé",
                        )
                    )

            elif current_section == "Místnosti mimo provoz":
                if len(tds) == 11 and first_cell:
                    r_hours: dict[int, str] = {}
                    for h_idx in range(1, 11):
                        val = texts[h_idx]
                        if val:
                            r_hours[h_idx] = val
                    current_day.closed_rooms.append(
                        ClosedRoom(room_name=first_cell, hours=r_hours)
                    )
                else:
                    current_day.unrecognized.append(
                        UnrecognizedItem(
                            date=current_day.date,
                            section=current_section,
                            raw_content=joined_row,
                            reason="Neočekávaný formát řádku v sekci Místnosti mimo provoz",
                        )
                    )

            elif current_section == "Změny v rozvrzích tříd":
                if first_cell:
                    current_class_name = first_cell

                # Typ A: Běžný 8-buněčný řádek změny třídy
                if len(tds) == 8 and current_class_name:
                    hour_raw = texts[1]
                    subject = texts[2]
                    group_name = texts[3]
                    room_raw = texts[4]
                    change_raw = texts[5]
                    sub_teacher = texts[6]
                    orig_or_note = texts[7]

                    m_h = HOUR_SINGLE_RE.match(hour_raw)
                    m_hr = HOUR_RANGE_RE.match(hour_raw)
                    if m_h:
                        h_from = h_to = int(m_h.group(1))
                    elif m_hr:
                        h_from, h_to = int(m_hr.group(1)), int(m_hr.group(2))
                    else:
                        current_day.unrecognized.append(
                            UnrecognizedItem(
                                date=current_day.date,
                                section=current_section,
                                raw_content=joined_row,
                                reason=f"Nerozpoznaná vyučovací hodina: {hour_raw!r}",
                            )
                        )
                        continue

                    room_clean = _strip_parens(room_raw)
                    room_classes = _cell_classes(tds[4])
                    teacher_classes = _cell_classes(tds[6])
                    room_changed = bool(room_clean) and not bool(room_classes & GREY_CLASSES)
                    sub_teacher_changed = bool(sub_teacher) and not bool(
                        teacher_classes & GREY_CLASSES
                    )

                    orig_code = ""
                    note = ""
                    if orig_or_note.startswith("(") and orig_or_note.endswith(")"):
                        orig_code = _strip_parens(orig_or_note)
                    elif orig_or_note:
                        note = orig_or_note

                    c_type = _classify_change_type(
                        change_raw, room_changed, sub_teacher_changed, orig_code
                    )
                    if c_type == ChangeType.OSTATNI and change_raw.lower() not in (
                        "změna",
                        "ostatní",
                    ):
                        current_day.unrecognized.append(
                            UnrecognizedItem(
                                date=current_day.date,
                                section=current_section,
                                raw_content=joined_row,
                                reason=f"Neznámý typ změny: {change_raw!r}",
                            )
                        )

                    current_day.class_changes.append(
                        ClassChange(
                            date=current_day.date,
                            class_name=current_class_name,
                            hour_from=h_from,
                            hour_to=h_to,
                            subject=subject,
                            group_name=group_name,
                            room=room_clean,
                            room_changed=room_changed,
                            change_type=c_type,
                            change_type_raw=change_raw,
                            sub_teacher=sub_teacher,
                            sub_teacher_changed=sub_teacher_changed,
                            orig_teacher_code=orig_code,
                            note=note,
                            raw_row_text=joined_row,
                        )
                    )

                # Typ B: Celodenní / vícehodinová akce třídy (např. "V2 | | 1.- 7. hod (Souvislá praxe)")
                elif len(tds) == 3 and current_class_name and texts[2]:
                    span_text = texts[2]
                    m_span = ACTION_SPAN_RE.match(span_text)
                    if m_span:
                        h_from = int(m_span.group(1))
                        h_to = int(m_span.group(2))
                        action_desc = (
                            m_span.group(3) or m_span.group(4) or m_span.group(5) or span_text
                        ).strip()
                        current_day.class_changes.append(
                            ClassChange(
                                date=current_day.date,
                                class_name=current_class_name,
                                hour_from=h_from,
                                hour_to=h_to,
                                subject=action_desc,
                                change_type=ChangeType.CELODENNI_AKCE,
                                change_type_raw="celodenní akce",
                                note=action_desc,
                                raw_row_text=joined_row,
                            )
                        )
                    else:
                        current_day.unrecognized.append(
                            UnrecognizedItem(
                                date=current_day.date,
                                section=current_section,
                                raw_content=joined_row,
                                reason=f"Nerozpoznaný formát celodenní akce: {span_text!r}",
                            )
                        )
                else:
                    current_day.unrecognized.append(
                        UnrecognizedItem(
                            date=current_day.date,
                            section=current_section,
                            raw_content=joined_row,
                            reason="Nerozpoznaný formát řádku v sekci Změny v rozvrzích tříd",
                        )
                    )

            elif current_section == "Pedagogické dohledy u tříd":
                if len(tds) == 2 and first_cell and texts[1]:
                    sup_text = texts[1]
                    m_sup = SUPERVISION_RE.match(sup_text)
                    if m_sup:
                        current_day.supervisions.append(
                            ClassSupervision(
                                class_name=first_cell,
                                hour_from=int(m_sup.group(1)),
                                hour_to=int(m_sup.group(2)),
                                teachers_text=m_sup.group(3).strip(),
                                raw_text=joined_row,
                            )
                        )
                    else:
                        current_day.unrecognized.append(
                            UnrecognizedItem(
                                date=current_day.date,
                                section=current_section,
                                raw_content=joined_row,
                                reason=f"Nerozpoznaný formát pedagogického dohledu: {sup_text!r}",
                            )
                        )
                else:
                    current_day.unrecognized.append(
                        UnrecognizedItem(
                            date=current_day.date,
                            section=current_section,
                            raw_content=joined_row,
                            reason="Neočekávaný formát řádku v sekci Pedagogické dohledy u tříd",
                        )
                    )
            else:
                current_day.unrecognized.append(
                    UnrecognizedItem(
                        date=current_day.date,
                        section=current_section or "Neznámá sekce",
                        raw_content=joined_row,
                        reason="Řádek mimo známé sekce dne",
                    )
                )

    if not days_order:
        raise ParseError("V HTML souboru nebyl nalezen žádný platný den s hlavičkou 'Suplování:'.")

    ordered_days = [days_by_date[d] for d in days_order]
    for day in ordered_days:
        _pair_moves_in_day(day)

    inferred_codes, name_to_titles = _correlate_teachers(ordered_days)
    merged_codes: dict[str, str] = {}
    if known_teachers:
        merged_codes.update(known_teachers)
    merged_codes.update(inferred_codes)

    # Aktualizace se sloučeným slovníkem učitelů a sestavení odvozeného pohledu
    for day in ordered_days:
        for ch in day.class_changes:
            if not ch.orig_teacher_resolved and ch.orig_teacher_code in merged_codes:
                ch.orig_teacher_resolved = merged_codes[ch.orig_teacher_code]
        for at in day.absent_teachers:
            for cell in at.hours.values():
                if not cell.sub_teacher_resolved and cell.sub_teacher_code in merged_codes:
                    cell.sub_teacher_resolved = merged_codes[cell.sub_teacher_code]
        day.derived_teachers = build_derived_teachers(day, merged_codes)
        global_unrecognized.extend(day.unrecognized)

    return ParseResult(
        file_name=file_name,
        detected_encoding=detected_encoding,
        exported_at=global_exported_at,
        school_name=global_school_name,
        days=ordered_days,
        teacher_directory=merged_codes,
        teacher_titles=name_to_titles,
        unrecognized=global_unrecognized,
    )
