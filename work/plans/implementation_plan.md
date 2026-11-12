# Implementační plán: Optimalizace přepínání dnů, odolnosti stahování a aktualizace GitHub Pages

## 1. Summary
1. Dopředné stahování: dnešek + až 2 dny dopředu (`web_max_forward_days = 2`, konfigurovatelné). V pátek ButtonNext vrací pondělí (1. krok).
2. GitHub Pages se aktualizuje samo bez scope `workflow`: lokální skript `scripts/sync_gh_pages.sh` + macOS LaunchAgent (každých 30 min).
3. Retence DB (`cleanup_old_days`) i pro webový fetcher a statický export.
4. Deduplikace `save_web_day` podle `source_hash`; SSE jen při skutečné změně.
5. Klient: přeskočit zbytečný re-render, ranní rollover na GitHub Pages, cache-busting, `Cache-Control`, sjednocení verze service workeru.
6. Okno Po–Po se posouvá samo (compute_school_week_dates, rollover) – ověřit testem, nerozbít.

## 2. Interfaces & Data Flow
- `app/config.py`, `config.yaml`: `web_max_forward_days: int = Field(default=2, ge=0, le=5)`, env `SUPL_WEB_MAX_FORWARD_DAYS`.
- `Storage.save_web_day(day, source_hash) -> bool`: pokud existuje řádek se stejným `source_hash` -> vrátit False bez zápisu; jinak zapsat, vrátit True. Zachovat chování, že web má přednost před souborem.
- `WebFetcher.fetch_once`: `max_forward_days = config.web_max_forward_days`; `on_update` jen když `save_web_day` vrátí True; po cyklu `storage.cleanup_old_days(config.retention_days)`. Výpadek nikdy nemaže data.
- `export_static_site`: před exportem `cleanup_old_days`; export jen dnů v retenci + okno; JSON kompaktně (bez indent=2), pokud to nerozbije testy.
- `app/web.py`: `Cache-Control: no-cache, no-store, must-revalidate` na `/api/schedule`, `/api/status`, `/api/fetch-web`.
- `app/static/app.js` (+ `dist/app.js`): v `loadData` při shodném payloadu (dates + day) jen aktualizovat časový štítek, nevolat `renderAll`; ve statickém exportu `index.json?_t=Date.now()` a `day-*.json?_t=`; při `!state.userManuallySelectedDate` vždy znovu `chooseDefaultDate`; zachovat Po–Po a rollover půlnoci.
- `app/static/sw.js`: `CACHE_NAME = "krizik-supl-v19"` (shodně s `?v=19`).
- `scripts/sync_gh_pages.sh` (+ `--dry-run`): aktivuje `.venv`, `python -m app export-static`, ověří `dist/data/index.json`, push `git subtree split --prefix dist` do `gh-pages` (--force). `scripts/cz.skolakrizik.suplovani.ghpages.plist` (LaunchAgent, StartInterval 1800) + stručný návod do `docs/provoz.md`.

## 3. Dependencies
Žádné nové (fastapi, httpx, beautifulsoup4, pydantic, pyyaml; bash/launchd nativně).

## 4. Test Specs
| ID | Scénář | Očekávání |
|---|---|---|
| TEST-FETCHER-FORWARD-2-DAYS-01 | Středa, forward=2 | 1 GET + 2 POST, uloženy St, Čt, Pá |
| TEST-FETCHER-FRIDAY-TO-MONDAY-01 | Pátek, ButtonNext přes víkend | v 1. kroku uloženo pondělí |
| TEST-STORAGE-SAVE-WEB-DEDUPLICATION-01 | stejný hash 2x | True, pak False, updated_at nezměněn |
| TEST-FETCHER-NO-SSE-ON-UNMODIFIED-01 | identický obsah | on_update nezavolán |
| TEST-WEB-RETENTION-ON-FETCH-01 | dny starší 14 dní | smazány po fetchi |
| TEST-API-CACHE-CONTROL-HEADERS-01 | GET /api/schedule, /api/status | hlavička no-cache |
| TEST-APP-JS-SKIP-IDENTICAL-RENDER-01 | stejný payload | renderAll se nevolá |
| TEST-WEEK-WINDOW-ROLLOVER-01 | So/Ne a Po po víkendu | okno Po–Po se posune na nový týden |
| TEST-GH-PAGES-SYNC-SCRIPT-VALID-01 | `--dry-run` | skript projde, bez pushe |
| TEST-SW-CACHE-VERSION-01 | sw.js | CACHE_NAME == krizik-supl-v19 |

## 5. Security Considerations
SSRF `validate_web_url` beze změny; skript nepíše tajemství do logů, pushuje jen do `gh-pages`; anonymizace exportu zachována; nulový `innerHTML`; retence v transakci s `PRAGMA foreign_keys = ON`.

## 6. Open Questions
Kde poběží sync (Mac LaunchAgent vs. cron na 10.20.0.81) – implementujeme Mac LaunchAgent, cron varianta jen v dokumentaci.
