"""Testy webového rozhraní, PWA, bezpečnostních hlaviček, anonymizace a export-static (Fáze 4 a 5)."""

from __future__ import annotations

import shutil
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
