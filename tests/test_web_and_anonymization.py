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
        assert 'href="styles.css?v=14"' in r_index.text
        assert 'src="app.js?v=14"' in r_index.text


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


def test_fetch_resilience_01(tmp_path: Path) -> None:
    """TEST-FETCH-RESILIENCE-01: Webový server vrací HTTP 503 nebo timeout.
    WebFetcher odchytí chybu, zapíše varování do logu, aplikace nespadne, existující data v DB zůstanou zachována.
    """
    import asyncio
    from unittest.mock import AsyncMock, patch

    import httpx

    from app.config import AppConfig
    from app.database import Storage
    from app.fetcher import WebFetcher
    from app.parser import parse_suplovani_html

    async def _async_scenario() -> None:
        db_path = tmp_path / "supl.db"
        storage = Storage(db_path)

        raw = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
        res = parse_suplovani_html(raw, file_name="suplprehtrid.html")
        storage.save_parse_result(res, file_hash="samplehash", file_size=len(raw))
        initial_dates = storage.list_available_dates()
        assert len(initial_dates) == 5

        cfg = AppConfig(
            db_path=db_path,
            web_url="https://klasifikace.skolakrizik.cz/next/zmeny.aspx",
            web_poll_interval_seconds=300.0,
        )
        fetcher = WebFetcher(cfg, storage)

        # 1. Test HTTP 503
        mock_503_resp = httpx.Response(503, request=httpx.Request("GET", cfg.web_url))
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_get.return_value = mock_503_resp
            success = await fetcher.fetch_once()
            assert success is False

        # Ověříme, že data v DB zůstala netknutá
        dates_after_503 = storage.list_available_dates()
        assert len(dates_after_503) == 5

        # 2. Test Timeout
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_get.side_effect = httpx.TimeoutException("Connection timed out")
            success = await fetcher.fetch_once()
            assert success is False

        # Ověříme, že data v DB stále existují
        dates_after_timeout = storage.list_available_dates()
        assert len(dates_after_timeout) == 5

    asyncio.run(_async_scenario())


def test_storage_hybrid_01(tmp_path: Path) -> None:
    """TEST-STORAGE-HYBRID-01: V databázi je týdenní soubor (Po–Pá).
    Stažen web pro pátek (data_source = 'web').
    Po–Čt mají data_source = 'file', Pátek má data_source = 'web'. Žádný jiný den nebyl smazán.
    """
    from app.database import Storage
    from app.parser import parse_suplovani_html
    from app.parser_web import parse_web_zmeny_html

    storage = Storage(tmp_path / "hybrid.db")
    raw_file = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res_file = parse_suplovani_html(raw_file, file_name="suplprehtrid.html")
    storage.save_parse_result(res_file, file_hash="filehash1", file_size=len(raw_file))

    # Ověříme výchozí dny
    dates_pre = storage.list_available_dates()
    assert len(dates_pre) == 5
    for d in dates_pre:
        day_pre = storage.get_day(d["date"])
        assert day_pre is not None
        assert day_pre.data_source == "file"

    # Uložíme webový export pro pátek (2026-11-06)
    raw_web = (SAMPLES_DIR / "zmeny_web_sample.html").read_bytes()
    res_web = parse_web_zmeny_html(raw_web)
    friday_web = res_web.days[0]
    friday_web.fetched_at = "2026-11-06T12:00:00+01:00"

    saved = storage.save_web_day(friday_web, source_hash="webhash1")
    assert saved is True

    # Ověření: Po–Čt mají data_source = 'file', Pátek má data_source = 'web'
    all_dates = storage.list_available_dates()
    assert len(all_dates) == 5
    for d_info in all_dates:
        d_obj = storage.get_day(d_info["date"])
        assert d_obj is not None
        if d_info["date"] == "2026-11-06":
            assert d_obj.data_source == "web"
            assert d_obj.source_label == "Web (klasifikace.skolakrizik.cz)"
        else:
            assert d_obj.data_source == "file"
            assert d_obj.source_label == "Soubor (Bakaláři export)"


def test_api_source_01(tmp_path: Path) -> None:
    """TEST-API-SOURCE-01: Volání /api/schedule pro den ze souboru a z webu.
    JSON obsahuje pole data_source a source_label.
    """
    from fastapi.testclient import TestClient

    from app.config import AppConfig
    from app.database import Storage
    from app.parser import parse_suplovani_html
    from app.parser_web import parse_web_zmeny_html
    from app.web import create_app

    db_path = tmp_path / "api_test.db"
    storage = Storage(db_path)
    raw_file = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res_file = parse_suplovani_html(raw_file, file_name="suplprehtrid.html")
    storage.save_parse_result(res_file, file_hash="hash_f", file_size=len(raw_file))

    raw_web = (SAMPLES_DIR / "zmeny_web_sample.html").read_bytes()
    res_web = parse_web_zmeny_html(raw_web)
    friday = res_web.days[0]
    friday.fetched_at = "2026-11-06T12:00:00+01:00"
    storage.save_web_day(friday, source_hash="hash_w")

    cfg = AppConfig(db_path=db_path, watch_dir=tmp_path / "watch")
    app = create_app(cfg, storage=storage, start_watcher=False)
    client = TestClient(app)

    # 1. Požadavek na pondělí (ze souboru)
    r_mon = client.get("/api/schedule?date=2026-11-02")
    assert r_mon.status_code == 200
    data_mon = r_mon.json()
    assert data_mon["day"]["data_source"] == "file"
    assert data_mon["day"]["source_label"] == "Soubor (Bakaláři export)"

    # 2. Požadavek na pátek (z webu)
    r_fri = client.get("/api/schedule?date=2026-11-06")
    assert r_fri.status_code == 200
    data_fri = r_fri.json()
    assert data_fri["day"]["data_source"] == "web"
    assert data_fri["day"]["source_label"] == "Web (klasifikace.skolakrizik.cz)"

    # 3. Kontrola seznamu 'dates' v odpovědi
    for date_entry in data_fri["dates"]:
        assert "data_source" in date_entry
        assert "source_label" in date_entry


def test_ui_indicators_01() -> None:
    """TEST-UI-INDICATORS-01: Kontrola nepřítomnosti zeleného online indikátoru a přítomnosti zdroje v index.html a app.js/styles.css."""
    static_dir = Path(__file__).resolve().parent.parent / "app" / "static"
    index_html = (static_dir / "index.html").read_text(encoding="utf-8")
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    styles_css = (static_dir / "styles.css").read_text(encoding="utf-8")

    assert 'id="connection-indicator"' not in index_html
    assert 'id="source-badge"' in index_html

    assert ".source-badge" in styles_css

    assert "sourceBadge" in app_js or "source-badge" in app_js
    assert "data_source" in app_js


def test_fetch_retry_01(tmp_path: Path) -> None:
    """TEST-FETCH-RETRY-01: Simulace školního serveru: první 2 volání vrátí HTTP 503, 3. volání vrátí HTTP 200 s platným HTML.
    WebFetcher.fetch_once() provede retry, neselže ihned, na 3. pokus uspěje. Status je SUCCESS, vráceno True, data uložena do DB.
    """
    import asyncio
    from unittest.mock import AsyncMock, patch

    import httpx

    from app.config import AppConfig
    from app.database import Storage
    from app.fetcher import WebFetcher

    async def _scenario() -> None:
        db_path = tmp_path / "retry.db"
        storage = Storage(db_path)
        cfg = AppConfig(
            db_path=db_path,
            web_url="https://klasifikace.skolakrizik.cz/next/zmeny.aspx",
        )
        fetcher = WebFetcher(cfg, storage)

        raw_web = (SAMPLES_DIR / "zmeny_web_sample.html").read_bytes()
        mock_503 = httpx.Response(503, request=httpx.Request("GET", cfg.web_url))
        mock_200 = httpx.Response(200, content=raw_web, request=httpx.Request("GET", cfg.web_url))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_get.side_effect = [mock_503, mock_503, mock_200]
            success = await fetcher.fetch_once()

            assert success is True
            assert fetcher.last_status == "SUCCESS"
            assert mock_get.call_count == 3
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1.0)
            mock_sleep.assert_any_call(2.0)

            day = storage.get_day("2026-11-06")
            assert day is not None
            assert day.data_source == "web"
            assert len(day.class_changes) == 19

    asyncio.run(_scenario())


def test_fetch_retry_fail_01(tmp_path: Path) -> None:
    """TEST-FETCH-RETRY-FAIL-01: Simulace trvalého výpadku: server vrátí HTTP 503 na všechny 3 pokusy.
    WebFetcher.fetch_once() vyčerpá 3 pokusy s prodlevou, nezpůsobí pád procesu, zaloguje varování,
    nastaví status ERROR a vrátí False. Původní data v DB zůstávají nedotčena.
    """
    import asyncio
    from unittest.mock import AsyncMock, patch

    import httpx

    from app.config import AppConfig
    from app.database import Storage
    from app.fetcher import WebFetcher
    from app.parser import parse_suplovani_html

    async def _scenario() -> None:
        db_path = tmp_path / "retry_fail.db"
        storage = Storage(db_path)
        raw_file = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
        res_file = parse_suplovani_html(raw_file, file_name="suplprehtrid.html")
        storage.save_parse_result(res_file, file_hash="orig_hash", file_size=len(raw_file))

        cfg = AppConfig(
            db_path=db_path,
            web_url="https://klasifikace.skolakrizik.cz/next/zmeny.aspx",
        )
        fetcher = WebFetcher(cfg, storage)

        mock_503 = httpx.Response(503, request=httpx.Request("GET", cfg.web_url))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_get.return_value = mock_503
            success = await fetcher.fetch_once()

            assert success is False
            assert fetcher.last_status == "ERROR"
            assert mock_get.call_count == 3
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1.0)
            mock_sleep.assert_any_call(2.0)

            dates = storage.list_available_dates()
            assert len(dates) == 5
            fri = storage.get_day("2026-11-06")
            assert fri is not None
            assert fri.data_source == "file"
            assert len(fri.class_changes) == 13

    asyncio.run(_scenario())


def test_storage_web_precedence_01(tmp_path: Path) -> None:
    """TEST-STORAGE-WEB-PRECEDENCE-01: V DB existuje starší export ze souboru pro pátek (13 změn, 3 nepřítomní).
    Zavolá se save_web_day s čerstvým webem (19 změn, 5 nepřítomných).
    save_web_day() vrátí True. Pátek je v DB kompletně aktualizován na 19 změn, 5 nepřítomných,
    data_source = 'web' a source_label = 'Web (klasifikace.skolakrizik.cz)'.
    Ostatní dny týdne (Po–Čt) zůstávají beze změny ('file').
    """
    from app.database import Storage
    from app.parser import parse_suplovani_html
    from app.parser_web import parse_web_zmeny_html

    storage = Storage(tmp_path / "precedence.db")
    raw_file = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res_file = parse_suplovani_html(raw_file, file_name="suplprehtrid.html")
    storage.save_parse_result(res_file, file_hash="hash_file", file_size=len(raw_file))

    day_fri_file = storage.get_day("2026-11-06")
    assert day_fri_file is not None
    assert len(day_fri_file.class_changes) == 13
    assert len(day_fri_file.absent_teachers) == 3
    assert day_fri_file.data_source == "file"

    raw_web = (SAMPLES_DIR / "zmeny_web_sample.html").read_bytes()
    res_web = parse_web_zmeny_html(raw_web)
    day_web = res_web.days[0]
    assert len(day_web.class_changes) == 19
    assert len(day_web.absent_teachers) == 5

    saved = storage.save_web_day(day_web, source_hash="hash_web")
    assert saved is True

    updated_fri = storage.get_day("2026-11-06")
    assert updated_fri is not None
    assert updated_fri.data_source == "web"
    assert updated_fri.source_label == "Web (klasifikace.skolakrizik.cz)"
    assert len(updated_fri.class_changes) == 19
    assert len(updated_fri.absent_teachers) == 5

    for d_str in ("2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"):
        d_obj = storage.get_day(d_str)
        assert d_obj is not None
        assert d_obj.data_source == "file"


def test_teacher_abbr_absent_01() -> None:
    """TEST-TEACHER-ABBR-ABSENT-01: Zobrazení nepřítomných pedagogů, jejichž jméno začíná na zkratku
    (Kodad Miloš -> Ko, Sobotová Dana -> So, Čermáková Irena -> Če, Fox Luděk -> Fo).
    Ve vygenerovaných štítcích .pill-name je text 'Kodad Miloš (Ko)', 'Sobotová Dana (So)',
    'Čermáková Irena (Če)', 'Fox Luděk (Fo)'. Žádná zkratka nechybí.
    """
    script = """
    const app = require('./app/static/app.js');
    const day = {
      absent_teachers: [
        { teacher_full_name: 'Kodad Miloš', teacher_code: 'Ko', hours: { 1: {} } },
        { teacher_full_name: 'Sobotová Dana', teacher_code: 'So', hours: { 2: {} } },
        { teacher_full_name: 'Čermáková Irena', teacher_code: 'Če', hours: { 3: {} } },
        { teacher_full_name: 'Fox Luděk', teacher_code: 'Fo', hours: { 4: {} } }
      ],
      class_changes: []
    };
    const strip = app.renderGridStrip(day);
    const absentBox = strip.children[0];
    const pillsContainer = absentBox.children[1];
    const pills = pillsContainer.children.map(p => {
      const nameEl = p.children[0];
      return nameEl.textContent;
    });
    console.log(JSON.stringify(pills));
    """
    pills = json.loads(_run_node_script(script))
    assert "Kodad Miloš (Ko)" in pills
    assert "Sobotová Dana (So)" in pills
    assert "Čermáková Irena (Če)" in pills
    assert "Fox Luděk (Fo)" in pills


def test_teacher_abbr_substituting_01() -> None:
    """TEST-TEACHER-ABBR-SUBSTITUTING-01: Zobrazení suplujících pedagogů v bloku Suplující učitelé
    (extractSubstitutingTeachers). Vstup: Bajerová Markéta, Prýmková Ivana, Rottová Renata.
    Štítky suplujících pedagogů obsahují plné jméno i oficiální zkratku:
    'Bajerová Markéta (Bj)', 'Prýmková Ivana (Pa)', 'Rottová Renata (Rt)'.
    """
    script = """
    const app = require('./app/static/app.js');
    const changes = [
      { class_name: '1.A', hour_from: 1, hour_to: 1, change_type: 'SUPLOVANI', sub_teacher: 'Bajerová Markéta' },
      { class_name: '2.B', hour_from: 2, hour_to: 3, change_type: 'SUPLOVANI', sub_teacher: 'Prýmková Ivana' },
      { class_name: '3.C', hour_from: 4, hour_to: 4, change_type: 'SPOJENO', sub_teacher: 'Rottová Renata' }
    ];
    const day = { absent_teachers: [], class_changes: changes };
    const strip = app.renderGridStrip(day);
    const subBox = strip.children[1];
    const pillsContainer = subBox.children[1];
    const pills = pillsContainer.children.map(p => {
      const nameEl = p.children[0];
      return nameEl.textContent;
    });
    const extracted = app.extractSubstitutingTeachers(changes, day);
    console.log(JSON.stringify({ pills, extracted }));
    """
    output = json.loads(_run_node_script(script))
    pills = output["pills"]
    assert "Bajerová Markéta (Bj)" in pills
    assert "Prýmková Ivana (Pa)" in pills
    assert "Rottová Renata (Rt)" in pills

    extracted = {item["teacher"]: item for item in output["extracted"]}
    assert extracted["Bajerová Markéta"]["teacherCode"] == "Bj"
    assert extracted["Bajerová Markéta"]["displayName"] == "Bajerová Markéta (Bj)"
    assert extracted["Prýmková Ivana"]["teacherCode"] == "Pa"
    assert extracted["Prýmková Ivana"]["displayName"] == "Prýmková Ivana (Pa)"
    assert extracted["Rottová Renata"]["teacherCode"] == "Rt"
    assert extracted["Rottová Renata"]["displayName"] == "Rottová Renata (Rt)"


def test_teacher_abbr_anonymized_01() -> None:
    """TEST-TEACHER-ABBR-ANONYMIZED-01: Zobrazení v anonymizovaném režimu (anonymize: true).
    Vstupem jsou pouze zkratky (Ko, Bj, So).
    Funkce formatTeacherWithCode('Ko', 'Ko') vrátí čistě 'Ko' (žádná duplicita 'Ko (Ko)').
    Žádné plné příjmení neunikne do DOMu.
    """
    script = """
    const app = require('./app/static/app.js');
    const f1 = app.formatTeacherWithCode('Ko', 'Ko');
    const f2 = app.formatTeacherWithCode('Bj', 'Bj');
    const f3 = app.formatTeacherWithCode('So', 'So');
    const f4 = app.formatTeacherWithCode('Ko', '');
    const f5 = app.formatTeacherWithCode('', 'Ko');

    const anonDay = {
      absent_teachers: [
        { teacher_full_name: 'Ko', teacher_code: 'Ko', hours: { 1: {} } }
      ],
      class_changes: [
        { class_name: '1.A', hour_from: 2, hour_to: 2, change_type: 'SUPLOVANI', sub_teacher: 'Bj' }
      ]
    };
    const strip = app.renderGridStrip(anonDay);
    const absentPillName = strip.children[0].children[1].children[0].children[0].textContent;
    const subPillName = strip.children[1].children[1].children[0].children[0].textContent;

    console.log(JSON.stringify({ f1, f2, f3, f4, f5, absentPillName, subPillName }));
    """
    output = json.loads(_run_node_script(script))
    assert output["f1"] == "Ko"
    assert output["f2"] == "Bj"
    assert output["f3"] == "So"
    assert output["f4"] == "Ko"
    assert output["f5"] == "(Ko)"
    assert output["absentPillName"] == "Ko"
    assert output["subPillName"] == "Bj"


def test_static_export_web_source_01(tmp_path: Path) -> None:
    """TEST-STATIC-EXPORT-WEB-SOURCE-01: Spuštění export-static po uložení webového dne do DB.
    V dist/data/day-2026-11-06.json a dist/data/index.json je správně zapsáno
    data_source: 'web' a source_label: 'Web (klasifikace.skolakrizik.cz)'.
    """
    from app.config import AppConfig
    from app.database import Storage
    from app.parser import parse_suplovani_html
    from app.parser_web import parse_web_zmeny_html
    from app.static_export import export_static_site

    watch_dir = tmp_path / "exports"
    watch_dir.mkdir()
    db_path = tmp_path / "static_web.db"
    storage = Storage(db_path)

    raw_file = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res_file = parse_suplovani_html(raw_file, file_name="suplprehtrid.html")
    storage.save_parse_result(res_file, file_hash="hash1", file_size=len(raw_file))

    raw_web = (SAMPLES_DIR / "zmeny_web_sample.html").read_bytes()
    res_web = parse_web_zmeny_html(raw_web)
    storage.save_web_day(res_web.days[0], source_hash="webhash")

    dist_dir = tmp_path / "dist"
    cfg = AppConfig(db_path=db_path, watch_dir=watch_dir)
    export_static_site(cfg, output_dir=dist_dir)

    day_file = dist_dir / "data" / "day-2026-11-06.json"
    assert day_file.is_file()
    day_data = json.loads(day_file.read_text(encoding="utf-8"))
    assert day_data["data_source"] == "web"
    assert day_data["source_label"] == "Web (klasifikace.skolakrizik.cz)"

    index_file = dist_dir / "data" / "index.json"
    assert index_file.is_file()
    index_data = json.loads(index_file.read_text(encoding="utf-8"))
    fri_entry = next((d for d in index_data["dates"] if d["date"] == "2026-11-06"), None)
    assert fri_entry is not None
    assert fri_entry["data_source"] == "web"
    assert fri_entry["source_label"] == "Web (klasifikace.skolakrizik.cz)"

    mon_entry = next((d for d in index_data["dates"] if d["date"] == "2026-11-02"), None)
    assert mon_entry is not None
    assert mon_entry["data_source"] == "file"


def test_note_public_01() -> None:
    """TEST-NOTE-PUBLIC-01: Test funkce sanitize_note pro různé varianty poznámek."""
    from app.anonymizer import sanitize_note

    # Organizační poznámky k rozvrhu jsou veřejné
    assert sanitize_note("supluje") == "supluje"
    assert sanitize_note("odpadá") == "odpadá"
    assert sanitize_note("spojí") == "spojí"
    assert sanitize_note("změna") == "změna"
    assert sanitize_note("přesun z 1. hod") == "přesun z 1. hod"
    assert sanitize_note("Exkurze") == "Exkurze"
    assert sanitize_note("  odpadá  ") == "odpadá"
    assert sanitize_note("") == ""
    assert sanitize_note(None) == ""  # type: ignore[arg-type]


def test_note_anonymized_day_01() -> None:
    """TEST-NOTE-ANONYMIZED-DAY-01: anonymize_schedule_day zachovává organizační poznámky."""
    from app.anonymizer import anonymize_schedule_day
    from app.models import ChangeType, ClassChange, ScheduleDay

    day = ScheduleDay(
        date="2026-11-06",
        day_name="Pátek",
        week_label="",
        school_name="SPŠE Františka Křižíka",
        exported_at="2026-11-06T22:17:00+01:00",
        exported_at_display="6. 11. 2026 22:17",
        data_source="web",
        source_label="Web (klasifikace.skolakrizik.cz)",
        fetched_at="2026-11-06T22:17:00+01:00",
        class_changes=[
            ClassChange(
                date="2026-11-06",
                class_name="1.A",
                hour_from=1,
                hour_to=1,
                subject="MAT",
                group_name="",
                room="101",
                room_changed=False,
                change_type=ChangeType.ODPADA,
                change_type_raw="odpadá",
                sub_teacher="",
                sub_teacher_changed=False,
                orig_teacher_code="Ko",
                orig_teacher_resolved="Kodad Miloš",
                note="odpadá",
                raw_row_text="",
            ),
            ClassChange(
                date="2026-11-06",
                class_name="2.B",
                hour_from=2,
                hour_to=2,
                subject="FYZ",
                group_name="",
                room="202",
                room_changed=False,
                change_type=ChangeType.SUPLOVANI,
                change_type_raw="supluje",
                sub_teacher="Bajerová Markéta",
                sub_teacher_changed=True,
                orig_teacher_code="Be",
                orig_teacher_resolved="Bernard Pavel",
                note="supluje",
                raw_row_text="",
            ),
        ],
    )
    anon = anonymize_schedule_day(day, {"Ko": "Kodad Miloš", "Be": "Bernard Pavel", "Bj": "Bajerová Markéta"})
    assert anon.class_changes[0].note == "odpadá"
    assert anon.class_changes[1].note == "supluje"
    assert anon.class_changes[0].orig_teacher_resolved == ""
    assert anon.class_changes[1].sub_teacher == "Bj"

    # Žádné pole neobsahuje [poznámka skryta]
    dumped_str = json.dumps(anon.model_dump(), ensure_ascii=False)
    assert "[poznámka skryta]" not in dumped_str


def test_parser_web_timestamp_01() -> None:
    """TEST-PARSER-WEB-TIMESTAMP-01: parse_web_zmeny_html nastaví přesný čas a datum."""
    import re

    from app.parser_web import parse_web_zmeny_html

    sample_html = (SAMPLES_DIR / "zmeny_web_sample.html").read_bytes()
    res = parse_web_zmeny_html(sample_html)
    assert len(res.days) == 1
    day = res.days[0]

    # ISO formát s časem a časovou zónou
    assert day.exported_at is not None
    assert "T" in day.exported_at
    assert day.fetched_at == day.exported_at

    # exported_at_display obsahuje datum i čas (např. '6. 11. 2026 22:17' nebo '06. 11. 2026 22:17')
    assert day.exported_at_display is not None
    assert re.match(r"^\d{1,2}\.\s*\d{1,2}\.\s*\d{4}\s+\d{1,2}:\d{2}$", day.exported_at_display)


def test_js_datetime_format_01() -> None:
    """TEST-JS-DATETIME-FORMAT-01: formatDateTimeCzech bezpečně formátuje ISO i fallback text."""
    script = """
    const app = require('./app/static/app.js');
    const isoRes = app.formatDateTimeCzech('2026-11-06T22:17:14+01:00');
    const txtRes = app.formatDateTimeCzech('', '5. 11. 2026 08:26');
    const emptyRes1 = app.formatDateTimeCzech('', '');
    const emptyRes2 = app.formatDateTimeCzech(null, null);
    const emptyRes3 = app.formatDateTimeCzech('invalid');
    console.log(JSON.stringify({ isoRes, txtRes, emptyRes1, emptyRes2, emptyRes3 }));
    """
    output = json.loads(_run_node_script(script))
    assert output["isoRes"] == "6. 11. 2026 v 22:17"
    assert output["txtRes"] == "5. 11. 2026 v 08:26"
    assert output["emptyRes1"] == ""
    assert output["emptyRes2"] == ""
    assert output["emptyRes3"] == ""


def test_js_source_badge_text_01() -> None:
    """TEST-JS-SOURCE-BADGE-TEXT-01: formatSourceBadgeText formátuje texty pro web i soubor."""
    script = """
    const app = require('./app/static/app.js');
    const webDay = {
      data_source: 'web',
      source_label: 'Web (klasifikace.skolakrizik.cz)',
      fetched_at: '2026-11-06T22:17:14+01:00',
      exported_at: '2026-11-06T22:17:14+01:00',
      exported_at_display: '6. 11. 2026 22:17'
    };
    const fileDay = {
      data_source: 'file',
      source_label: 'Soubor (Bakaláři export)',
      exported_at: '2026-11-05T08:26:00+01:00',
      exported_at_display: '5. 11. 2026 08:26'
    };
    const noTimeDay = {
      data_source: 'file',
      source_label: 'Soubor (Bakaláři export)'
    };

    const webText = app.formatSourceBadgeText(webDay);
    const fileText = app.formatSourceBadgeText(fileDay);
    const noTimeText = app.formatSourceBadgeText(noTimeDay);
    const nullText = app.formatSourceBadgeText(null);

    console.log(JSON.stringify({ webText, fileText, noTimeText, nullText }));
    """
    output = json.loads(_run_node_script(script))
    assert output["webText"] == "Zdroj: Web (klasifikace.skolakrizik.cz) · Načteno 6. 11. 2026 v 22:17"
    assert output["fileText"] == "Zdroj: Soubor (Bakaláři export) · Export 5. 11. 2026 v 08:26"
    assert "Zdroj: Soubor (Bakaláři export)" in output["noTimeText"]
    assert output["nullText"] == ""


def test_js_tab_switch_instant_01() -> None:
    """TEST-JS-TAB-SWITCH-INSTANT-01: Okamžité přepnutí třídy a textu source-badge při změně záložky dne."""
    script = """
    // Simulace minimálního DOMu před načtením app.js
    const elements = {};
    function createMockElement(id, tag = 'div') {
      const classListSet = new Set();
      const el = {
        id,
        tagName: tag.toUpperCase(),
        className: '',
        textContent: '',
        children: [],
        listeners: {},
        classList: {
          add: (c) => { classListSet.add(c); el.className = Array.from(classListSet).join(' '); },
          remove: (c) => { classListSet.delete(c); el.className = Array.from(classListSet).join(' '); },
          contains: (c) => classListSet.has(c)
        },
        setAttribute: (k, v) => { el[k] = v; },
        getAttribute: (k) => el[k] || '',
        replaceChildren: () => { el.children = []; },
        appendChild: (child) => { el.children.push(child); return child; },
        querySelectorAll: (sel) => el.children,
        addEventListener: (evt, fn) => { el.listeners[evt] = fn; }
      };
      elements[id] = el;
      return el;
    }

    createMockElement('main-container');
    createMockElement('school-name');
    createMockElement('exported-at-label');
    createMockElement('updated-at-label');
    createMockElement('banner-parse-error');
    createMockElement('banner-parse-error-text');
    createMockElement('banner-stale');
    createMockElement('banner-stale-text');
    createMockElement('banner-offline');
    createMockElement('date-tabs');
    createMockElement('entity-select');
    createMockElement('search-input');
    createMockElement('btn-clear-filter');
    createMockElement('day-heading');
    createMockElement('source-badge');
    createMockElement('source-badge-text');
    createMockElement('connection-indicator');
    createMockElement('connection-text');
    createMockElement('grid-view');

    global.window = {
      location: { search: '' },
      addEventListener: () => {},
      __STATIC_EXPORT__: true
    };
    global.document = {
      getElementById: (id) => elements[id] || createMockElement(id),
      createElement: (tag) => createMockElement('', tag),
      createElementNS: () => createMockElement('', 'svg'),
      addEventListener: () => {},
      documentElement: { scrollTop: 0 },
      body: { scrollTop: 0 }
    };

    const app = require('./app/static/app.js');

    const monDay = {
      date: '2026-11-02',
      day_name: 'Pondělí',
      data_source: 'file',
      source_label: 'Soubor (Bakaláři export)',
      exported_at: '2026-11-05T08:26:00+01:00',
      exported_at_display: '5. 11. 2026 08:26'
    };
    const friDay = {
      date: '2026-11-06',
      day_name: 'Pátek',
      data_source: 'web',
      source_label: 'Web (klasifikace.skolakrizik.cz)',
      fetched_at: '2026-11-06T22:17:14+01:00',
      exported_at: '2026-11-06T22:17:14+01:00',
      exported_at_display: '6. 11. 2026 22:17'
    };

    // 1. Změna na souborový den
    app.updateSourceBadge(monDay);
    const step1BadgeClass = elements['source-badge'].className;
    const step1BadgeText = elements['source-badge-text'].textContent;

    // 2. Okamžitá změna na webový den (např. při kliku na záložku Pátek)
    app.updateSourceBadge(friDay);
    const step2BadgeClass = elements['source-badge'].className;
    const step2BadgeText = elements['source-badge-text'].textContent;

    // 3. Zpět na soubor
    app.updateSourceBadge(monDay);
    const step3BadgeClass = elements['source-badge'].className;
    const step3BadgeText = elements['source-badge-text'].textContent;

    console.log(JSON.stringify({
      step1BadgeClass, step1BadgeText,
      step2BadgeClass, step2BadgeText,
      step3BadgeClass, step3BadgeText
    }));
    """
    output = json.loads(_run_node_script(script))
    assert "source-file" in output["step1BadgeClass"]
    assert "Soubor" in output["step1BadgeText"]
    assert "Export 5. 11. 2026 v 08:26" in output["step1BadgeText"]

    assert "source-web" in output["step2BadgeClass"]
    assert "Web" in output["step2BadgeText"]
    assert "Načteno 6. 11. 2026 v 22:17" in output["step2BadgeText"]

    assert "source-file" in output["step3BadgeClass"]
    assert "Soubor" in output["step3BadgeText"]


def test_static_export_no_hidden_notes_01(tmp_path: Path) -> None:
    """TEST-STATIC-EXPORT-NO-HIDDEN-NOTES-01: Ověří absenci [poznámka skryta] ve statickém exportu."""
    from app.config import AppConfig
    from app.database import Storage
    from app.parser import parse_suplovani_html
    from app.parser_web import parse_web_zmeny_html
    from app.static_export import export_static_site

    watch_dir = tmp_path / "exports"
    watch_dir.mkdir()
    db_path = tmp_path / "test_notes.db"
    storage = Storage(db_path)

    raw_file = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res_file = parse_suplovani_html(raw_file, file_name="suplprehtrid.html")
    storage.save_parse_result(res_file, file_hash="hash1", file_size=len(raw_file))

    raw_web = (SAMPLES_DIR / "zmeny_web_sample.html").read_bytes()
    res_web = parse_web_zmeny_html(raw_web)
    storage.save_web_day(res_web.days[0], source_hash="webhash")

    dist_dir = tmp_path / "dist"
    cfg = AppConfig(db_path=db_path, watch_dir=watch_dir)
    export_static_site(cfg, output_dir=dist_dir)

    # a) V žádném .json souboru se nevyskytuje [poznámka skryta]
    for json_file in (dist_dir / "data").glob("*.json"):
        content = json_file.read_text(encoding="utf-8")
        assert "[poznámka skryta]" not in content, f"Nalezeno '[poznámka skryta]' v {json_file.name}"

    # b) dist/index.html neobsahuje natvrdo zapsané Zdroj: Soubor ani statickou třídu source-file
    index_html = (dist_dir / "index.html").read_text(encoding="utf-8")
    assert "source-badge source-file" not in index_html
    assert "Zdroj: Soubor (Bakaláři export)" not in index_html
    assert "Načítám zdroj…" not in index_html
    assert "?v=14" in index_html

    # c) dist/data/day-2026-11-06.json obsahuje čas v exported_at_display a data_source = 'web'
    fri_file = dist_dir / "data" / "day-2026-11-06.json"
    assert fri_file.is_file()
    fri_data = json.loads(fri_file.read_text(encoding="utf-8"))
    assert fri_data["data_source"] == "web"
    assert ":" in fri_data["exported_at_display"]


def test_clean_header_no_online_01() -> None:
    """TEST-CLEAN-HEADER-NO-ONLINE-01: Element #connection-indicator neexistuje a nejsou v něm placeholdery."""
    static_dir = Path(__file__).resolve().parent.parent / "app" / "static"
    index_html = (static_dir / "index.html").read_text(encoding="utf-8")

    assert 'id="connection-indicator"' not in index_html
    assert 'id="connection-text"' not in index_html
    assert "status-dot" not in index_html

    assert "Datum výpisu: načítám…" not in index_html
    assert "Poslední kontrola: —" not in index_html
    assert "Načítám rozvrh…" not in index_html
    assert "Načítám zdroj…" not in index_html

    assert '<div id="exported-at-label"></div>' in index_html
    assert '<div id="updated-at-label"></div>' in index_html
    assert '<h2 class="day-heading" id="day-heading"></h2>' in index_html
    assert 'id="source-badge" class="source-badge hidden"' in index_html


def test_default_view_is_grid_01() -> None:
    """TEST-DEFAULT-VIEW-IS-GRID-01: Načtení aplikace v defaultním stavu (activeView = 'grid')."""
    script = """
    const elements = {};
    function createMockElement(id, tag = 'div') {
      const classListSet = new Set();
      const el = {
        id,
        tagName: tag.toUpperCase(),
        className: '',
        textContent: '',
        children: [],
        listeners: {},
        classList: {
          add: (c) => { classListSet.add(c); el.className = Array.from(classListSet).join(' '); },
          remove: (c) => { classListSet.delete(c); el.className = Array.from(classListSet).join(' '); },
          toggle: (c, force) => {
            if (force === undefined) {
              if (classListSet.has(c)) classListSet.delete(c); else classListSet.add(c);
            } else if (force) {
              classListSet.add(c);
            } else {
              classListSet.delete(c);
            }
            el.className = Array.from(classListSet).join(' ');
          },
          contains: (c) => classListSet.has(c)
        },
        setAttribute: (k, v) => { el[k] = v; },
        getAttribute: (k) => el[k] || '',
        replaceChildren: () => { el.children = []; },
        appendChild: (child) => { el.children.push(child); return child; },
        querySelectorAll: (sel) => el.children,
        addEventListener: (evt, fn) => { el.listeners[evt] = fn; }
      };
      elements[id] = el;
      return el;
    }

    createMockElement('main-container');
    createMockElement('school-name');
    createMockElement('exported-at-label');
    createMockElement('updated-at-label');
    createMockElement('banner-parse-error');
    createMockElement('banner-parse-error-text');
    createMockElement('banner-stale');
    createMockElement('banner-stale-text');
    createMockElement('banner-offline');
    createMockElement('date-tabs');
    createMockElement('view-tabs');
    createMockElement('btn-view-grid', 'button');
    createMockElement('btn-view-cards', 'button');
    createMockElement('entity-select');
    createMockElement('search-input');
    createMockElement('btn-clear-filter');
    createMockElement('day-heading');
    createMockElement('source-badge');
    createMockElement('source-badge-text');
    createMockElement('grid-view');
    createMockElement('cards-view');

    global.window = {
      location: { search: '' },
      addEventListener: () => {},
      __STATIC_EXPORT__: true,
      innerHeight: 900
    };
    global.document = {
      getElementById: (id) => elements[id] || createMockElement(id),
      createElement: (tag) => createMockElement('', tag),
      createElementNS: () => createMockElement('', 'svg'),
      addEventListener: () => {},
      documentElement: { scrollTop: 0, scrollHeight: 900 },
      body: { scrollTop: 0, scrollHeight: 900, classList: { contains: () => false, add: () => {}, remove: () => {} } }
    };

    const app = require('./app/static/app.js');

    app.state.dayData = {
      date: '2026-11-05',
      day_name: 'Čtvrtek',
      class_changes: [
        { class_name: '1.A', hour_from: 1, hour_to: 1, subject: 'CJL', change_type: 'SUPLOVANI', sub_teacher: 'Kodad Miloš', note: 'Změna učitele' }
      ]
    };
    app.renderAll();

    console.log(JSON.stringify({
      activeView: app.state.activeView,
      gridHasHidden: elements['grid-view'].classList.contains('hidden'),
      cardsHasHidden: elements['cards-view'].classList.contains('hidden'),
      btnGridActive: elements['btn-view-grid'].classList.contains('active'),
      btnCardsActive: elements['btn-view-cards'].classList.contains('active'),
      btnGridSelected: elements['btn-view-grid']['aria-selected'],
      btnCardsSelected: elements['btn-view-cards']['aria-selected']
    }));
    """
    output = json.loads(_run_node_script(script))
    assert output["activeView"] == "grid"
    assert output["gridHasHidden"] is False
    assert output["cardsHasHidden"] is True
    assert output["btnGridActive"] is True
    assert output["btnCardsActive"] is False
    assert output["btnGridSelected"] == "true"
    assert output["btnCardsSelected"] == "false"


def test_switch_to_cards_view_01() -> None:
    """TEST-SWITCH-TO-CARDS-VIEW-01: Kliknutí na tlačítko přepnutí do režimu 'cards' (Old Seznam karet)."""
    script = """
    const elements = {};
    function createMockElement(id, tag = 'div') {
      const classListSet = new Set();
      const el = {
        id,
        tagName: tag.toUpperCase(),
        className: '',
        textContent: '',
        children: [],
        listeners: {},
        classList: {
          add: (c) => { classListSet.add(c); el.className = Array.from(classListSet).join(' '); },
          remove: (c) => { classListSet.delete(c); el.className = Array.from(classListSet).join(' '); },
          toggle: (c, force) => {
            if (force === undefined) {
              if (classListSet.has(c)) classListSet.delete(c); else classListSet.add(c);
            } else if (force) {
              classListSet.add(c);
            } else {
              classListSet.delete(c);
            }
            el.className = Array.from(classListSet).join(' ');
          },
          contains: (c) => classListSet.has(c)
        },
        setAttribute: (k, v) => { el[k] = v; },
        getAttribute: (k) => el[k] || '',
        replaceChildren: () => { el.children = []; },
        appendChild: (child) => { el.children.push(child); return child; },
        querySelectorAll: (sel) => el.children,
        addEventListener: (evt, fn) => { el.listeners[evt] = fn; }
      };
      elements[id] = el;
      return el;
    }

    createMockElement('main-container');
    createMockElement('school-name');
    createMockElement('exported-at-label');
    createMockElement('updated-at-label');
    createMockElement('banner-parse-error');
    createMockElement('banner-parse-error-text');
    createMockElement('banner-stale');
    createMockElement('banner-stale-text');
    createMockElement('banner-offline');
    createMockElement('date-tabs');
    createMockElement('view-tabs');
    createMockElement('btn-view-grid', 'button');
    createMockElement('btn-view-cards', 'button');
    createMockElement('entity-select');
    createMockElement('search-input');
    createMockElement('btn-clear-filter');
    createMockElement('day-heading');
    createMockElement('source-badge');
    createMockElement('source-badge-text');
    createMockElement('grid-view');
    createMockElement('cards-view');

    global.window = {
      location: { search: '' },
      addEventListener: () => {},
      __STATIC_EXPORT__: true,
      innerHeight: 900
    };
    global.document = {
      getElementById: (id) => elements[id] || createMockElement(id),
      createElement: (tag) => createMockElement('', tag),
      createElementNS: () => createMockElement('', 'svg'),
      addEventListener: () => {},
      documentElement: { scrollTop: 0, scrollHeight: 900 },
      body: { scrollTop: 0, scrollHeight: 900, classList: { contains: () => false, add: () => {}, remove: () => {} } }
    };

    const app = require('./app/static/app.js');

    app.state.dayData = {
      date: '2026-11-05',
      day_name: 'Čtvrtek',
      class_changes: [
        { class_name: '1.A', hour_from: 1, hour_to: 1, subject: 'CJL', change_type: 'SUPLOVANI', sub_teacher: 'Kodad Miloš', note: 'Změna učitele' }
      ]
    };

    app.switchView('cards');

    function countGroupCards(node) {
      let cnt = 0;
      if (node.className && node.className.includes('group-card') && !node.className.includes('group-card-')) {
        cnt++;
      }
      for (const ch of (node.children || [])) {
        cnt += countGroupCards(ch);
      }
      return cnt;
    }

    console.log(JSON.stringify({
      activeView: app.state.activeView,
      gridHasHidden: elements['grid-view'].classList.contains('hidden'),
      cardsHasHidden: elements['cards-view'].classList.contains('hidden'),
      btnGridActive: elements['btn-view-grid'].classList.contains('active'),
      btnCardsActive: elements['btn-view-cards'].classList.contains('active'),
      groupCardsCount: countGroupCards(elements['cards-view'])
    }));
    """
    output = json.loads(_run_node_script(script))
    assert output["activeView"] == "cards"
    assert output["gridHasHidden"] is True
    assert output["cardsHasHidden"] is False
    assert output["btnGridActive"] is False
    assert output["btnCardsActive"] is True
    assert output["groupCardsCount"] >= 1


def test_cards_view_content_01() -> None:
    """TEST-CARDS-VIEW-CONTENT-01: Každá třída se změnami má kartu .group-card a plné znění poznámek bez [poznámka skryta]."""
    script = """
    const elements = {};
    function createMockElement(id, tag = 'div') {
      const classListSet = new Set();
      const el = {
        id,
        tagName: tag.toUpperCase(),
        className: '',
        textContent: '',
        children: [],
        listeners: {},
        classList: {
          add: (c) => { classListSet.add(c); el.className = Array.from(classListSet).join(' '); },
          remove: (c) => { classListSet.delete(c); el.className = Array.from(classListSet).join(' '); },
          toggle: (c, force) => {
            if (force === undefined) {
              if (classListSet.has(c)) classListSet.delete(c); else classListSet.add(c);
            } else if (force) {
              classListSet.add(c);
            } else {
              classListSet.delete(c);
            }
            el.className = Array.from(classListSet).join(' ');
          },
          contains: (c) => classListSet.has(c)
        },
        setAttribute: (k, v) => { el[k] = v; },
        getAttribute: (k) => el[k] || '',
        replaceChildren: () => { el.children = []; },
        appendChild: (child) => { el.children.push(child); return child; },
        querySelectorAll: (sel) => el.children,
        addEventListener: (evt, fn) => { el.listeners[evt] = fn; }
      };
      elements[id] = el;
      return el;
    }

    createMockElement('cards-view');

    global.window = {
      location: { search: '' },
      addEventListener: () => {},
      __STATIC_EXPORT__: true
    };
    global.document = {
      getElementById: (id) => elements[id] || createMockElement(id),
      createElement: (tag) => createMockElement('', tag),
      createElementNS: () => createMockElement('', 'svg'),
      addEventListener: () => {}
    };

    const app = require('./app/static/app.js');

    const day = {
      date: '2026-11-05',
      day_name: 'Čtvrtek',
      class_changes: [
        {
          class_name: '2.B',
          hour_from: 2,
          hour_to: 3,
          subject: 'MAT',
          group_name: 'sk1',
          room: '205',
          sub_teacher: 'Kodad Miloš',
          change_type: 'SUPLOVANI',
          note: 'spojeno s 2.A v učebně 205'
        },
        {
          class_name: '3.C',
          hour_from: 5,
          hour_to: 5,
          subject: 'FYZ',
          group_name: '',
          room: '',
          orig_teacher_code: 'Vl',
          change_type: 'ODPADA',
          note: 'odpadá bez náhrady'
        }
      ]
    };

    app.renderCards(day);

    function collectText(node) {
      let t = node.textContent || '';
      for (const ch of (node.children || [])) {
        t += ' ' + collectText(ch);
      }
      return t;
    }

    const cardsText = collectText(elements['cards-view']);

    console.log(JSON.stringify({
      cardsText: cardsText,
      hasHiddenMarker: cardsText.includes('[poznámka skryta]'),
      hasNote1: cardsText.includes('spojeno s 2.A v učebně 205'),
      hasNote2: cardsText.includes('odpadá bez náhrady'),
      hasClass2B: cardsText.includes('2.B'),
      hasClass3C: cardsText.includes('3.C')
    }));
    """
    output = json.loads(_run_node_script(script))
    assert output["hasHiddenMarker"] is False
    assert output["hasNote1"] is True
    assert output["hasNote2"] is True
    assert output["hasClass2B"] is True
    assert output["hasClass3C"] is True


def test_cards_filter_interaction_01() -> None:
    """TEST-CARDS-FILTER-INTERACTION-01: Změna filtru třídy v režimu karet zobrazí pouze vybranou třídu."""
    script = """
    const elements = {};
    function createMockElement(id, tag = 'div') {
      const classListSet = new Set();
      const el = {
        id,
        tagName: tag.toUpperCase(),
        className: '',
        textContent: '',
        children: [],
        listeners: {},
        classList: {
          add: (c) => { classListSet.add(c); el.className = Array.from(classListSet).join(' '); },
          remove: (c) => { classListSet.delete(c); el.className = Array.from(classListSet).join(' '); },
          toggle: (c, force) => {
            if (force === undefined) {
              if (classListSet.has(c)) classListSet.delete(c); else classListSet.add(c);
            } else if (force) {
              classListSet.add(c);
            } else {
              classListSet.delete(c);
            }
            el.className = Array.from(classListSet).join(' ');
          },
          contains: (c) => classListSet.has(c)
        },
        setAttribute: (k, v) => { el[k] = v; },
        getAttribute: (k) => el[k] || '',
        replaceChildren: () => { el.children = []; },
        appendChild: (child) => { el.children.push(child); return child; },
        querySelectorAll: (sel) => el.children,
        addEventListener: (evt, fn) => { el.listeners[evt] = fn; }
      };
      elements[id] = el;
      return el;
    }

    createMockElement('cards-view');

    global.window = {
      location: { search: '' },
      addEventListener: () => {},
      __STATIC_EXPORT__: true
    };
    global.document = {
      getElementById: (id) => elements[id] || createMockElement(id),
      createElement: (tag) => createMockElement('', tag),
      createElementNS: () => createMockElement('', 'svg'),
      addEventListener: () => {}
    };

    const app = require('./app/static/app.js');

    const day = {
      date: '2026-11-05',
      day_name: 'Čtvrtek',
      class_changes: [
        { class_name: '1.A', hour_from: 1, hour_to: 1, subject: 'MAT', change_type: 'SUPLOVANI' },
        { class_name: '2.B', hour_from: 2, hour_to: 2, subject: 'FYZ', change_type: 'ODPADA' }
      ]
    };

    app.state.selectedEntity = '2.B';
    app.renderCards(day);

    function collectText(node) {
      let t = node.textContent || '';
      for (const ch of (node.children || [])) {
        t += ' ' + collectText(ch);
      }
      return t;
    }

    const cardsText = collectText(elements['cards-view']);
    console.log(JSON.stringify({
      cardsText: cardsText,
      has2B: cardsText.includes('2.B'),
      has1A: cardsText.includes('1.A')
    }));
    """
    output = json.loads(_run_node_script(script))
    assert output["has2B"] is True
    assert output["has1A"] is False


def test_no_hidden_notes_anywhere_01(tmp_path: Path) -> None:
    """TEST-NO-HIDDEN-NOTES-ANYWHERE-01: Ověří 0 výskytů [poznámka skryta] ve statickém exportu a v kódu."""
    from app.config import AppConfig
    from app.database import Storage
    from app.parser import parse_suplovani_html
    from app.static_export import export_static_site

    watch_dir = tmp_path / "exports"
    watch_dir.mkdir()
    db_path = tmp_path / "test_notes.db"
    storage = Storage(db_path)

    raw_file = (SAMPLES_DIR / "suplprehtrid.html").read_bytes()
    res_file = parse_suplovani_html(raw_file, file_name="suplprehtrid.html")
    storage.save_parse_result(res_file, file_hash="hash1", file_size=len(raw_file))

    dist_dir = tmp_path / "dist"
    cfg = AppConfig(db_path=db_path, watch_dir=watch_dir)
    export_static_site(cfg, output_dir=dist_dir)

    for json_file in (dist_dir / "data").glob("*.json"):
        content = json_file.read_text(encoding="utf-8")
        assert "[poznámka skryta]" not in content, f"Nalezeno '[poznámka skryta]' v {json_file.name}"

    real_dist = Path(__file__).resolve().parent.parent / "dist"
    if (real_dist / "data").exists():
        for json_file in (real_dist / "data").glob("*.json"):
            content = json_file.read_text(encoding="utf-8")
            assert "[poznámka skryta]" not in content, f"Nalezeno '[poznámka skryta]' v dist/data/{json_file.name}"


def test_source_badge_clean_load_01() -> None:
    """TEST-SOURCE-BADGE-CLEAN-LOAD-01: Stav source-badge před a po načtení dat bez placeholderů."""
    script = """
    const elements = {};
    function createMockElement(id, tag = 'div') {
      const classListSet = new Set();
      const el = {
        id,
        tagName: tag.toUpperCase(),
        className: '',
        textContent: '',
        children: [],
        listeners: {},
        classList: {
          add: (c) => { classListSet.add(c); el.className = Array.from(classListSet).join(' '); },
          remove: (c) => { classListSet.delete(c); el.className = Array.from(classListSet).join(' '); },
          toggle: (c, force) => {
            if (force === undefined) {
              if (classListSet.has(c)) classListSet.delete(c); else classListSet.add(c);
            } else if (force) {
              classListSet.add(c);
            } else {
              classListSet.delete(c);
            }
            el.className = Array.from(classListSet).join(' ');
          },
          contains: (c) => classListSet.has(c)
        },
        setAttribute: (k, v) => { el[k] = v; },
        getAttribute: (k) => el[k] || '',
        replaceChildren: () => { el.children = []; },
        appendChild: (child) => { el.children.push(child); return child; },
        querySelectorAll: (sel) => el.children,
        addEventListener: (evt, fn) => { el.listeners[evt] = fn; }
      };
      elements[id] = el;
      return el;
    }

    createMockElement('source-badge');
    createMockElement('source-badge-text');

    global.window = {
      location: { search: '' },
      addEventListener: () => {},
      __STATIC_EXPORT__: true
    };
    global.document = {
      getElementById: (id) => elements[id] || createMockElement(id),
      createElement: (tag) => createMockElement('', tag),
      createElementNS: () => createMockElement('', 'svg'),
      addEventListener: () => {}
    };

    const app = require('./app/static/app.js');

    // 1. Před načtením dat
    app.updateSourceBadge(null);
    const beforeHasHidden = elements['source-badge'].classList.contains('hidden');
    const beforeText = elements['source-badge-text'].textContent;

    // 2. Po načtení webového dne
    const webDay = {
      data_source: 'web',
      source_label: 'Web (klasifikace.skolakrizik.cz)',
      fetched_at: '2026-11-06T22:17:14+01:00',
      exported_at: '2026-11-06T22:17:14+01:00',
      exported_at_display: '6. 11. 2026 22:17'
    };
    app.updateSourceBadge(webDay);
    const afterHasHidden = elements['source-badge'].classList.contains('hidden');
    const afterClass = elements['source-badge'].className;
    const afterText = elements['source-badge-text'].textContent;

    console.log(JSON.stringify({
      beforeHasHidden, beforeText,
      afterHasHidden, afterClass, afterText
    }));
    """
    output = json.loads(_run_node_script(script))
    assert output["beforeHasHidden"] is True
    assert output["beforeText"] == ""
    assert "Načítám zdroj…" not in output["beforeText"]

    assert output["afterHasHidden"] is False
    assert "source-web" in output["afterClass"]
    assert "Web (klasifikace.skolakrizik.cz)" in output["afterText"]
    assert "Načteno 6. 11. 2026 v 22:17" in output["afterText"]




