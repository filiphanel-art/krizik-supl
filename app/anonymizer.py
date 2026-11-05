"""Anonymizace osobních údajů učitelů pro veřejné zobrazení a statický export (F7)."""

from __future__ import annotations

import re

from app.models import (
    AbsentTeacher,
    AbsentTeacherHour,
    ClassChange,
    ClassSupervision,
    DerivedTeacherEntry,
    ScheduleDay,
    UnrecognizedItem,
)
from app.parser import ACADEMIC_TITLES, normalize_teacher_full_name

SAFE_NOTE_RE = re.compile(
    r"^(?:(?:na|z)\s+\d{1,2}\.\s*hod|Souvislá praxe|Exkurze|Praxe|Sportovní kurz|Lyžařský kurz)$",
    re.IGNORECASE,
)


def name_to_initials(name: str) -> str:
    """Převede 'Příjmení Jméno' nebo 'Titul Jméno Příjmení' na iniciály (např. 'V. P.')."""
    cleaned = re.sub(r"[,]", " ", name).strip()
    if not cleaned:
        return ""
    tokens: list[str] = []
    for tok in cleaned.split():
        stripped = tok.strip(".").lower()
        if stripped in ACADEMIC_TITLES or tok.lower() in {"ph.d.", "cs.c.", "di.s."}:
            continue
        if tok and tok[0].isalpha():
            tokens.append(f"{tok[0].upper()}.")
    return " ".join(tokens) if tokens else "—"


def _anonymize_teacher_label(
    name: str,
    name_to_code: dict[str, str],
    fallback_code: str = "",
) -> str:
    """Vrátí zkratku učitele (pokud je známa) nebo iniciály."""
    if fallback_code:
        return fallback_code
    norm = normalize_teacher_full_name(name) if "." in name else name.strip()
    if norm in name_to_code:
        return name_to_code[norm]
    if name.strip() in name_to_code:
        return name_to_code[name.strip()]
    return name_to_initials(name)


def sanitize_note(note: str, forbidden_tokens: set[str]) -> str:
    """Odstraní případné osobní údaje z poznámky."""
    if not note:
        return ""
    if SAFE_NOTE_RE.match(note.strip()):
        return note.strip()
    # Pokud poznámka obsahuje některé ze známých jmen/příjmení, nahradíme ji obecným textem
    low = note.lower()
    for tok in forbidden_tokens:
        if len(tok) >= 3 and tok.lower() in low:
            return "[poznámka skryta]"
    return "[poznámka skryta]"


def collect_name_tokens(day: ScheduleDay, code_to_name: dict[str, str]) -> set[str]:
    """Shromáždí všechna jména a příjmení učitelů vyskytující se v daném dni a slovníku."""
    raw_names: set[str] = set(code_to_name.values())
    for at in day.absent_teachers:
        raw_names.add(at.teacher_full_name)
        raw_names.add(at.teacher_normalized_name)
        for cell in at.hours.values():
            if cell.sub_teacher_resolved:
                raw_names.add(cell.sub_teacher_resolved)
    for ch in day.class_changes:
        if ch.sub_teacher:
            raw_names.add(ch.sub_teacher)
        if ch.orig_teacher_resolved:
            raw_names.add(ch.orig_teacher_resolved)
    for sup in day.supervisions:
        for part in sup.teachers_text.split(","):
            if part.strip():
                raw_names.add(part.strip())

    tokens: set[str] = set()
    for full in raw_names:
        for piece in re.split(r"[\s,]+", full):
            clean = piece.strip(".")
            if len(clean) >= 3 and clean.lower() not in ACADEMIC_TITLES:
                tokens.add(clean)
    return tokens


def anonymize_schedule_day(
    day: ScheduleDay,
    code_to_name: dict[str, str] | None = None,
) -> ScheduleDay:
    """Vytvoří hlubokou kopii ScheduleDay zbavenou všech plných jmen a osobních poznámek (F7)."""
    code_map = code_to_name or {}
    name_to_code = {v: k for k, v in code_map.items()}
    forbidden = collect_name_tokens(day, code_map)

    anon_absent_teachers: list[AbsentTeacher] = []
    for at in day.absent_teachers:
        label = _anonymize_teacher_label(
            at.teacher_normalized_name or at.teacher_full_name,
            name_to_code,
            fallback_code=at.teacher_code,
        )
        anon_hours: dict[int, AbsentTeacherHour] = {}
        for h, cell in at.hours.items():
            anon_hours[h] = AbsentTeacherHour(
                hour=cell.hour,
                raw=cell.raw,
                status=cell.status,
                sub_teacher_code=cell.sub_teacher_code,
                sub_teacher_resolved="",
            )
        anon_absent_teachers.append(
            AbsentTeacher(
                teacher_full_name=label,
                teacher_normalized_name=label,
                teacher_code=at.teacher_code or label,
                hours=anon_hours,
            )
        )

    anon_changes: list[ClassChange] = []
    for ch in day.class_changes:
        sub_anon = (
            _anonymize_teacher_label(ch.sub_teacher, name_to_code) if ch.sub_teacher else ""
        )
        orig_anon = ch.orig_teacher_code or (
            _anonymize_teacher_label(ch.orig_teacher_resolved, name_to_code)
            if ch.orig_teacher_resolved
            else ""
        )
        anon_changes.append(
            ClassChange(
                id=ch.id,
                date=ch.date,
                class_name=ch.class_name,
                hour_from=ch.hour_from,
                hour_to=ch.hour_to,
                subject=ch.subject,
                group_name=ch.group_name,
                room=ch.room,
                room_changed=ch.room_changed,
                change_type=ch.change_type,
                change_type_raw=ch.change_type_raw,
                sub_teacher=sub_anon,
                sub_teacher_changed=ch.sub_teacher_changed,
                orig_teacher_code=orig_anon,
                orig_teacher_resolved="",
                note=sanitize_note(ch.note, forbidden),
                paired_hour=ch.paired_hour,
                paired_change_id=ch.paired_change_id,
                raw_row_text="",
            )
        )

    anon_supervisions: list[ClassSupervision] = []
    for sup in day.supervisions:
        parts = [p.strip() for p in sup.teachers_text.split(",") if p.strip()]
        anon_parts = [_anonymize_teacher_label(p, name_to_code) for p in parts]
        anon_supervisions.append(
            ClassSupervision(
                class_name=sup.class_name,
                hour_from=sup.hour_from,
                hour_to=sup.hour_to,
                teachers_text=", ".join(anon_parts),
                raw_text="",
            )
        )

    anon_derived: list[DerivedTeacherEntry] = []
    for d in day.derived_teachers:
        t_code = d.teacher_code or _anonymize_teacher_label(d.teacher_key, name_to_code)
        cp_anon = ""
        if d.counterpart_teacher:
            # Pokud má tvar "Jméno (Zk)", vezmeme jen "(Zk)" nebo iniciály
            m_paren = re.search(r"\(([^)]+)\)", d.counterpart_teacher)
            if m_paren:
                cp_anon = f"({m_paren.group(1)})"
            else:
                cp_anon = _anonymize_teacher_label(d.counterpart_teacher, name_to_code)
        anon_derived.append(
            DerivedTeacherEntry(
                teacher_key=t_code,
                teacher_display=t_code,
                teacher_code=t_code,
                role=d.role,
                hour_from=d.hour_from,
                hour_to=d.hour_to,
                class_name=d.class_name,
                subject=d.subject,
                group_name=d.group_name,
                room=d.room,
                change_type=d.change_type,
                change_type_raw=d.change_type_raw,
                counterpart_teacher=cp_anon,
                note=sanitize_note(d.note, forbidden),
            )
        )
    anon_derived.sort(key=lambda e: (e.teacher_key.lower(), e.hour_from, e.class_name))

    anon_unrecognized: list[UnrecognizedItem] = []
    for u in day.unrecognized:
        redacted = u.raw_content
        for tok in forbidden:
            if tok:
                redacted = re.sub(re.escape(tok), "[redigováno]", redacted, flags=re.IGNORECASE)
        anon_unrecognized.append(
            UnrecognizedItem(
                date=u.date,
                section=u.section,
                raw_content=redacted,
                reason=u.reason,
            )
        )

    return ScheduleDay(
        date=day.date,
        day_name=day.day_name,
        week_label=day.week_label,
        school_name=day.school_name,
        exported_at=day.exported_at,
        exported_at_display=day.exported_at_display,
        absent_classes=list(day.absent_classes),
        absent_teachers=anon_absent_teachers,
        closed_rooms=list(day.closed_rooms),
        class_changes=anon_changes,
        supervisions=anon_supervisions,
        unrecognized=anon_unrecognized,
        derived_teachers=anon_derived,
    )
