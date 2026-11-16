# Implementační plán: Automatický posun dne a týdne na GitHub Pages a blesková synchronizace bez GitHub Actions

## 1. Summary
Tento implementační plán řeší nesoulad mezi chováním na localhostu a na GitHub Pages (`filiphanel-art.github.io`), kde na GitHub Pages docházelo k zamrznutí na starém týdnu a nezobrazoval se posun dne/týdne. Dále řeší požadavek uživatele na automatickou aktualizaci dat několikrát denně během několika sekund, striktně **bez pomalých GitHub Actions**.

### Klíčové příčiny problému:
1. **Statický obsah `dates` v `index.json`**:
   - `dist/data/index.json` obsahoval pole `dates` napevno vygenerované při minulém exportu (12. 11. 2026), tj. pondělí 9. 11. až pátek 13. 11. + pondělí 16. 11. (s `has_data: false`).
2. **Absence klientského přepočtu 6denního okna v `app.js`**:
   - V `app/static/app.js` ve funkci `fetchSchedulePayload()` v režimu `state.isStaticExport === true` klient nekriticky převzal pole `idxData.dates` z `index.json`. Na rozdíl od localhostu (kde `/api/schedule` při každém requestu volá dynamické `compute_school_week_dates(reference_date=None)` podle dnešního pražského data) klientský kód okno nepřepočítával.
   - Ve funkci `chooseDefaultDate()` navíc pondělí 16. 11. mělo `has_data: false`, takže klient spadl zpět na pondělí 9. 11.!
3. **Absence automatického exportu a pushování v běžícím serveru**:
   - Běžící server na localhostu (`WebFetcher`) sice každých 5 minut úspěšně stahuje čerstvá data z webu Bakalářů do SQLite (`data/suplovani.db`), ale po stažení dat ani po přechodu půlnoci nepřegenerovával složku `dist/` ani nepouštěl synchronizaci do větve `gh-pages`.
4. **Zákaz GitHub Actions**:
   - Uživatel výslovně nechce používat GitHub Actions („Nechci použít github action ten trvá dlouho a taky to má sledovat několikrát denně“). Odstraníme `scripts/update-gh-pages.yml` a příslušný test nahradíme testy přímé synchronizace a klientského přepočtu okna.

---

## 2. Interfaces & Data Flow

### 2.1 Rozhraní v JavaScriptu (`app/static/app.js` a `dist/app.js`)
```javascript
/**
 * Vypočítá 6denní řadu školního týdne (Po-Pá + Po příštího týdne) pro statický export.
 * Zajišťuje 100% paritu s python funkcí compute_school_week_dates() v app/database.py.
 *
 * @param {string|null} referenceDateIso - Referenční datum ve formátu YYYY-MM-DD (null/"" = getPragueCalendarDate())
 * @param {Array<Object>} indexDates - Původní pole dates z index.json (pro zachování metadat)
 * @param {Array<string>} availableDates - Seznam existujících dat z index.json (available_dates)
 * @returns {Array<Object>} 6 položek pro dny Po-Pá a Po následujícího týdne
 */
function computeClientSchoolWeekDates(referenceDateIso, indexDates, availableDates)
```

**Pravidla `computeClientSchoolWeekDates`**:
- Pokud `referenceDateIso` není zadáno (nebo je součástí aktuálního týdne), použije `getPragueCalendarDate()`.
- Pro sobotu (den v týdnu 6) přičte 2 dny (následující pondělí), pro neděli (0) přičte 1 den (následující pondělí), pro Po–Pá odečte `weekday - 1` dnů.
- Vygeneruje 6 dnů s posuny `[0, 1, 2, 3, 4, 7]` od pondělí (české názvy dnů: `Pondělí`, `Úterý`, `Středa`, `Čtvrtek`, `Pátek`).
- Pro každý den zjistí:
  - Pokud je den v `indexDates`, převezme jeho metadata (`exported_at`, `exported_at_display`, `updated_at`, `data_source`, `source_label`, `fetched_at`, `week_label`) a `has_data` nastaví na `Boolean(entry.has_data || (availableDates && availableDates.includes(isoStr)))`.
  - Pokud den není v `indexDates`, ale je v `availableDates`, nastaví `has_data: true`.
  - Jinak nastaví `has_data: false`.
- Exportovat `computeClientSchoolWeekDates` na `window` i `module.exports`.

**Datový tok v `fetchSchedulePayload(targetDate)` pro `state.isStaticExport`**:
1. Stáhne `./data/index.json?_t=<timestamp>`.
2. Zavolá `const computedDates = computeClientSchoolWeekDates(targetDate, idxData.dates || [], idxData.available_dates || []);` (kde pokud `targetDate` leží v aktuálním týdnu dle `getPragueCalendarDate()`, okno zůstává ukotveno k aktuálnímu týdnu).
3. Zvolí den: `const chosen = (targetDate && computedDates.some((d) => d.date === targetDate)) ? targetDate : chooseDefaultDate(computedDates);`.
4. Stáhne `./data/day-${chosen}.json?_t=<timestamp>`. Pokud `dayRes.ok`, načte `dayObj` a pokud měl vybraný den v `computedDates` `has_data === false`, nastaví mu `has_data = true` a doplní metadata z `dayObj`.
5. Vrátí `{ dates: computedDates, selected_date: chosen, day: dayObj, status: idxData.status || {} }`.

### 2.2 Rozhraní ve statickém exportéru (`app/static_export.py`)
Do `dist/data/index.json` doplnit pole `available_dates`:
```python
index_payload = {
    "dates": dates,
    "available_dates": sorted(dates_to_export),
    "status": { ... }
}
```

### 2.3 Rozhraní v konfiguraci (`app/config.py` a `config.yaml`)
V `AppConfig`:
```python
gh_pages_auto_push: bool = Field(default=False)
gh_pages_sync_script: Path = Field(default=Path("./scripts/sync_gh_pages.sh"))
```
- V `load_config`: mapování env proměnné `SUPL_GH_PAGES_AUTO_PUSH` (přes `_parse_bool`).
- V `config.yaml`: `gh_pages_auto_push: true`.

### 2.4 Automatický export a bleskový push ve `WebFetcher` (`app/fetcher.py`)
- V `__init__`: `self._last_exported_calendar_day: str = ""`
- V `fetch_once()` po `self.storage.cleanup_old_days(...)`:
  ```python
  today_iso = datetime.now(PRAGUE_TZ).date().isoformat()
  should_sync = saved_any or (self._last_exported_calendar_day != today_iso)
  if should_sync:
      self._last_exported_calendar_day = today_iso
      if self.config.gh_pages_auto_push:
          await self._trigger_static_sync()
  ```
- Metoda `async def _trigger_static_sync(self) -> bool`:
  - V bloku `try/except` spustí v `asyncio.to_thread` funkci `export_static_site(self.config, output_dir=Path("./dist"), fetch_online=False)`.
  - Pokud existuje skript `self.config.gh_pages_sync_script`, spustí v `asyncio.to_thread` `subprocess.run(["bash", str(script_path), "--skip-export"], check=False, capture_output=True, text=True, timeout=60)`.
  - Jakékoli selhání zaloguje jako `warning` a nikdy neshodí `fetch_once()`.

### 2.5 Úprava `scripts/sync_gh_pages.sh` a `scripts/cz.skolakrizik.suplovani.ghpages.plist`
- V `scripts/sync_gh_pages.sh` přidat podporu přepínače `--skip-export` (když už `export_static_site` proběhl v Pythonu, přeskočí spouštění `python -m app export-static` a rovnou publikuje `dist/` do větve `gh-pages` za ~1–2 sekundy).
- V `scripts/cz.skolakrizik.suplovani.ghpages.plist` nastavit `StartInterval` na `900` (15 minut).
- Odstranit soubor `scripts/update-gh-pages.yml` (GitHub Actions se nepoužívá).

---

## 3. Dependencies
Žádné nové externí závislosti.

---

## 4. Test Specs

| Test ID | Typ | Scénář | Očekávaný výsledek |
|---|---|---|---|
| `TEST-CLIENT-WEEK-CALC-MONDAY-01` | Unit (JS) | `computeClientSchoolWeekDates('2026-11-16', [], [])` | Vrátí 6 dnů: `2026-11-16` až `2026-11-20` + `2026-11-23` |
| `TEST-CLIENT-WEEK-CALC-WEEKEND-02` | Unit (JS) | `computeClientSchoolWeekDates('2026-11-14', [], [])` (sobota) a `'2026-11-15'` (neděle) | Posune okno na následující týden `2026-11-16` až `2026-11-23` |
| `TEST-CLIENT-STATIC-STALE-INDEX-ROLLOVER-03` | Unit (JS) | `index.json` má v `dates` starý týden `9. 11. – 16. 11.`, ale `available_dates` obsahuje `2026-11-16` a `2026-11-18` a dnešek je `2026-11-16` | `computeClientSchoolWeekDates` vrátí nový týden `16. 11. – 23. 11.` s `has_data: true` u `16. 11.` a `18. 11.` |
| `TEST-STATIC-EXPORT-AVAILABLE-DATES-04` | Unit (Py) | Spuštění `export_static_site()` | `dist/data/index.json` obsahuje pole `available_dates` se všemi exportovanými dny |
| `TEST-FETCHER-AUTO-SYNC-TRIGGER-05` | Integration (Py) | `WebFetcher.fetch_once()` s `gh_pages_auto_push=True` při `saved_any=True` | Zavolá `_trigger_static_sync()`, při dalším běhu beze změny a ve stejný den jej nevolá |
| `TEST-SYNC-SCRIPT-SKIP-EXPORT-06` | Integration (Bash) | `./scripts/sync_gh_pages.sh --dry-run --skip-export` | Ověří `dist/data/index.json` bez volání `export-static` a skončí s kódem 0 |

---

## 5. Security Considerations
- **SSRF ochrana**: `validate_web_url` beze změny.
- **Bezpečné spouštění subprocesu**: `subprocess.run(["bash", str(script_path), "--skip-export"], shell=False, timeout=60)` bez `shell=True`, žádné uživatelské vstupy.
- **Anonymizace**: `export_static_site` nadále anonymizuje všechna jména učitelů v `dist/data/*.json`.
- **XSS prevence**: Nulový výskyt `innerHTML`.
