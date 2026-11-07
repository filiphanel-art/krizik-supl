"""Parser pro jednodenní HTML stránku Bakaláři - změny v rozvrhu (next/zmeny.aspx)."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

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
    TeacherHourStatus,
    UnrecognizedItem,
)
from app.parser import (
    ParseError,
    _classify_change_type,
    _correlate_teachers,
    _pair_moves_in_day,
    build_derived_teachers,
    detect_and_decode,
    normalize_teacher_full_name,
)

PRAGUE_TZ = ZoneInfo("Europe/Prague")
CZECH_DAY_NAMES = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"]


def _clean_cell_text(td: Tag) -> str:
    """Očistí text buňky od pevných mezer a bílých znaků."""
    return td.get_text(separator=" ", strip=True).replace("\xa0", " ").strip()


def parse_web_zmeny_html(
    html_content: str | bytes,
    known_teachers: dict[str, str] | None = None,
) -> ParseResult:
    """Zpracuje HTML obsah jednodenního výstupu Bakalářů z next/zmeny.aspx."""
    if isinstance(html_content, bytes):
        try:
            html_text = html_content.decode("utf-8")
            detected_encoding = "utf-8"
        except UnicodeDecodeError:
            html_text, detected_encoding = detect_and_decode(html_content)
    else:
        html_text = html_content
        detected_encoding = "utf-8"

    soup = BeautifulSoup(html_text, "lxml")

    # 1. Datum rozvrhu z #DateEdit_I nebo záložně z <h1>
    date_str = ""
    date_edit = soup.find("input", id="DateEdit_I")
    if isinstance(date_edit, Tag) and date_edit.get("value"):
        raw_val = str(date_edit.get("value") or "").strip()
        m_date = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", raw_val)
        if m_date:
            d, m, y = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
            dt_obj = datetime(y, m, d)
            date_str = dt_obj.strftime("%Y-%m-%d")

    if not date_str:
        h1_tag = soup.find("h1")
        if isinstance(h1_tag, Tag):
            h1_text = h1_tag.get_text(strip=True)
            m_h1 = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.(?:\s*(\d{4}))?", h1_text)
            if m_h1:
                d = int(m_h1.group(1))
                m = int(m_h1.group(2))
                y = int(m_h1.group(3)) if m_h1.group(3) else datetime.now(PRAGUE_TZ).year
                dt_obj = datetime(y, m, d)
                date_str = dt_obj.strftime("%Y-%m-%d")

    if not date_str:
        raise ParseError("Z webového rozvrhu se nepodařilo detekovat platné datum (chybí #DateEdit_I i <h1>).")

    dt_parsed = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = CZECH_DAY_NAMES[dt_parsed.weekday()]

    # 2. Název školy
    school_elem = soup.find(id="schoolTitle")
    school_name = (
        school_elem.get_text(strip=True)
        if isinstance(school_elem, Tag)
        else "VOŠ a SPŠE Františka Křižíka"
    )

    teacher_dir: dict[str, str] = dict(known_teachers or {})
    name_to_code: dict[str, str] = {v: k for k, v in teacher_dir.items()}
    # Umožníme reverzní dohledání i pro Jméno Příjmení
    for k, v in list(teacher_dir.items()):
        parts = v.split()
        if len(parts) >= 2:
            reversed_name = f"{parts[-1]} {' '.join(parts[:-1])}"
            name_to_code[reversed_name] = k

    absent_classes: list[AbsentClass] = []
    absent_teachers: list[AbsentTeacher] = []
    closed_rooms: list[ClosedRoom] = []
    class_changes: list[ClassChange] = []
    supervisions: list[ClassSupervision] = []
    unrecognized: list[UnrecognizedItem] = []

    # 3. Zpracování tabulek s třídou 'datagrid'
    datagrids = soup.find_all("table", class_="datagrid")

    # Pomocné předběžné projití spanů s title pro obohacení slovníku zkratek
    for sp in soup.find_all("span"):
        title_val = sp.get("title", "").strip()
        txt = sp.get_text(strip=True)
        # Očistíme případné závorky z textu spanu, např. (So) -> So
        clean_code = re.sub(r"[\(\)]", "", txt).strip()
        if title_val and clean_code and len(clean_code) <= 4:
            clean_name = normalize_teacher_full_name(title_val)
            teacher_dir[clean_code] = title_val
            name_to_code[title_val] = clean_code
            name_to_code[clean_name] = clean_code

    for table in datagrids:
        rows = table.find_all("tr")
        if not rows:
            continue

        header_tr = rows[0]
        header_text = header_tr.get_text(separator=" ", strip=True)

        # A) Nepřítomné třídy
        if "Nepřítomné třídy" in header_text:
            for tr in rows[1:]:
                tds = tr.find_all("td")
                if not tds:
                    continue
                cls_name = _clean_cell_text(tds[0])
                if not cls_name:
                    continue
                hours: dict[int, str] = {}
                for idx, td in enumerate(tds[1:], start=1):
                    txt = _clean_cell_text(td)
                    if txt:
                        hours[idx] = txt
                absent_classes.append(AbsentClass(class_name=cls_name, hours=hours))

        # B) Nepřítomní učitelé
        elif "Nepřítomní učitelé" in header_text:
            for tr in rows[1:]:
                tds = tr.find_all("td")
                if not tds:
                    continue
                t_raw_name = _clean_cell_text(tds[0])
                if not t_raw_name:
                    continue

                norm_name = t_raw_name
                t_code = name_to_code.get(norm_name, "")
                if not t_code:
                    parts = norm_name.split()
                    if len(parts) >= 2:
                        rev = f"{parts[-1]} {' '.join(parts[:-1])}"
                        t_code = name_to_code.get(rev, "")

                hours_dict: dict[int, AbsentTeacherHour] = {}
                for idx, td in enumerate(tds[1:], start=1):
                    span_elem = td.find("span")
                    span = span_elem if isinstance(span_elem, Tag) else None
                    cell_txt = span.get_text(strip=True) if span else _clean_cell_text(td)
                    title_attr = str(span.get("title", "")).strip() if span else ""

                    if not cell_txt:
                        st = TeacherHourStatus.PRESENT
                        sub_code = ""
                        sub_resolved = ""
                    elif cell_txt == "-":
                        st = TeacherHourStatus.ABSENT_FREE
                        sub_code = ""
                        sub_resolved = ""
                    elif cell_txt in ("..", "...", "...."):
                        st = TeacherHourStatus.ABSENT_CANCELLED
                        sub_code = ""
                        sub_resolved = ""
                    else:
                        st = TeacherHourStatus.ABSENT_SUBSTITUTED
                        sub_code = cell_txt
                        sub_resolved = title_attr or teacher_dir.get(sub_code, "")
                        if title_attr and sub_code:
                            teacher_dir[sub_code] = title_attr
                            name_to_code[title_attr] = sub_code

                    hours_dict[idx] = AbsentTeacherHour(
                        hour=idx,
                        raw=cell_txt,
                        status=st,
                        sub_teacher_code=sub_code,
                        sub_teacher_resolved=sub_resolved,
                    )

                absent_teachers.append(
                    AbsentTeacher(
                        teacher_full_name=t_raw_name,
                        teacher_normalized_name=norm_name,
                        teacher_code=t_code,
                        hours=hours_dict,
                    )
                )

        # C) Místnosti mimo provoz
        elif "Místnosti mimo provoz" in header_text:
            for tr in rows[1:]:
                tds = tr.find_all("td")
                if not tds:
                    continue
                r_name = _clean_cell_text(tds[0])
                if not r_name:
                    continue
                hours_r: dict[int, str] = {}
                for idx, td in enumerate(tds[1:], start=1):
                    txt = _clean_cell_text(td)
                    if txt:
                        hours_r[idx] = txt
                closed_rooms.append(ClosedRoom(room_name=r_name, hours=hours_r))

        # D) Změny v rozvrzích tříd
        elif "Změny v rozvrzích tříd" in header_text:
            for tr in rows[1:]:
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                class_name = _clean_cell_text(tds[0])
                if not class_name:
                    continue

                inner_table = tds[1].find("table", class_="inner")
                if not isinstance(inner_table, Tag):
                    continue

                for inner_tr in inner_table.find_all("tr"):
                    inner_tds = inner_tr.find_all("td")
                    if not inner_tds:
                        continue

                    # Kontrola celodenní akce / sloučené buňky
                    first_td = inner_tds[0]
                    first_txt = _clean_cell_text(first_td)
                    if len(inner_tds) == 1 or first_td.get("colspan"):
                        m_action = re.match(
                            r"^(\d{1,2})\.\s*-\s*(\d{1,2})\.\s*(?:hod|les)\.?\s*(.+)$",
                            first_txt,
                            re.IGNORECASE,
                        )
                        if m_action:
                            h_from = int(m_action.group(1))
                            h_to = int(m_action.group(2))
                            desc = m_action.group(3).strip()
                            class_changes.append(
                                ClassChange(
                                    date=date_str,
                                    class_name=class_name,
                                    hour_from=h_from,
                                    hour_to=h_to,
                                    subject=desc,
                                    change_type=ChangeType.CELODENNI_AKCE,
                                    change_type_raw="celodenní akce",
                                    note=desc,
                                    raw_row_text=first_txt,
                                )
                            )
                        else:
                            unrecognized.append(
                                UnrecognizedItem(
                                    date=date_str,
                                    section="Změny v rozvrzích tříd",
                                    raw_content=first_txt,
                                    reason="Nerozpoznaný formát jednořádkové akce",
                                )
                            )
                        continue

                    # Standardní 7-sloupcový řádek
                    m_hour = re.match(r"^(\d{1,2})\.\s*(?:hod|les)\.?", first_txt, re.IGNORECASE)
                    if not m_hour:
                        m_hour_range = re.match(
                            r"^(\d{1,2})\.\s*-\s*(\d{1,2})\.\s*(?:hod|les)\.?",
                            first_txt,
                            re.IGNORECASE,
                        )
                        if m_hour_range:
                            h_from = int(m_hour_range.group(1))
                            h_to = int(m_hour_range.group(2))
                        else:
                            unrecognized.append(
                                UnrecognizedItem(
                                    date=date_str,
                                    section="Změny v rozvrzích tříd",
                                    raw_content=inner_tr.get_text(separator=" ", strip=True),
                                    reason=f"Nerozpoznaná hodina: {first_txt!r}",
                                )
                            )
                            continue
                    else:
                        h_from = int(m_hour.group(1))
                        h_to = h_from

                    subj = _clean_cell_text(inner_tds[1]) if len(inner_tds) > 1 else ""
                    grp = _clean_cell_text(inner_tds[2]) if len(inner_tds) > 2 else ""
                    rm = _clean_cell_text(inner_tds[3]) if len(inner_tds) > 3 else ""
                    ch_type_raw = _clean_cell_text(inner_tds[4]) if len(inner_tds) > 4 else ""

                    # Suplující učitel
                    sub_td = inner_tds[5] if len(inner_tds) > 5 else None
                    sub_span_elem = sub_td.find("span") if sub_td else None
                    sub_span = sub_span_elem if isinstance(sub_span_elem, Tag) else None
                    sub_code = (
                        sub_span.get_text(strip=True)
                        if sub_span
                        else (_clean_cell_text(sub_td) if sub_td else "")
                    ).strip()
                    sub_title = str(sub_span.get("title", "")).strip() if sub_span else ""

                    sub_teacher_name = ""
                    if sub_title:
                        sub_teacher_name = sub_title
                        if sub_code:
                            teacher_dir[sub_code] = sub_title
                            name_to_code[sub_title] = sub_code
                    elif sub_code:
                        sub_teacher_name = teacher_dir.get(sub_code, sub_code)

                    # Původní učitel
                    orig_td = inner_tds[6] if len(inner_tds) > 6 else None
                    orig_span_elem = orig_td.find("span") if orig_td else None
                    orig_span = orig_span_elem if isinstance(orig_span_elem, Tag) else None
                    orig_raw = (
                        orig_span.get_text(strip=True)
                        if orig_span
                        else (_clean_cell_text(orig_td) if orig_td else "")
                    ).strip()
                    orig_title = str(orig_span.get("title", "")).strip() if orig_span else ""

                    orig_code = re.sub(r"[\(\)]", "", orig_raw).strip()
                    orig_resolved = ""
                    if orig_title:
                        orig_resolved = normalize_teacher_full_name(orig_title)
                        if orig_code:
                            teacher_dir[orig_code] = orig_resolved
                            name_to_code[orig_resolved] = orig_code
                    elif orig_code:
                        orig_resolved = teacher_dir.get(orig_code, "")

                    room_changed = bool(rm)
                    sub_changed = bool(sub_teacher_name or sub_code)
                    c_type = _classify_change_type(
                        raw_type=ch_type_raw,
                        room_changed=room_changed,
                        sub_teacher_changed=sub_changed,
                        orig_teacher_code=orig_code,
                    )

                    class_changes.append(
                        ClassChange(
                            date=date_str,
                            class_name=class_name,
                            hour_from=h_from,
                            hour_to=h_to,
                            subject=subj,
                            group_name=grp,
                            room=rm,
                            room_changed=room_changed,
                            change_type=c_type,
                            change_type_raw=ch_type_raw,
                            sub_teacher=sub_teacher_name,
                            sub_teacher_changed=sub_changed,
                            orig_teacher_code=orig_code,
                            orig_teacher_resolved=orig_resolved,
                            note=ch_type_raw,
                            raw_row_text=inner_tr.get_text(separator=" ", strip=True),
                        )
                    )

    now_dt = datetime.now(PRAGUE_TZ)
    now_iso = now_dt.isoformat(timespec="seconds")
    exp_disp = f"{now_dt.day}. {now_dt.month}. {now_dt.year} {now_dt.hour:02d}:{now_dt.minute:02d}"
    day = ScheduleDay(
        date=date_str,
        day_name=day_name,
        week_label="",
        school_name=school_name,
        exported_at=now_iso,
        exported_at_display=exp_disp,
        data_source="web",
        source_label="Web (klasifikace.skolakrizik.cz)",
        fetched_at=now_iso,
        absent_classes=absent_classes,
        absent_teachers=absent_teachers,
        closed_rooms=closed_rooms,
        class_changes=class_changes,
        supervisions=supervisions,
        unrecognized=unrecognized,
    )

    _pair_moves_in_day(day)
    corr_codes, _ = _correlate_teachers([day])
    for c, n in corr_codes.items():
        teacher_dir.setdefault(c, n)
    day.derived_teachers = build_derived_teachers(day, teacher_dir)

    return ParseResult(
        file_name="zmeny.aspx",
        detected_encoding=detected_encoding,
        exported_at=now_iso,
        school_name=school_name,
        days=[day],
        teacher_directory=teacher_dir,
        unrecognized=unrecognized,
    )
