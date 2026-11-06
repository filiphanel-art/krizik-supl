# Implementation Plan: Hybridní integrace webu zmeny.aspx, oficiální slovník zkratek a indikátory UI

## Summary
Tento implementační plán rozšiřuje aplikaci **Suplování Viewer (Křižík)** o podporu hybridního vícezdrojového získávání dat a kompletní oficiální adresář pedagogů:
1. **Oficiální slovník pedagogů (`Učitelé_zkratky.xlsx`)**: Integrace kompletního adresáře 55 pedagogů VOŠ a SPŠE Františka Křižíka do výchozí konfigurace (`config.yaml`) a databáze pro 100% spolehlivé párování zkratek na plná jména i anonymizaci.
2. **Webový parser pro `next/zmeny.aspx` (`app/parser_web.py`)**: Samostatný robustní parser pro jednodenní HTML výstupy z webové aplikace Bakalářů (parsování data z `#DateEdit_I`, tabulek `Nepřítomné třídy`, `Nepřítomní učitelé`, `Místnosti mimo provoz` a `Změny v rozvrzích tříd` včetně titulkových atributů `title` pro jména pedagogů).
3. **Odolný periodický web fetcher (`app/fetcher.py`)**: Asynchronní stahovač postavený na `httpx` s ochranou proti častým pádům webu Bakalářů (detekce a bezpečný záchyt HTTP 503 Service Unavailable, 500, timeoutů a síťových chyb bez pádu služby, uplatnění exponenciálního backoffu).
4. **Hybridní SQLite úložiště & slučovací strategie (`app/database.py`)**: Rozšíření schématu o příznak `data_source` (`'file'` | `'web'`), čas získání `fetched_at` a kontrolní hash. Slučovací logika zachovává týdenní přehled z desktopového souboru a aktualizuje vybraný den z webu pouze tehdy, pokud je web novější nebo pokud soubor pro daný den chybí. Při výpadku webu zůstávají v databázi netknutá poslední platná data.
5. **Rozšíření API (`/api/schedule`, `/api/status`)**: Expozice informací o zdroji pro každý den (`data_source`, `source_label`), časového razítka a stavu webového fetcheru.
6. **Indikátory v uživatelském rozhraní (`index.html`, `app.js`, `styles.css`)**:
   - Vizuální stavový indikátor **Online / Offline** v záhlaví s barevným pulzujícím bodem a přístupností pro čtečky obrazovky (`aria-live`).
   - Přesný indikátor zdroje dat pro zobrazený den: **"Zdroj: Soubor (Bakaláři export)"** vs. **"Zdroj: Web (klasifikace.skolakrizik.cz)"**.

## Interfaces

### 1. Oficiální slovník zkratek učitelů (`config.yaml` / `app/config.py`)
55 oficiálních zkratek pedagogů z `Učitelé_zkratky.xlsx` je uloženo do `teacher_codes` v `config.yaml` (např. `Ko: "Kodad Miloš"`, `Vl: "Valtr Pavel"`, `Bj: "Bajerová Markéta"`, `Hf: "Hanel Filip"`). Tento slovník slouží jako primární autorita pro dekódování zkratek i pro anonymizační modul.

### 2. Backendové modely a parser (`app/models.py`, `app/parser_web.py`)
- **Rozšíření `ScheduleDay`**:
  - `data_source: str = "file"` (`"file"` | `"web"`)
  - `source_label: str = "Soubor (Bakaláři export)"`
  - `fetched_at: str = ""` (ISO 8601)
- **Funkce `parse_web_zmeny_html(html_content: str | bytes, known_teachers: dict[str, str] | None = None) -> ParseResult`**:
  - Parsování data z `#DateEdit_I` (formát `DD.MM.YYYY`), záložně z `h1`.
  - Parsování tabulek `datagrid`: Nepřítomné třídy, Nepřítomní učitelé (s mřížkou 1..10 a zkratkami), Místnosti mimo provoz.
  - Parsování tabulky Změny v rozvrzích tříd: třída, hodina od-do, předmět, učebna, typ změny (`odpadá`, `spojí`, `supluje`, `změna`), suplující učitel (včetně `title`), původní učitel.

### 3. Asynchronní Web Fetcher (`app/fetcher.py`)
- **Třída `WebFetcher`**:
  - Metody `async def fetch_once() -> bool`, `async def run_loop(stop_event: asyncio.Event) -> None`.
  - `httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=True)`.
  - Whitelist cílových hostitelů: `["klasifikace.skolakrizik.cz"]` s validací schématu `https://`.
  - Bezpečný záchyt `HTTPStatusError` (503, 502, 500), `TimeoutException`, `RequestError`.
  - Interval dotazování: výchozí 300 s (konfigurovatelné `SUPL_WEB_POLL_INTERVAL_SECONDS`).

### 4. Hybridní databázové úložiště (`app/database.py`)
- Rozšíření tabulky `schedule_days` o sloupce `data_source`, `source_label`, `fetched_at`, `source_hash`.
- Metoda `save_web_day(day: ScheduleDay, source_hash: str)`:
  - Aktualizuje výhradně jediný den $D$, ostatní dny týdne ponechává nedotčené.
  - Pokud stávající den pochází ze souboru a je novější než web, soubor má přednost.
  - Při chybě webu zůstávají v platnosti poslední uložená data.

### 5. Frontendové komponenty (`app.js`, `styles.css`, `index.html`)
- **Indikátor Online / Offline (`#connection-indicator`)**:
  - Pulzující zelený bod pro Online, výrazný červený pro Offline.
  - Sledování událostí sítě i úspěšnosti API volání.
- **Indikátor zdroje dat (`#source-badge`)**:
  - Umístění v ovládací liště vedle nadpisu dne.
  - Zobrazení: `Zdroj: Soubor (Bakaláři export)` nebo `Zdroj: Web (klasifikace.skolakrizik.cz)` s odpovídající ikonou a CSS třídou.

## Dependencies
- **HTTPX (`>=0.27.0`)**: Přidáno do `pyproject.toml` (BSD-3-Clause, 0 známých CVE).
- Ostatní knihovny beze změny: BeautifulSoup4, lxml, FastAPI, Pydantic, Watchdog.

## Test Specs
| Test ID | Typ testu | Testovací scénář a Edge-cases | Očekávaný výsledek |
|---|---|---|---|
| `TEST-TEACHERS-DICT-01` | Unit | Načtení 55 učitelů z konfigurace `teacher_codes`. | Slovník obsahuje přesně 55 kódů (např. `Ko -> Kodad Miloš`, `Vl -> Valtr Pavel`, `Hf -> Hanel Filip`). |
| `TEST-WEB-PARSE-01` | Unit | Parsování reálného souboru `samples/zmeny_web_sample.html`. | Datum úspěšně detekováno jako `2026-11-06`, den `Pátek`. Extrahovány třídy, učitelé i místnosti. Všechny změny v rozvrzích tříd (1A, 1B, 4D, V2) naparsovány. |
| `TEST-WEB-PARSE-02` | Unit | Parsování titulkových atributů `title` u učitelů (např. `<span title="Blažek Martin">Ba</span>`). | Zkratky jsou správně provázány na plná jména ve slovníku `known_teachers`. |
| `TEST-FETCH-RESILIENCE-01` | Integration | Webový server vrací HTTP 503 nebo timeout. | `WebFetcher` odchytí chybu, zapíše varování do logu, aplikace nespadne, existující data v DB zůstanou zachována. |
| `TEST-STORAGE-HYBRID-01` | Integration | V databázi je týdenní soubor (Po–Pá). Stažen web pro pátek (`data_source = 'web'`). | Po–Čt mají `data_source = 'file'`, Pátek má `data_source = 'web'`. Žádný jiný den nebyl smazán. |
| `TEST-API-SOURCE-01` | Integration | Volání `/api/schedule` pro den ze souboru a z webu. | JSON obsahuje pole `data_source` a `source_label`. |
| `TEST-UI-INDICATORS-01` | DOM/Frontend | Simulace stavu online/offline a přepnutí zdroje dat. | Indikátor Online/Offline reaguje na stav sítě, štítek zdroje zobrazuje správný text. |

## Security Considerations
1. **SSRF prevence**: Striktní whitelist domény `klasifikace.skolakrizik.cz`, vynucení HTTPS, zákaz privátních a cloud metadata IP adres.
2. **DoS a Resource Exhaustion**: Connect timeout 5 s, read timeout 10 s, limit velikosti odpovědi 5 MB, minimální interval mezi dotazy 60 s.
3. **XSS ochrana**: Veškerý obsah z HTML webu Bakalářů je vkládán do DOMu výhradně přes `textContent`.

## Open Questions & Doporučení
1. *Frekvence stahování webu:* Doporučujeme výchozí interval 5 minut (300 s) s okamžitým záchytem 503 a odložením dalšího pokusu o 1 minutu.
2. *Priorita při shodném datu:* Doporučujeme, aby souborový export měl přednost před webem, pokud je soubor novější (má vyšší nebo rovné `exported_at`). Pokud je soubor starší než web, web aktualizuje daný den.
