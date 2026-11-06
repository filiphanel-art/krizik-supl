"""Datové modely pro Suplování Viewer."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ChangeType(StrEnum):
    """Normalizované typy změn v rozvrhu."""

    SUPLOVANI = "SUPLOVANI"
    ODPADA = "ODPADA"
    SPOJENO = "SPOJENO"
    ZMENA_UCEBNY = "ZMENA_UCEBNY"
    PRESUN_NA = "PRESUN_NA"
    PRESUN_Z = "PRESUN_Z"
    NAVIC = "NAVIC"
    VYMENA = "VYMENA"
    CELODENNI_AKCE = "CELODENNI_AKCE"
    OSTATNI = "OSTATNI"


class TeacherHourStatus(StrEnum):
    """Význam buňky v mřížce Nepřítomní učitelé."""

    PRESENT = "PRESENT"
    ABSENT_FREE = "ABSENT_FREE"  # "-"
    ABSENT_CANCELLED = "ABSENT_CANCELLED"  # ".."
    ABSENT_SUBSTITUTED = "ABSENT_SUBSTITUTED"  # zkratka učitele, např. "Vl"
    UNRECOGNIZED = "UNRECOGNIZED"


class AbsentTeacherHour(BaseModel):
    """Stav jedné vyučovací hodiny nepřítomného učitele."""

    hour: int
    raw: str
    status: TeacherHourStatus
    sub_teacher_code: str = ""
    sub_teacher_resolved: str = ""


class AbsentClass(BaseModel):
    """Záznam nepřítomné třídy v daném dni (mřížka 1..10)."""

    class_name: str
    hours: dict[int, str] = Field(default_factory=dict)


class AbsentTeacher(BaseModel):
    """Záznam nepřítomného učitele v daném dni (mřížka 1..10)."""

    teacher_full_name: str
    teacher_normalized_name: str
    teacher_code: str = ""
    hours: dict[int, AbsentTeacherHour] = Field(default_factory=dict)


class ClosedRoom(BaseModel):
    """Záznam učebny mimo provoz v daném dni (mřížka 1..10)."""

    room_name: str
    hours: dict[int, str] = Field(default_factory=dict)


class ClassSupervision(BaseModel):
    """Záznam pedagogického dohledu u třídy."""

    class_name: str
    hour_from: int
    hour_to: int
    teachers_text: str
    raw_text: str = ""


class ClassChange(BaseModel):
    """Jeden řádek změny v rozvrhu třídy."""

    id: int | None = None
    date: str
    class_name: str
    hour_from: int
    hour_to: int
    subject: str = ""
    group_name: str = ""
    room: str = ""
    room_changed: bool = False
    change_type: ChangeType
    change_type_raw: str = ""
    sub_teacher: str = ""
    sub_teacher_changed: bool = False
    orig_teacher_code: str = ""
    orig_teacher_resolved: str = ""
    note: str = ""
    paired_hour: int | None = None
    paired_change_id: int | None = None
    raw_row_text: str = ""


class UnrecognizedItem(BaseModel):
    """Nerozpoznaný řádek nebo buňka z HTML exportu."""

    date: str = ""
    section: str = ""
    raw_content: str
    reason: str


class DerivedTeacherEntry(BaseModel):
    """Odvozený záznam změny z pohledu učitele."""

    teacher_key: str
    teacher_display: str
    teacher_code: str = ""
    role: str  # "supluje" | "chybí" | "přesun" | "změna učebny" | "dohled" | "navíc" | "spojeno"
    hour_from: int
    hour_to: int
    class_name: str
    subject: str = ""
    group_name: str = ""
    room: str = ""
    change_type: ChangeType
    change_type_raw: str = ""
    counterpart_teacher: str = ""
    note: str = ""


class ScheduleDay(BaseModel):
    """Kompletní data suplování pro jeden den."""

    date: str  # YYYY-MM-DD
    day_name: str
    week_label: str = ""
    school_name: str = ""
    exported_at: str = ""  # ISO 8601
    exported_at_display: str = ""
    data_source: str = "file"  # "file" | "web"
    source_label: str = "Soubor (Bakaláři export)"
    fetched_at: str = ""  # ISO 8601
    absent_classes: list[AbsentClass] = Field(default_factory=list)
    absent_teachers: list[AbsentTeacher] = Field(default_factory=list)
    closed_rooms: list[ClosedRoom] = Field(default_factory=list)
    class_changes: list[ClassChange] = Field(default_factory=list)
    supervisions: list[ClassSupervision] = Field(default_factory=list)
    unrecognized: list[UnrecognizedItem] = Field(default_factory=list)
    derived_teachers: list[DerivedTeacherEntry] = Field(default_factory=list)


class ParseResult(BaseModel):
    """Výsledek zpracování celého HTML souboru."""

    file_name: str
    detected_encoding: str
    exported_at: str
    school_name: str
    days: list[ScheduleDay] = Field(default_factory=list)
    teacher_directory: dict[str, str] = Field(default_factory=dict)  # code -> "Příjmení Jméno"
    teacher_titles: dict[str, str] = Field(default_factory=dict)  # "Příjmení Jméno" -> "Titul Jméno Příjmení"
    unrecognized: list[UnrecognizedItem] = Field(default_factory=list)
