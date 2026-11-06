"""Unit testy pro HTML parser suplování (Fáze 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models import ChangeType, TeacherHourStatus
from app.parser import ParseError, detect_and_decode, parse_suplovani_html

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def test_parse_all_samples_in_directory() -> None:
    """Ověří, že každý HTML soubor ve složce samples/ se úspěšně zparsuje."""
    sample_files = sorted(SAMPLES_DIR.glob("*.html"))
    assert len(sample_files) >= 2
    for sample_path in sample_files:
        raw = sample_path.read_bytes()
        res = parse_suplovani_html(raw, file_name=sample_path.name)
        assert len(res.days) >= 1
        assert "Křižík" in res.school_name


def test_real_sample_suplprehtrid_structure() -> None:
    """Testuje detailní rozbor reálného vzorku samples/suplprehtrid.html."""
    raw = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res = parse_suplovani_html(raw, file_name="suplprehtrid.html")

    # 5 dnů: Po 2. 11. až Pá 6. 11. 2026
    assert [d.date for d in res.days] == [
        "2026-11-02",
        "2026-11-03",
        "2026-11-04",
        "2026-11-05",
        "2026-11-06",
    ]
    assert res.exported_at == "2026-11-05T08:26:00+01:00"
    assert "Františka Křižíka" in res.school_name
    assert len(res.unrecognized) == 0

    # Ověření všech typů změn v reálném vzorku
    found_types = {ch.change_type for d in res.days for ch in d.class_changes}
    assert ChangeType.SUPLOVANI in found_types
    assert ChangeType.ODPADA in found_types
    assert ChangeType.SPOJENO in found_types
    assert ChangeType.ZMENA_UCEBNY in found_types
    assert ChangeType.NAVIC in found_types
    assert ChangeType.PRESUN_NA in found_types
    assert ChangeType.PRESUN_Z in found_types
    assert ChangeType.CELODENNI_AKCE in found_types


def test_full_day_actions_modeled_as_hour_range() -> None:
    """Celodenní akce (Souvislá praxe, Exkurze) musí být modelovány jako rozsah hodin 1..7."""
    raw = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res = parse_suplovani_html(raw)

    thursday = next(d for d in res.days if d.date == "2026-11-05")
    actions = [
        ch for ch in thursday.class_changes if ch.change_type == ChangeType.CELODENNI_AKCE
    ]
    assert len(actions) == 2

    exkurze = next(a for a in actions if a.class_name == "3B")
    assert exkurze.hour_from == 1
    assert exkurze.hour_to == 7
    assert exkurze.note == "Exkurze"

    praxe = next(a for a in actions if a.class_name == "V2")
    assert praxe.hour_from == 1
    assert praxe.hour_to == 7
    assert praxe.note == "Souvislá praxe"


def test_paired_moves_in_thursday() -> None:
    """Přesuny ('přesun >>' na X. hod a 'přesun <<' z Y. hod) musí být spárovány."""
    raw = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res = parse_suplovani_html(raw)
    thursday = next(d for d in res.days if d.date == "2026-11-05")

    # 1A: 1. hod -> 4. hod (Dě, Fox Luděk)
    moves_1a = [
        ch
        for ch in thursday.class_changes
        if ch.class_name == "1A"
        and ch.change_type in (ChangeType.PRESUN_NA, ChangeType.PRESUN_Z)
    ]
    assert len(moves_1a) == 2
    m_from, m_to = moves_1a[0], moves_1a[1]
    assert m_from.hour_from == 1 and m_from.paired_hour == 4
    assert m_to.hour_from == 4 and m_to.paired_hour == 1
    assert m_from.sub_teacher == "Fox Luděk"

    # V1: 7. hod -> 3. hod (Emt, Novák Zdeněk) - v tabulce je 3. hod před 7. hod!
    moves_v1 = [
        ch
        for ch in thursday.class_changes
        if ch.class_name == "V1"
        and ch.change_type in (ChangeType.PRESUN_NA, ChangeType.PRESUN_Z)
    ]
    assert len(moves_v1) == 2
    v1_target = next(m for m in moves_v1 if m.hour_from == 3)
    v1_source = next(m for m in moves_v1 if m.hour_from == 7)
    assert v1_target.change_type == ChangeType.PRESUN_Z
    assert v1_target.paired_hour == 7
    assert v1_source.change_type == ChangeType.PRESUN_NA
    assert v1_source.paired_hour == 3
    assert v1_source.sub_teacher == "Novák Zdeněk"


def test_absent_teachers_grid_and_derived_teachers() -> None:
    """Ověří interpretaci mřížky Nepřítomní učitelé ('-', '..', zkratka) a odvozený pohled."""
    raw = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res = parse_suplovani_html(raw)

    monday = res.days[0]
    assert len(monday.absent_teachers) == 1
    kodad = monday.absent_teachers[0]
    assert kodad.teacher_full_name == "Ing. Miloš Kodad"
    assert kodad.teacher_normalized_name == "Kodad Miloš"
    assert kodad.teacher_code == "Ko"
    assert kodad.hours[1].status == TeacherHourStatus.ABSENT_FREE
    assert kodad.hours[4].status == TeacherHourStatus.ABSENT_SUBSTITUTED
    assert kodad.hours[4].sub_teacher_code == "Vl"
    assert kodad.hours[4].sub_teacher_resolved == "Valtr Pavel"
    assert kodad.hours[7].status == TeacherHourStatus.ABSENT_CANCELLED

    # Odvozený pohled podle učitelů v pondělí
    derived_names = {d.teacher_key for d in monday.derived_teachers}
    assert "Valtr Pavel" in derived_names
    assert "Kodad Miloš" in derived_names
    assert "Šebková Blanka" in derived_names


def test_cp1250_encoding_and_diacritics() -> None:
    """Ověří správnou detekci cp1250 a zobrazení 'Křižík', 'Čermáková', 'Řehořová'."""
    raw = (SAMPLES_DIR / "supl_cp1250_vymena.html").read_bytes()
    res = parse_suplovani_html(raw, file_name="supl_cp1250_vymena.html")

    assert res.detected_encoding.lower() in ("cp1250", "windows-1250")
    assert "Františka Křižíka" in res.school_name
    day = res.days[0]
    assert day.absent_teachers[0].teacher_full_name == "Mgr. Jana Čermáková"
    assert day.absent_teachers[0].teacher_normalized_name == "Čermáková Jana"

    sub_names = [ch.sub_teacher for ch in day.class_changes if ch.sub_teacher]
    assert "Řehořová Šárka" in sub_names
    assert "Křižík František" in sub_names

    vymena = next(ch for ch in day.class_changes if ch.change_type == ChangeType.VYMENA)
    assert vymena.subject == "Fy"
    assert vymena.sub_teacher == "Křižík František"

    # Test cp1250 i v případě, že v hlavičce HTML je lživě uvedeno charset=utf-8
    misleading_html = raw.replace(b"charset=windows-1250", b"charset=utf-8")
    decoded_text, enc = detect_and_decode(misleading_html)
    assert "Čermáková" in decoded_text
    assert "Křižík" in decoded_text
    assert enc.lower() in ("cp1250", "windows-1250")


def test_unrecognized_rows_and_cells_are_preserved() -> None:
    """Nerozpoznané řádky a buňky v mřížce učitelů se nesmí zahodit – uloží se do unrecognized."""
    html = """<!DOCTYPE html>
    <html><body>
    <table>
      <tr><td>Suplování:</td><td>Pátek 6. 11. 2026</td><td>(2. týden)</td></tr>
      <tr><td>SPŠE Františka Křižíka</td><td>datum výpisu: 6. 11. 2026, 09:00</td></tr>
      <tr><td>Nepřítomní učitelé</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td>9</td><td>10</td></tr>
      <tr><td>Mgr. Jana Čermáková</td><td>???</td><td>-</td><td>..</td><td>Vl</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
      <tr><td>Změny v rozvrzích tříd</td><td></td><td></td><td></td><td></td><td></td></tr>
      <tr><td>1A</td><td>neznámá_hodina</td><td>Ma</td><td></td><td>(1)</td><td>supluje</td><td>Novák Jan</td><td>(Čm)</td></tr>
      <tr><td>Podivný řádek s jednou buňkou</td><td>druhá buňka</td></tr>
    </table>
    </body></html>"""
    res = parse_suplovani_html(html.encode("cp1250"))
    assert len(res.days) == 1
    day = res.days[0]
    assert day.absent_teachers[0].hours[1].status == TeacherHourStatus.UNRECOGNIZED
    assert len(day.unrecognized) == 3
    reasons = " | ".join(u.reason for u in day.unrecognized)
    assert "Nerozpoznaný symbol v mřížce" in reasons
    assert "Nerozpoznaná vyučovací hodina" in reasons
    assert "Nerozpoznaný formát řádku" in reasons


def test_corrupted_or_empty_html_raises_parse_error() -> None:
    """Prázdný soubor, binární šum nebo HTML bez tabulek vyhodí ParseError."""
    with pytest.raises(ParseError):
        parse_suplovani_html(b"")

    with pytest.raises(ParseError):
        parse_suplovani_html(b"<html><body><p>Jen odstavec bez tabulky</p></body></html>")

    with pytest.raises(ParseError):
        parse_suplovani_html(b"<html><body><table><tr><td>Cizi tabulka</td></tr></table></body></html>")

    with pytest.raises(ParseError):
        parse_suplovani_html(b"a" * 2048, max_size_bytes=1024)


def test_teachers_dict_01() -> None:
    """TEST-TEACHERS-DICT-01: Načtení 55 učitelů z konfigurace teacher_codes."""
    from app.config import load_config

    cfg = load_config()
    assert len(cfg.teacher_codes) == 55
    assert cfg.teacher_codes["Ko"] == "Kodad Miloš"
    assert cfg.teacher_codes["Vl"] == "Valtr Pavel"
    assert cfg.teacher_codes["Hf"] == "Hanel Filip"
    assert cfg.teacher_codes["Bj"] == "Bajerová Markéta"
    assert cfg.teacher_codes["Št"] == "Šťastný Ondřej"


def test_web_parse_01() -> None:
    """TEST-WEB-PARSE-01: Parsování reálného souboru samples/zmeny_web_sample.html."""
    from app.parser_web import parse_web_zmeny_html

    raw = (SAMPLES_DIR / "zmeny_web_sample.html").read_bytes()
    res = parse_web_zmeny_html(raw)
    assert len(res.days) == 1
    day = res.days[0]
    assert day.date == "2026-11-06"
    assert day.day_name == "Pátek"
    assert day.data_source == "web"
    assert day.source_label == "Web (klasifikace.skolakrizik.cz)"
    assert "Křižík" in day.school_name

    # Extrahovány třídy, učitelé i místnosti
    assert len(day.absent_classes) >= 1
    assert any(ac.class_name == "V2" for ac in day.absent_classes)

    assert len(day.absent_teachers) >= 5
    absent_teacher_names = {at.teacher_full_name for at in day.absent_teachers}
    assert "Hanel Filip" in absent_teacher_names
    assert "Kodad Miloš" in absent_teacher_names
    assert "Maňák Tomáš" in absent_teacher_names

    assert len(day.closed_rooms) >= 1
    assert any(cr.room_name == "7" for cr in day.closed_rooms)

    # Všechny změny v rozvrzích tříd (1A, 1B, 4D, V2) naparsovány
    classes_in_changes = {ch.class_name for ch in day.class_changes}
    assert {"1A", "1B", "4D", "V2"}.issubset(classes_in_changes)

    # 1A má odpadající Ma a spojenou Aj
    ch_1a = [ch for ch in day.class_changes if ch.class_name == "1A"]
    assert any(ch.subject == "Ma" and ch.change_type == ChangeType.ODPADA for ch in ch_1a)
    assert any(ch.subject == "Aj" and ch.change_type == ChangeType.SPOJENO for ch in ch_1a)

    # V2 má celodenní praxi
    ch_v2 = [ch for ch in day.class_changes if ch.class_name == "V2"]
    assert len(ch_v2) == 1
    assert ch_v2[0].hour_from == 1 and ch_v2[0].hour_to == 7
    assert ch_v2[0].change_type == ChangeType.CELODENNI_AKCE
    assert "praxe" in ch_v2[0].subject.lower() or "praxe" in ch_v2[0].note.lower()


def test_web_parse_02() -> None:
    """TEST-WEB-PARSE-02: Parsování titulkových atributů title u učitelů."""
    from app.parser_web import parse_web_zmeny_html

    raw = (SAMPLES_DIR / "zmeny_web_sample.html").read_bytes()
    res = parse_web_zmeny_html(raw)
    assert res.teacher_directory.get("Ba") == "Blažek Martin"
    assert res.teacher_directory.get("Le") == "Ledvina David"
    assert res.teacher_directory.get("Pl") == "Poul Richard"
    assert res.teacher_directory.get("Vl") == "Valtr Pavel"
    assert res.teacher_directory.get("Nz") == "Novák Zdeněk"

