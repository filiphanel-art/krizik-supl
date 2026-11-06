"""Testy webového rozhraní, PWA, bezpečnostních hlaviček, anonymizace a export-static (Fáze 4 a 5)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.anonymizer import collect_name_tokens
from app.cli import main as cli_main
from app.config import AppConfig
from app.parser import parse_suplovani_html
from app.web import create_app

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def test_web_endpoints_pwa_and_security_headers(tmp_path: Path) -> None:
    """Ověří hlavní stránku, PWA manifest, service worker, API a bezpečnostní hlavičky CSP."""
    watch_dir = tmp_path / "exports"
    watch_dir.mkdir()
    shutil.copy2(SAMPLES_DIR / "suplprehtrid.html", watch_dir / "suplprehtrid.html")

    cfg = AppConfig(
        watch_dir=watch_dir,
        db_path=tmp_path / "supl.db",
        log_dir=tmp_path / "logs",
        stability_seconds=0.0,
    )
    app = create_app(config=cfg, start_watcher=False)

    with TestClient(app) as client:
        # 1) Hlavní stránka + bezpečnostní hlavičky
        r_index = client.get("/")
        assert r_index.status_code == 200
        assert "Přehled suplování" in r_index.text
        assert r_index.headers["X-Content-Type-Options"] == "nosniff"
        assert "default-src 'self'" in r_index.headers["Content-Security-Policy"]

        # 2) PWA soubory (manifest, service worker, ikony)
        assert client.get("/manifest.json").status_code == 200
        assert client.get("/sw.js").status_code == 200
        assert client.get("/icon-192.png").status_code == 200
        assert client.get("/nonexistent.js").status_code == 404

        # 3) API rozvrhu
        r_sched = client.get("/api/schedule?date=2026-11-05")
        assert r_sched.status_code == 200
        payload = r_sched.json()
        assert len(payload["dates"]) == 5
        assert payload["selected_date"] == "2026-11-05"
        assert payload["day"]["day_name"] == "Čtvrtek"
        assert len(payload["day"]["class_changes"]) == 38
        assert len(payload["day"]["supervisions"]) == 1

        # 4) /admin/status
        r_admin = client.get("/admin/status")
        assert r_admin.status_code == 200
        assert "Správa a stav systému" in r_admin.text
        assert "suplprehtrid.html" in r_admin.text


def test_admin_basic_auth_protection(tmp_path: Path) -> None:
    """Ověří, že při nastavení hesla je /admin/status chráněn HTTP Basic autentizací (F8)."""
    cfg = AppConfig(
        watch_dir=tmp_path / "exports",
        db_path=tmp_path / "supl.db",
        log_dir=tmp_path / "logs",
        admin_username="spravce",
        admin_password="tajne-heslo-123",
        stability_seconds=0.0,
    )
    app = create_app(config=cfg, start_watcher=False)

    with TestClient(app) as client:
        # Bez přihlášení -> 401
        r_unauth = client.get("/admin/status")
        assert r_unauth.status_code == 401

        # Špatné heslo -> 401
        r_wrong = client.get("/admin/status", auth=("spravce", "spatne"))
        assert r_wrong.status_code == 401

        # Správné přihlášení -> 200
        r_ok = client.get("/admin/status", auth=("spravce", "tajne-heslo-123"))
        assert r_ok.status_code == 200


def test_static_export_contains_zero_personal_names(tmp_path: Path) -> None:
    """Automaticky ověří, že dist/ neobsahuje žádné jméno ani příjmení učitele ze vstupních vzorků (F7)."""
    watch_dir = tmp_path / "exports"
    watch_dir.mkdir()

    # Zkopírujeme všechny vzorky do sledované složky a posbíráme všechna jména a příjmení učitelů
    all_forbidden_names: set[str] = set()
    for sample_file in sorted(SAMPLES_DIR.glob("*.html")):
        shutil.copy2(sample_file, watch_dir / sample_file.name)
        parsed = parse_suplovani_html(sample_file.read_bytes(), file_name=sample_file.name)
        for day in parsed.days:
            all_forbidden_names.update(collect_name_tokens(day, parsed.teacher_directory))

    # Ujistíme se, že v testovací množině jsou skutečná jména ze vzorků (vč. nahlášených s diakritikou)
    # Pozn.: "Křižík" je v názvu školy ("SPŠE Františka Křižíka"), proto kontrolujeme celá jména učitelů
    # i příjmení všech reálných vyučujících.
    teacher_full_names = {
        "Valtr Pavel",
        "Miloš Kodad",
        "Kodad Miloš",
        "Šebková Blanka",
        "Rottová Renata",
        "Poul Richard",
        "Novák Zdeněk",
        "Michael Kudrnáč",
        "Kudrnáč Michael",
        "Šimková Veronika",
        "Ledvina David",
        "Prýmek Josef",
        "Bajerová Markéta",
        "Suchý Zbyněk",
        "Luděk Fox",
        "Fox Luděk",
        "Jakub Hausner",
        "Adam Ryba",
        "Kubečková Marta",
        "Bernardová Radka",
        "Bureš Pavel",
        "Očenášková Marie",
        "Pleskačová Linda",
        "Drchota Viktor",
        "Šťastný Ondřej",
        "Bařinka Lukáš",
        "Hanel Filip",
        "Martin Blažek",
        "Blažek Martin",
        "Tomáš Maňák",
        "Anna Mudruňková",
        "Mudruňková Anna",
        "Jan Pfeifer",
        "Dana Sobotová",
        "Tichá Tereza",
        "Hájek Jiří",
        "Fojtík Filip",
        "Roušová Helena",
        "Jobek Tomáš",
        "Kulhánek Eduard",
        "Prýmková Ivana",
        "Jana Čermáková",
        "Čermáková Jana",
        "Řehořová Šárka",
        "Křižík František",
    }
    teacher_surnames = {
        "Valtr",
        "Kodad",
        "Šebková",
        "Rottová",
        "Poul",
        "Kudrnáč",
        "Šimková",
        "Ledvina",
        "Prýmek",
        "Bajerová",
        "Suchý",
        "Hausner",
        "Ryba",
        "Kubečková",
        "Bernardová",
        "Bureš",
        "Očenášková",
        "Pleskačová",
        "Drchota",
        "Šťastný",
        "Bařinka",
        "Hanel",
        "Blažek",
        "Maňák",
        "Mudruňková",
        "Pfeifer",
        "Sobotová",
        "Tichá",
        "Hájek",
        "Fojtík",
        "Roušová",
        "Jobek",
        "Kulhánek",
        "Prýmková",
        "Čermáková",
        "Řehořová",
    }

    dist_dir = tmp_path / "dist"
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        f"watch_dir: {watch_dir}\ndb_path: {tmp_path / 'supl.db'}\nlog_dir: {tmp_path / 'logs'}\n",
        encoding="utf-8",
    )

    rc = cli_main(["--config", str(cfg_file), "export-static", "--output", str(dist_dir)])
    assert rc == 0
    assert (dist_dir / "index.html").is_file()
    assert (dist_dir / "data" / "index.json").is_file()

    # Projdeme úplně všechny textové soubory v dist/ a ověříme, že neobsahují žádné jméno učitele
    checked_files = 0
    for path in dist_dir.rglob("*"):
        if path.is_file() and path.suffix in (".html", ".json", ".js", ".css"):
            content = path.read_text(encoding="utf-8")
            checked_files += 1
            for full_name in teacher_full_names:
                assert full_name not in content, f"Nalezeno plné jméno {full_name!r} v {path}"
            for surname in teacher_surnames:
                assert surname not in content, f"Nalezeno příjmení {surname!r} v {path}"

    assert checked_files >= 8


def test_upload_export_endpoint(tmp_path: Path) -> None:
    """Ověří funkčnost skrytého upload endpointu /api/upload/{token}."""
    watch_dir = tmp_path / "watch_exports"
    watch_dir.mkdir()
    cfg = AppConfig(
        watch_dir=watch_dir,
        db_path=tmp_path / "supl.db",
        log_dir=tmp_path / "logs",
        upload_token="tajny-token-456",
        stability_seconds=0.0,
    )
    app = create_app(config=cfg, start_watcher=False)

    sample_bytes = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()

    with TestClient(app) as client:
        # 1. Špatný token
        r_bad_token = client.post(
            "/api/upload/spatny-token",
            content=sample_bytes,
            headers={"Content-Type": "text/html; charset=windows-1250"},
        )
        assert r_bad_token.status_code == 401

        # 2. Špatný název souboru
        r_bad_name = client.post(
            "/api/upload/tajny-token-456?filename=jiny_soubor.txt",
            content=sample_bytes,
        )
        assert r_bad_name.status_code == 400

        # 3. Úspěšný upload suplprehtrid.html
        r_ok = client.post(
            "/api/upload/tajny-token-456",
            content=sample_bytes,
            headers={"X-Filename": "suplprehtrid.html"},
        )
        assert r_ok.status_code == 200
        assert r_ok.json()["ok"] is True
        assert (watch_dir / "suplprehtrid.html").is_file()


def test_static_export_injects_static_mode_script(tmp_path: Path) -> None:
    """index.html ve statickém exportu musí načítat static-mode.js před app.js."""
    watch_dir = tmp_path / "exports"
    watch_dir.mkdir()
    shutil.copy2(SAMPLES_DIR / "suplprehtrid.html", watch_dir / "suplprehtrid.html")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        f"watch_dir: {watch_dir}\ndb_path: {tmp_path / 'supl.db'}\nlog_dir: {tmp_path / 'logs'}\n",
        encoding="utf-8",
    )
    dist_dir = tmp_path / "dist"
    assert cli_main(["--config", str(cfg_file), "export-static", "--output", str(dist_dir)]) == 0
    html = (dist_dir / "index.html").read_text(encoding="utf-8")
    assert html.index("static-mode.js") < html.index("app.js")


def _run_node_script(script: str) -> str:
    """Spustí Node.js skript z kořenového adresáře a vrátí standardní výstup."""
    res = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    return res.stdout.strip()


def test_strip_01_no_substituting_teachers() -> None:
    """TEST-STRIP-01: Žádný suplující učitel v daném dni (pouze ODPADA nebo CELODENNI_AKCE) -> <span class="strip-empty">žádní</span>."""
    script = """
    const app = require('./app/static/app.js');
    const changes = [
      { class_name: '1.A', hour_from: 1, hour_to: 1, change_type: 'ODPADA', sub_teacher: '' },
      { class_name: '2.B', hour_from: 2, hour_to: 6, change_type: 'CELODENNI_AKCE', sub_teacher: '' }
    ];
    const subs = app.extractSubstitutingTeachers(changes);
    const day = { absent_teachers: [], class_changes: changes };
    const strip = app.renderGridStrip(day);
    console.log(JSON.stringify({ subs, strip }));
    """
    output = json.loads(_run_node_script(script))
    assert output["subs"] == []

    sub_box = output["strip"]["children"][1]
    assert "strip-sub-teachers" in sub_box["className"]
    pills_container = sub_box["children"][1]
    assert "strip-pills" in pills_container["className"]
    assert len(pills_container["children"]) == 1
    empty_span = pills_container["children"][0]
    assert "strip-empty" in empty_span["className"]
    assert empty_span["textContent"] == "žádní"


def test_strip_02_multiple_non_consecutive_hours() -> None:
    """TEST-STRIP-02: Vícenásobné a nesouvislé hodiny téhož pedagoga (např. 1., 3., 7. hodina)."""
    script = """
    const app = require('./app/static/app.js');
    const changes = [
      { class_name: '1.A', hour_from: 1, hour_to: 1, change_type: 'SUPLOVANI', sub_teacher: 'Novák Zdeněk' },
      { class_name: '2.B', hour_from: 7, hour_to: 7, change_type: 'SUPLOVANI', sub_teacher: 'Novák Zdeněk' },
      { class_name: '3.C', hour_from: 3, hour_to: 3, change_type: 'SUPLOVANI', sub_teacher: 'Novák Zdeněk' },
      { class_name: '4.D', hour_from: 3, hour_to: 3, change_type: 'SPOJENO', sub_teacher: 'Novák Zdeněk' }
    ];
    const subs = app.extractSubstitutingTeachers(changes);
    console.log(JSON.stringify(subs));
    """
    output = json.loads(_run_node_script(script))
    assert len(output) == 1
    assert output[0]["teacher"] == "Novák Zdeněk"
    assert output[0]["hoursText"] == "1., 3., 7. hod"


def test_strip_03_range_compression_consecutive_hours() -> None:
    """TEST-STRIP-03: Souvislý blok suplování (Range Compression): hodiny 2, 3, 4 -> '2.–4. hod'."""
    script = """
    const app = require('./app/static/app.js');
    const r1 = app.formatHoursList([2, 3, 4]);
    const r2 = app.formatHoursList([1, 2, 5]);
    const r3 = app.formatHoursList([1]);
    const r4 = app.formatHoursList([]);
    const changes = [
      { class_name: '1.A', hour_from: 2, hour_to: 4, change_type: 'SUPLOVANI', sub_teacher: 'Valtr Pavel' }
    ];
    const subs = app.extractSubstitutingTeachers(changes);
    console.log(JSON.stringify({ r1, r2, r3, r4, subs }));
    """
    output = json.loads(_run_node_script(script))
    assert output["r1"] == "2.–4. hod"
    assert output["r2"] == "1.–2., 5. hod"
    assert output["r3"] == "1. hod"
    assert output["r4"] == ""
    assert output["subs"][0]["hoursText"] == "2.–4. hod"


def test_strip_04_integration_dom_and_api_strip_blocks(tmp_path: Path) -> None:
    """TEST-STRIP-04: Kompletní vykreslení vzorku suplprehtrid.html (5. 11. 2026).

    Bloky strip-rooms a strip-sup nejsou v DOMu. Jsou přítomny bloky strip-teachers a strip-sub-teachers.
    """
    watch_dir = tmp_path / "exports"
    watch_dir.mkdir()
    shutil.copy2(SAMPLES_DIR / "suplprehtrid.html", watch_dir / "suplprehtrid.html")

    cfg = AppConfig(
        watch_dir=watch_dir,
        db_path=tmp_path / "supl.db",
        log_dir=tmp_path / "logs",
        stability_seconds=0.0,
    )
    app = create_app(config=cfg, start_watcher=False)

    with TestClient(app) as client:
        res = client.get("/api/schedule?date=2026-11-05")
        assert res.status_code == 200
        payload = res.json()
        day_data = payload["day"]

        script = f"""
        const app = require('./app/static/app.js');
        const day = {json.dumps(day_data)};
        const strip = app.renderGridStrip(day);
        console.log(JSON.stringify(strip));
        """
        strip_json = json.loads(_run_node_script(script))

        strip_str = json.dumps(strip_json)
        assert "strip-rooms" not in strip_str
        assert "strip-sup" not in strip_str

        assert len(strip_json["children"]) == 2
        assert "strip-teachers" in strip_json["children"][0]["className"]
        assert "strip-sub-teachers" in strip_json["children"][1]["className"]

        r_index = client.get("/")
        assert r_index.status_code == 200
        assert 'href="styles.css?v=10"' in r_index.text
        assert 'src="app.js?v=10"' in r_index.text


def test_strip_05_anonymization_and_security_pills(tmp_path: Path) -> None:
    """TEST-STRIP-05: Anonymizovaný režim (export-static).

    Štítky zobrazují výhradně zkratky či iniciály, žádné plné příjmení učitele neunikne.
    """
    watch_dir = tmp_path / "exports"
    watch_dir.mkdir()
    for sample_file in sorted(SAMPLES_DIR.glob("*.html")):
        shutil.copy2(sample_file, watch_dir / sample_file.name)

    dist_dir = tmp_path / "dist"
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        f"watch_dir: {watch_dir}\ndb_path: {tmp_path / 'supl.db'}\nlog_dir: {tmp_path / 'logs'}\n",
        encoding="utf-8",
    )

    rc = cli_main(["--config", str(cfg_file), "export-static", "--output", str(dist_dir)])
    assert rc == 0

    day_files = list((dist_dir / "data").glob("day-*.json"))
    assert len(day_files) > 0

    script = f"""
    const app = require('{dist_dir.resolve()}/app.js');
    const fs = require('fs');
    const dayFiles = {json.dumps([str(p) for p in day_files])};
    const renderedPills = [];
    dayFiles.forEach(f => {{
        const day = JSON.parse(fs.readFileSync(f, 'utf8'));
        const strip = app.renderGridStrip(day);
        function walk(node) {{
            if (node.className && node.className.includes('pill-name')) {{
                renderedPills.push(node.textContent);
            }}
            (node.children || []).forEach(walk);
        }}
        walk(strip);
    }});
    console.log(JSON.stringify(renderedPills));
    """
    pill_names = json.loads(_run_node_script(script))

    forbidden_surnames = {
        "Valtr", "Kodad", "Šebková", "Rottová", "Poul", "Kudrnáč", "Šimková", "Ledvina",
        "Prýmek", "Bajerová", "Suchý", "Fox", "Hausner", "Ryba", "Kubečková", "Bernardová",
        "Bureš", "Očenášková", "Pleskačová", "Drchota", "Šťastný", "Bařinka", "Hanel",
        "Blažek", "Maňák", "Mudruňková", "Pfeifer", "Sobotová", "Tichá", "Hájek",
        "Fojtík", "Roušová", "Jobek", "Kulhánek", "Prýmková", "Čermáková", "Řehořová", "Křižík"
    }
    for name in pill_names:
        for surname in forbidden_surnames:
            assert surname not in name, f"V anonymizovaném štítku nalezeno příjmení {surname!r}: {name!r}"


def test_strip_06_regression_layout_and_kiosk() -> None:
    """TEST-STRIP-06: Regression (Layout & Kiosk): Dlouhý seznam učitelů (např. 15 nepřítomných a 12 suplujících)."""
    script = """
    const app = require('./app/static/app.js');
    const absent_teachers = Array.from({ length: 15 }, (_, i) => ({
        teacher_full_name: `Učitel Nepřítomný ${i + 1}`,
        teacher_code: `UN${i + 1}`,
        hours: { 1: {}, 2: {} }
    }));
    const class_changes = Array.from({ length: 12 }, (_, i) => ({
        class_name: `${i + 1}.A`,
        hour_from: 1,
        hour_to: 2,
        change_type: 'SUPLOVANI',
        sub_teacher: `Učitel Suplující ${i + 1}`,
        sub_teacher_changed: true
    }));
    const day = { absent_teachers, class_changes };
    const strip = app.renderGridStrip(day);
    console.log(JSON.stringify(strip));
    """
    strip = json.loads(_run_node_script(script))
    abs_pills = strip["children"][0]["children"][1]["children"]
    sub_pills = strip["children"][1]["children"][1]["children"]
    assert len(abs_pills) == 15
    assert len(sub_pills) == 12

    css = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert ".strip-pills" in css
    assert "flex-wrap: wrap" in css
    assert ".strip-teachers" in css
    assert ".strip-sub-teachers" in css
    assert "flex: 1 1 320px" in css
