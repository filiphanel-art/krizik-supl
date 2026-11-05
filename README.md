# Školní zobrazení suplování (Suplování Viewer)

Produkčně připravená, lehká a plně lokální webová aplikace (PWA) pro střední školu (**VOŠ a SPŠE Františka Křižíka**), která automaticky sleduje sdílenou složku s HTML exporty z desktopového programu **Bakaláři – Suplování** a zobrazuje přehled suplování pro třídy i učitele na mobilu a počítači.

- **Bez zásahu do Bakalářů:** Aplikace nepřistupuje k databázi ani API Bakalářů; pouze čte (read-only) exportované HTML soubory (FastReport 5.0).
- **100% lokální provoz (Offline-first):** Žádné cloudové služby, žádná telemetrie, žádné externí CDN. Funguje bez přístupu k internetu ve školním intranetu.
- **Spolehlivost na SMB/CIFS:** Kombinuje `watchdog` a záložní polling (`30 s`) s kontrolou dokončení zápisu (`2 s` stabilní velikost a `mtime`).
- **Ochrana při selhání (F6):** Pokud se změní formát exportu nebo je nahrán poškozený soubor, aplikace **zachová poslední platná data**, zobrazí varování *„Nelze zpracovat nový export“* a zaloguje chybu i na `/admin/status`.
- **Anonymizovaný režim a statický export (`export-static`):** Možnost přepnutí do režimu zkratek/iniciál bez plných jmen a vygenerování statického webu do složky `dist/`.

---

## Rychlé spuštění v Dockeru (doporučeno pro produkci)

1. Zkopírujte ukázkovou konfiguraci prostředí a upravte cestu ke sdílené složce s HTML exporty (`HOST_EXPORTS_DIR`):
   ```bash
   cp .env.example .env
   ```
2. Spusťte aplikaci jedním příkazem:
   ```bash
   docker compose up -d
   ```
3. Otevřete v prohlížeči:
   - **Přehled suplování:** `http://localhost:8000`
   - **Stav systému pro správce:** `http://localhost:8000/admin/status`

> Složka s exporty je v `docker-compose.yml` připojena výhradně v režimu pro čtení (`:ro`). Databáze SQLite je uložena ve složce `./data/` a rotované logy v `./logs/`.

---

## Lokální instalace a spuštění (bez Dockeru)

Vyžaduje **Python 3.12+** (kompatibilní s Python 3.11–3.14).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Spuštění webového serveru a sledování složky
python -m app serve --host 0.0.0.0 --port 8000
```

---

## Generování statické anonymizované verze (`export-static`)

Pro publikování mimo intranet (kde nesmí být uvedena žádná plná jména učitelů) spusťte příkaz:

```bash
python -m app export-static --watch-dir ./samples --output ./dist
```

Příkaz vygeneruje kompletní statickou aplikaci (HTML + CSS + JS + PWA + JSON data jednotlivých dnů) do složky `dist/`, kde jsou veškerá jména vyučujících nahrazena zkratkami nebo iniciálami.

---

## Konfigurace (`config.yaml` a `.env`)

Konfiguraci lze měnit v souboru `config.yaml` nebo pomocí proměnných prostředí (`.env`):

| Proměnná prostředí | Klíč v `config.yaml` | Výchozí hodnota | Popis |
|---|---|---|---|
| `SUPL_WATCH_DIR` | `watch_dir` | `./samples` | Cesta ke sledované složce s HTML exporty |
| `SUPL_FILE_PATTERN` | `file_pattern` | `*.htm*` | Maska sledovaných souborů |
| `SUPL_DB_PATH` | `db_path` | `./data/suplovani.db` | Cesta k SQLite databázi |
| `SUPL_LOG_DIR` | `log_dir` | `./logs` | Složka pro rotované JSON logy |
| `SUPL_POLL_INTERVAL_SECONDS` | `poll_interval_seconds` | `30.0` | Interval záložního pollingu (SMB/CIFS) |
| `SUPL_STABILITY_SECONDS` | `stability_seconds` | `2.0` | Doba klidu souboru před čtením (dokončení zápisu) |
| `SUPL_RETENTION_DAYS` | `retention_days` | `14` | Počet dní historie v DB (starší se mažou) |
| `SUPL_STALE_THRESHOLD_HOURS` | `stale_threshold_hours` | `24.0` | Práh pro zobrazení varování o zastaralosti dat |
| `SUPL_ANONYMIZE` | `anonymize` | `false` | `true` = zobrazovat pouze zkratky/iniciály bez jmen |
| `SUPL_ADMIN_USERNAME` | `admin_username` | `admin` | Uživatelské jméno pro `/admin/status` |
| `SUPL_ADMIN_PASSWORD` | `admin_password` | *(prázdné)* | Heslo pro `/admin/status` (HTTP Basic Auth) |
| `SUPL_ADMIN_ALLOWED_CIDRS` | `admin_allowed_cidrs` | privátní IP rozsahy | Povolené IP podsítě pro `/admin/status` |

---

## Testování a kontrola kvality kódu

```bash
# Spuštění všech unit a integračních testů
.venv/bin/pytest -v

# Kontrola linterem Ruff
.venv/bin/ruff check .

# Striktní typová kontrola Mypy
.venv/bin/mypy app tests
```

---

## Řešení problémů (Troubleshooting)

1. **Nový soubor ve sdílené složce se nezobrazí:**
   - Zkontrolujte `/admin/status`, zda běží `Watcher` a jaký je stav posledního importu.
   - Ujistěte se, že soubor má příponu `.html` nebo `.htm` a nezačíná tečkou.
   - Při uložení na síťový disk SMB/CIFS může trvat až `30 s` (interval záložního pollingu) + `2 s` (kontrola dopsání souboru), než se změna projeví.
2. **Zobrazuje se červené varování „Nelze zpracovat nový export“:**
   - Poslední platná data jsou zachována. Na `/admin/status` zkontrolujte text chyby. Nejčastěji byla z Bakalářů omylem vyexportována jiná sestava místo *Přehledu suplování pro třídy*. Podrobný postup je v `docs/provoz.md`.
3. **Špatná diakritika u starších exportů:**
   - Aplikace detekuje kódování automaticky (`UTF-8`, `windows-1250` / `cp1250`, `ISO-8859-2`). Není nutné měnit nastavení v Bakalářích.

---

## Dokumentace v repozitáři

- [`docs/format-analysis.md`](docs/format-analysis.md) – Detailní rozbor surového HTML z FastReportu 5.0 a návrh datového modelu.
- [`docs/architecture.md`](docs/architecture.md) – Architektura aplikace a diagram toku dat (`složka → parser → DB → web`).
- [`docs/provoz.md`](docs/provoz.md) – Provozní příručka pro IT správce (postup při změně exportu nebo výpadku).
- [`docs/navod-zastupkyne.md`](docs/navod-zastupkyne.md) – Jednostránkový návod pro zástupkyni ředitele.
