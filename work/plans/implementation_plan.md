# Implementační plán: Oprava DevExpress DateEdit$State pro více-denní stahování, statický export a přepínání dnů

## 1. Summary

### Popis problému a kořenové příčiny
Uživatel nahlásil:
> „na localhostu a na githubu nefunguje to denní přepínání a taky jsem chtěl abych tam měl vždy načtený tři dny dopředu což bude ze suplovani.skolakrizik.cz ale 2 dny dopředu pokud existuje“

Analýzou živého serveru Bakalářů (`https://klasifikace.skolakrizik.cz/next/zmeny.aspx`, kam přesměrovává `https://suplovani.skolakrizik.cz/`) a lokálního prostředí byly odhaleny přesné příčiny:

1. **Chybějící skryté pole `DateEdit$State` při POST požadavku `ButtonNext` (`app/fetcher.py`)**:
   - Komponenta DevExpress `ASPxClientDateEdit` (`DateEdit`) ve statickém HTML vykresluje prázdný `<input type="hidden"/>` bez atributu `name` a hodnotu `rawValue` (např. `'1794268800000'` pro `10.11.2026`) předává v inline JavaScriptu:
     `ASPx.createControl(ASPxClientDateEdit,'DateEdit','',{'autoPostBack':true,...,'stateObject':{'rawValue':'1794268800000','useMinDateInsteadOfNull':false}...})`.
   - V prohlížeči DevExpress skript při načtení stránky dynamicky vytvoří pole `DateEdit$State` s JSON hodnotou `{"rawValue":"1794268800000","useMinDateInsteadOfNull":false}`.
   - Protože `extract_asp_form_inputs()` parsoval pouze statické `<input name="...">` tagy, pole `DateEdit$State` v POST požadavku chybělo. Server Bakalářů proto při stisku `ButtonNext` nevěděl, z jakého dne vychází, a vrátil výchozí historické datum z ViewState (`03.11.2026`), které bylo vyhodnoceno jako `<= 2026-11-10` a dopředné stahování se zastavilo.
   - Při doplnění `DateEdit$State` server Bakalářů na `ButtonNext` správně vrací:
     - Krok 0 (GET): `2026-11-10` (Úterý, 12 změn)
     - Krok 1 (POST `ButtonNext`): `2026-11-11` (Středa, 17 změn)
     - Krok 2 (POST `ButtonNext`): `2026-11-12` (Čtvrtek, 29 změn)
     - Krok 3 (POST `ButtonNext`): `2026-11-12` (Pátek zatím nepublikován -> vrátí stejné datum -> čisté zastavení).

2. **`export-static` (`app/cli.py` / `app/static_export.py`) před exportem nespouštěl `WebFetcher.fetch_once()`**:
   - Příkaz `python -m app export-static` volal pouze `FolderWatcher.scan_once()` nad složkou `./samples` (kde byl jen vzorek z pondělí `2026-11-09`).
   - V `dist/data/index.json` proto mělo `has_data: true` pouze pondělí `2026-11-09` a úterý `10. 11.`, středa `11. 11.` i čtvrtek `12. 11.` měly `has_data: false` (zašedlé a neklikatelné). Aplikace proto vybrala jediné dostupné datum `Pondělí 9. 11.` a neumožnila přepnout na úterý, středu ani čtvrtek.

3. **Rozšíření dopředného stahování až na 3 dny dopředu (`max_forward_days = 3`) a podpora `suplovani.skolakrizik.cz`**:
   - Navýšení `max_forward_days` v `WebFetcher.fetch_once()` na `3`, takže pokud škola publikuje 1, 2 nebo 3 dny dopředu, stáhnou se všechny publikované dny.
   - Ošetření URL `https://suplovani.skolakrizik.cz/next/zmeny.aspx` (která na Apache vrací 404, zatímco kořen `https://suplovani.skolakrizik.cz/` přesměrovává 302 na `https://klasifikace.skolakrizik.cz/next/zmeny.aspx`).

4. **Stabilita 6denního okna při kliknutí na následující pondělí v `/api/schedule` (`app/web.py`)**:
   - V `api_schedule` se volalo `storage.list_school_week_dates(reference_date=date)`. Pokud uživatel klikl na 6. záložku (následující pondělí `2026-11-16`), posunulo se celé okno záložek na další týden. Okno záložek musí zůstat ukotvené k aktuálnímu týdnu (`reference_date=None`), pokud je vybrané datum součástí aktuálního 6denního okna.

5. **Periodická kontrola a půlnoční přepnutí i na GitHub Pages (`app/static/app.js`)**:
   - V `setupLiveUpdates()` byl předčasný návrat `if (state.isStaticExport) return;`, který na GitHub Pages vypnul nejen SSE `EventSource`, ale i 25s časovač `checkCalendarDayAndRefresh(false)`. Časovač bude spuštěn i ve statickém režimu (mimo Node.js testovací běh), aby GitHub Pages průběžně načítaly čerstvý `index.json` a po půlnoci automaticky přešly na nový den.

---

## 2. Interfaces & Data Flow

### 2.1 `app/fetcher.py`
- **`extract_asp_form_inputs(html_content: str | bytes, button_name: str = "ButtonNext") -> tuple[str, dict[str, str]]`**:
  - Kromě standardních `<input>`, `<select>`, `<textarea>` a `<button>` prvků vyhledá v textu HTML inicializaci DevExpress `ASPxClientDateEdit`:
    ```python
    # Regex pro extrakci unikátního ID DateEditu a rawValue ze stateObject
    # Např. ASPx.createControl(ASPxClientDateEdit,'DateEdit','',{'autoPostBack':true,...,'stateObject':{'rawValue':'1794268800000','useMinDateInsteadOfNull':false}
    ```
  - Pokud v `data` dosud není `<date_edit_id>$State` a v HTML je nalezeno `rawValue`, zapíše:
    `data[f"{date_edit_id}$State"] = f'{{"rawValue":"{raw_val}","useMinDateInsteadOfNull":false}}'`.
  - Podporuje tlačítko `button_name` jak při přímé shodě (`name == button_name`), tak při ASP.NET prefixu (`name.endswith(f"${button_name}")` nebo `name.endswith(f":{button_name}")`).
- **`WebFetcher.fetch_once()`**:
  - `max_forward_days = 3` (stahuje dnešek + až 3 následující publikované dny; pokud jsou publikovány jen 2 dny dopředu, po 2. dni se čistě zastaví díky `day_next.date <= last_date`).
  - Pokud je v konfiguraci nastavena URL na `suplovani.skolakrizik.cz/next/zmeny.aspx` a server vrátí 404, nebo při normalizaci pro `suplovani.skolakrizik.cz`, použije kořen `https://suplovani.skolakrizik.cz/` (který přesměruje 302 na `https://klasifikace.skolakrizik.cz/next/zmeny.aspx`).
  - Odstranění předčasného přeskočení `if content_hash == self.last_hash: return True` před dopředným stahováním, neboť dopředné dny mohly přibýt nebo nemusí být v DB kompletní; místo toho uloží aktuální i dopředné dny.

### 2.2 `app/static_export.py` a `app/cli.py`
- **`export_static_site(config: AppConfig, output_dir: Path = Path("./dist"), fetch_online: bool = False) -> dict[str, int]`**:
  - Pokud `fetch_online and config.web_enabled`:
    Spustí `WebFetcher(config, storage, logger=logger).fetch_once()` (přes `asyncio.run()`) před čtením databáze a generováním `dist/data/`. Případné síťové chyby bezpečně zaloguje a pokračuje exportem dat z lokální SQLite databáze.
- **`app/cli.py`**:
  - Při příkazu `export-static` volá `export_static_site(config, output_dir=Path(args.output_dir), fetch_online=True)`.

### 2.3 `app/web.py`
- **`api_schedule`**:
  ```python
  current_week_dates = storage.list_school_week_dates(reference_date=None)
  if date and not any(d["date"] == date for d in current_week_dates):
      dates = storage.list_school_week_dates(reference_date=date)
  else:
      dates = current_week_dates
  selected_date = date if (date and any(d["date"] == date for d in dates)) else _choose_default_date(dates)
  ```

### 2.4 `app/static/app.js` a `dist/app.js`
- **`setupLiveUpdates()`**:
  - `EventSource("/api/events")` se spouští pouze pokud `!state.isStaticExport`.
  - Periodický `setInterval(() => checkCalendarDayAndRefresh(false), 25000)` se spouští jak na serveru/localhostu, tak na GitHub Pages (`state.isStaticExport === true`), pokud neběží v Node.js unit testu (`!(typeof process !== "undefined" && process.versions && process.versions.node)`).

---

## 3. Dependencies

Žádné nové externí závislosti nejsou přidávány. Využívají se stávající knihovny (`httpx`, `beautifulsoup4`, `lxml`, `fastapi`, `pydantic`).

---

## 4. Test Specs

| Test ID | Typ | Scénář / Edge-cases | Očekávaný výsledek |
|---|---|---|---|
| `TEST-ASP-DEVEXPRESS-STATE-01` | Unit | HTML obsahuje `ASPx.createControl(ASPxClientDateEdit,'DateEdit','',{'stateObject':{'rawValue':'1794268800000','useMinDateInsteadOfNull':false}})` | `extract_asp_form_inputs` vloží do slovníku `DateEdit$State` s `{"rawValue":"1794268800000","useMinDateInsteadOfNull":false}` |
| `TEST-ASP-FORM-PREFIXED-BUTTON-01` | Unit | Tlačítko má v HTML atribut `name="ctl00$cphmain$ButtonNext"` | `extract_asp_form_inputs` detekuje tlačítko a přidá klíč `ctl00$cphmain$ButtonNext` |
| `TEST-FETCHER-3-DAYS-FORWARD-01` | Integration | Server má publikované změny na dnešek + 3 následující dny | `fetch_once()` provede 1 GET a 3 POSTy (s `DateEdit$State`), do SQLite uloží všechny 4 dny |
| `TEST-FETCHER-CLEAN-STOP-2-DAYS-02` | Integration | Server má publikované změny na dnešek + 2 dny dopředu (3. POST vrátí stejné datum) | `fetch_once()` uloží 3 dny (dnešek + 2 dny dopředu) a po 3. POSTu se čistě zastaví se statusem `SUCCESS` |
| `TEST-STATIC-EXPORT-FETCH-ONLINE-01` | Integration | Volání `export_static_site(cfg, output_dir, fetch_online=True)` | Před exportem zavolá `WebFetcher.fetch_once()` a vygeneruje `day-*.json` i `index.json` (`has_data: true`) pro všechny stažené dny |
| `TEST-API-SCHEDULE-WEEK-WINDOW-STABLE-01` | Integration | Dotaz `GET /api/schedule?date=<následující_pondělí>` v rámci aktuálního 6denního okna | Vrácené pole `dates` zůstává ukotveno na aktuální týden (Po–Pá + následující Po) a neposouvá se o týden dopředu |
| `TEST-STATIC-LIVE-UPDATES-POLLING-01` | Unit (JS) | Spuštění `setupLiveUpdates()` při `state.isStaticExport = true` v prohlížeči | Nevytváří `EventSource`, ale zaregistruje periodický `setInterval` pro kontrolu dat a přechod dne |

---

## 5. Security Considerations

1. **SSRF prevence**: Veškeré GET i POST požadavky (včetně případných redirectů ze `suplovani.skolakrizik.cz` na `klasifikace.skolakrizik.cz`) prochází `validate_web_url()` a request hookem `_validate_request_hook`.
2. **Bezpečná extrakce `rawValue`**: Z JavaScriptového bloku se extrahuje výhradně číselný timestamp `\d+` pomocí striktního regulárního výrazu – žádné vyhodnocování JS kódu (`eval`).
3. **XSS ochrana**: Žádné použití `innerHTML`.
4. **Anonymizace**: Statický export pro GitHub Pages (`dist/data/*.json`) anonymizuje všechna jména učitelů na zkratky i pro nově stažené dopředné dny.
