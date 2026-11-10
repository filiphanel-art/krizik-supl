# Changelog

## [Unreleased]
### Added
- **Podpora DevExpress `ASPxClientDateEdit` `State` a prefixovaných tlačítek pro vícedenní stahování**:
  - `extract_asp_form_inputs()` v `app/fetcher.py` nyní bezpečně extrahuje `rawValue` z JavaScriptového bloku `ASPx.createControl(ASPxClientDateEdit, ...)` a doplňuje formulářové pole `DateEdit$State = {"rawValue":"...","useMinDateInsteadOfNull":false}` pro korektní POST dotazy na server Bakalářů.
  - Podpora ASP.NET prefixovaných tlačítek (`ctl00$cphmain$ButtonNext`, `$ButtonNext`, `:ButtonNext`).
- **Rozšíření dopředného stahování až na 3 dny dopředu a resilience pro `suplovani.skolakrizik.cz`**:
  - `max_forward_days` ve `WebFetcher.fetch_once()` navýšen na 3 publikované dny dopředu s čistým ukončením při detekci `day_next.date <= last_date`.
  - Automatická normalizace URL pro `suplovani.skolakrizik.cz` a fallback na `https://klasifikace.skolakrizik.cz/next/zmeny.aspx` při HTTP 404.
  - Odstraněn předčasný early return na shodu hashe před parsováním a dopředným stahováním.
- **Online stahování před statickým exportem (`export-static`)**:
  - `export_static_site()` v `app/static_export.py` podporuje parametr `fetch_online: bool = False`.
  - CLI příkaz `export-static` (`app/cli.py`) volá export s `fetch_online=True`, čímž před sestavením `dist/` stáhne z webu všechny publikované dny (dnešek + až 3 dny dopředu).
  - V `dist/data/index.json` mají nově stažené dny `has_data: true` a v `dist/data/` vznikají příslušné soubory `day-*.json`.
- **Stabilita 6denního týdenního okna v `/api/schedule`**:
  - V endpointu `/api/schedule` (`app/web.py`) je 6denní okno záložek ukotveno k aktuálnímu týdnu, takže kliknutí na 6. záložku (následující pondělí) neposune celé okno na další týden.
- **Periodická kontrola dat a půlnoční přepnutí na GitHub Pages**:
  - `setupLiveUpdates()` v `app/static/app.js` a `dist/app.js` spouští 25s kontrolní interval i ve statickém exportu (`state.isStaticExport === true`), což zajišťuje načítání čerstvých dat a půlnoční přechod na nový den na GitHub Pages.
- **Nové testovací specifikace**:
  - `TEST-ASP-DEVEXPRESS-STATE-01`, `TEST-ASP-FORM-PREFIXED-BUTTON-01`, `TEST-FETCHER-3-DAYS-FORWARD-01`, `TEST-FETCHER-CLEAN-STOP-2-DAYS-02`, `TEST-STATIC-EXPORT-FETCH-ONLINE-01`, `TEST-API-SCHEDULE-WEEK-WINDOW-STABLE-01` a `TEST-STATIC-LIVE-UPDATES-POLLING-01`.

### Added
- **Multi-day forward fetch (dopředné stahování až 2 následujících publikovaných dnů)**:
  - Implementována funkce `extract_asp_form_inputs(html_content, button_name="ButtonNext")` v `app/fetcher.py` pro bezpečnou extrakci ASP.NET formulářových polí (`__VIEWSTATE`, `__EVENTVALIDATION`, `__VIEWSTATEGENERATOR`, `DateEdit`, `FilterDropDown` atd.) a cílové action URL.
  - Ve `WebFetcher.fetch_once()` implementován iterativní dopředný fetch až 2 následujících publikovaných dnů pomocí POST dotazů s `ButtonNext: ""` a validací odchozích URL (`validate_web_url`).
  - Každý dopředný den je uložen do SQLite přes `Storage.save_web_day(day_next, source_hash)` s `source_label = f"Web ({host})"`.
  - Odolnost při dílčím síťovém výpadku dopředného dotazu: výpadek je bezpečně zalogován jako varování, stahování ukončeno a dnešek i dříve stažené dny zůstávají v SQLite nedotčeny.
- **Rozdělení chování Kiosku pro větev `main` a `kiosk-server`**:
  - `shouldAutoStartKiosk()` v `app/static/app.js` a `dist/app.js` na localhostu a GitHub Pages vrací striktně `false` (žádný automatický celoobrazovkový kiosk na desktopu vývojáře/uživatele).
  - Na serveru `10.20.0.81` nebo při `window.__AUTO_KIOSK__ === true` na desktopu automaticky spustí celoobrazovkový kiosk s autoscrollem.
  - Podporovány explicitní parametry `?kiosk=1` (vynucení kiosku kdekoli) a únikový `?kiosk=0` (vypnutí kiosku).
- **Nové testovací specifikace**:
  - `TEST-ASP-FORM-EXTRACT-01` a `TEST-ASP-FORM-NO-BUTTON-02` (extrakce ASP.NET formuláře).
  - `TEST-FETCHER-FORWARD-FETCH-01`, `TEST-FETCHER-FORWARD-STOP-SAME-DATE-02`, `TEST-FETCHER-FORWARD-PARTIAL-FAIL-03` a `TEST-FETCHER-OUTAGE-PRESERVES-DB-04` (dopředný fetch a odolnost).
  - `TEST-STORAGE-WEB-PRECEDENCE-05` (priorita webových dnů před týdenním souborovým importem).
  - `TEST-BRANCH-MAIN-DESKTOP-NO-KIOSK-01`, `TEST-BRANCH-MAIN-FORCE-KIOSK-PARAM-02`, `TEST-BRANCH-KIOSK-SERVER-AUTO-DESKTOP-03` a `TEST-BRANCH-KIOSK-SERVER-ESCAPE-HATCH-04` (chování kiosku v různých prostředích).
  - `TEST-UI-MULTI-DAY-TABS-ACTIVE-01` (aktivace záložek v 6denním kalendáři pro dopředné dny).
  - `TEST-STATIC-EXPORT-MULTI-DAY-FORWARD-01` (generování platných JSONů pro všechny dopředné dny v export-static).
  - `TEST-MIDNIGHT-ROLLOVER-AUTO-REFRESH-01` (půlnoční reset ručního výběru a přechod na aktuální den).

### Added
- **Kiosk fullscreen režim na serverovém desktopu**:
  - Funkce `shouldAutoStartKiosk()` automaticky aktivuje režim kiosk na serverovém desktopu (`!state.isStaticExport && !detectIsMobile()`) a při `?kiosk=1`. Podporován escape hatch `?kiosk=0` a zachováno standardní zobrazení na mobilních zařízeních.
  - Při startu aplikace se automaticky vyvolá `startKiosk()`, který aplikuje třídu `body.kiosk`, zobrazí tlačítko `#btn-kiosk-exit`, pokusí se o `requestFullscreen()` a registruje jednorázový posluchač uživatelského gesta (`click`, `touchstart`, `pointerdown`) pro okamžitou aktivaci nativního fullscreenu.
  - Zachována možnost opustit režim stiskem klávesy `Escape` nebo kliknutím na tlačítko `#btn-kiosk-exit`.
- **Podpora domény `suplovani.skolakrizik.cz` a dynamický `source_label`**:
  - Přidána školní subdoména `'suplovani.skolakrizik.cz'` do `ALLOWED_HOSTS` v `app/fetcher.py`.
  - Dynamické určení `source_label = f"Web ({host})"` v modulu `WebFetcher` podle cílové URL.
  - V `Storage.save_web_day` v `app/database.py` parametrizováno ukládání `day.source_label` namísto pevného řetězce.
- **Midnight & Morning rollover**:
  - Implementováno sledování kalendářního dne v časovém pásmu `Europe/Prague` (`getPragueCalendarDate()`).
  - Periodická smyčka (25 s) i SSE posluchač změn při přechodu půlnoci nebo vypršení nečinnosti v kiosku (300 s) resetují `state.userManuallySelectedDate = false` a volají `loadData("", false)`, čímž automaticky přejdou na aktuální den bez nutnosti restartu prohlížeče.
- **Nové testovací specifikace**:
  - Implementována sada 11 testů pokrývající všechny body implementačního plánu: `TEST-UI-SUPPRESS-STALE-BANNER-01`, `TEST-KIOSK-AUTO-START-DESKTOP-01`, `TEST-KIOSK-FIRST-CLICK-FULLSCREEN-01`, `TEST-KIOSK-EXIT-ESC-AND-BUTTON-01`, `TEST-FETCHER-ALLOWED-HOSTS-01`, `TEST-FETCHER-SOURCE-LABEL-DYNAMIC-01`, `TEST-FETCHER-DB-PRESERVATION-ON-FAILURE-01`, `TEST-FILE-IMPORT-PRESERVATION-ON-WATCHER-01`, `TEST-CALENDAR-MIDNIGHT-ROLLOVER-01`, `TEST-CALENDAR-MORNING-DATA-ARRIVAL-01` a `TEST-STATIC-EXPORT-VERSION-19-01`.

### Changed
- **Potlačení banneru zastaralosti dat (`#banner-stale`)**:
  - V `app/static/app.js` a `dist/app.js` v `renderBannersAndHeader` je banner `#banner-stale` trvale skryt třídou `hidden` a varovný text se v UI nezobrazuje. Diagnostika stáří dat na backendu (`/admin/status`, `/api/status`) zůstává netknutá.
- Verzování klientských assetů povýšeno na `styles.css?v=19` a `app.js?v=19` v `app/static/index.html` i `dist/index.html`.
- Přegenerován statický export `dist/` (`python -m app export-static`) a PDF dokumentace v `docs/` (`python scripts/generate_docs_and_pdfs.py`).

### Added
- **Oficiální název školy**: Nastaven na kratší jednotnou formu **„VOŠ a SPŠE Františka Křižíka“** v hlavičce `<h1>` (`#school-name`), v `app/parser_web.py` a normalizací v klientském JS.
- **Patička s copyrightem**: Přidána responzivní patička `<footer class="app-footer">` s textem `© 2026 VOŠ a SPŠE Františka Křižíka · Všechna práva vyhrazena`. V celoobrazovkovém režimu (kiosk) je automaticky skryta (`body.kiosk .app-footer { display: none !important; }`).
- **6denní řada školního týdne (Po–Pá + Po příštího týdne)**:
  - Implementována funkce `compute_school_week_dates(reference_date, stored_days)` a metoda `Storage.list_school_week_dates(reference_date)` v `app/database.py`, generující dny s offsety `[0, 1, 2, 3, 4, 7]` (např. 9. 11. – 13. 11. + 16. 11.) s příznakem `has_data: bool`.
  - Endpoint `/api/schedule` a statický export `dist/data/index.json` používají toto 6denní školní okno.
  - V klientském JS (`renderDateTabs`) mají dny bez suplování (`has_data: false`) třídu `.disabled`, atributy `disabled` a `aria-disabled="true"`, tooltip a zakázané klikání.
  - Funkce `chooseDefaultDate` automaticky preferuje nejbližší den s dostupnými daty (`has_data !== false`).
- **Nové testovací specifikace**: `TEST-FIX-DATASET-GETTER-01` (ověření v reálném headless prohlížeči Chromium přes Playwright), `TEST-SCHOOL-NAME-HEADER-01`, `TEST-FOOTER-HTML-01`, `TEST-CALENDAR-MONDAY-RANGE-01`, `TEST-CALENDAR-FLAGS-01`, `TEST-UI-DATE-TABS-DISABLED-01` a `TEST-STATIC-EXPORT-VERSION-18-01`.

### Changed
- Verzování assetů povýšeno na `styles.css?v=18` a `app.js?v=18` v šablonách i statickém exportu.
- Aktualizován statický export `dist/` a přegenerována PDF dokumentace v `docs/`.
- Funkce `lookupTeacherFullName(codeOrName, dayOrMap, naturalOrder = true)` pro spolehlivou expanzi oficiálních zkratek učitelů na celá jména.
- Helper `detectIsMobile(win)` a přepínač zobrazení celých jmen / zkratek na mobilních zařízeních (`.btn-strip-toggle` v hlavičce stripu nepřítomných učitelů).
- Funkce `toggleStripTeacherNames(strip, showFull)` umožňující okamžité přepnutí všech štítků vyučujících na mobilním zařízení mezi úspornou zkratkou a plným jménem.
- Nové unit a integrační testy v `tests/test_web_and_anonymization.py`: `TEST-EXPAND-TEACHER-CODE-01`, `TEST-STRIP-DESKTOP-FULL-NAMES-01`, `TEST-STRIP-MOBILE-DEFAULT-ABBR-01`, `TEST-STRIP-MOBILE-TOGGLE-CLICK-01`, `TEST-STATIC-EXPORT-PRESERVES-CODES-01`, `TEST-STATIC-EXPORT-EXPANSION-01` a `TEST-STATIC-EXPORT-VERSION-17-01`.

### Changed
- `app/static_export.py` zachovává kompletní číselník `OFFICIAL_TEACHER_CODES` v `dist/app.js` pro klientskou expanzi kódů na desktopu a po kliknutí na mobilu.
- Tlačítko `.btn-strip-toggle` je na desktopu (`> 768px`) skryto pomocí `@media (min-width: 769px) { display: none !important; }`.
- Verzování assetů povýšeno na `styles.css?v=17` a `app.js?v=17` v `app/static/index.html` i `dist/index.html`.
- Aktualizován statický export `dist/` a přegenerována PDF dokumentace v `docs/`.

### Changed
- Verzování assetů povýšeno na `styles.css?v=16` a `app.js?v=16` v šablonách i statickém exportu.
- Aktualizován statický export `dist/` a přegenerována PDF dokumentace v `docs/`.

### Removed
- Kompletně odstraněn element `#source-badge` ("Zdroj: Soubor / Web") z `app/static/index.html` i `dist/index.html`; v `.heading-with-source` zůstává pouze čistý nadpis dne `#day-heading`.

### Changed
- Přejmenováno tlačítko `#btn-view-cards` z „Old (Seznam karet)“ na „Přehled po třídách“ s popisem `title="Zobrazit rozpis změn rozdělený po jednotlivých třídách"`.
- Odstraněny všechny zmínky a komentáře označující zobrazení karet jako „Old“.
- Verzování klientských assetů navýšeno na `styles.css?v=15` a `app.js?v=15` pro spolehlivou invalidaci vyrovnávací paměti prohlížeče.
- Aktualizován statický export `dist/` a přegenerována PDF dokumentace v `docs/`.

### Added
- Nové testovací specifikace v `tests/test_web_and_anonymization.py`: `TEST-CLEAN-HEADER-NO-SOURCE-BADGE-01`, `TEST-BTN-VIEW-CARDS-RENAMED-01`, `TEST-JS-GRACEFUL-WITHOUT-SOURCE-BADGE-01`, `TEST-DEFAULT-VIEW-IS-GRID-02`, `TEST-SWITCH-TO-PREHLED-TRID-01` a `TEST-STATIC-EXPORT-NO-SOURCE-BADGE-01`.

- Reálný export rozvrhu pro pondělí 9. 11. 2026 z webu Bakalářů (`samples/zmeny_web_sample_2026-11-09.html`) nahrazující dřívější testovací mock data (3 nepřítomní pedagogové Ko, Pe, Sl, uzavřená místnost 7, 14 změn pro třídy 1A, 2C, 3A, 3C, 3D).
- Nový unit test `TEST-WEB-PARSE-MONDAY-03` ověřující kompletní a bezchybné zpracování pondělního exportu.
- Podpora pro formát vyučovacích hodin `les.` vedle `hod.` v regulárních výrazech `app/parser_web.py` (např. `4. les. 10:20 - 11:05`).
- Křížová korelace nepřítomných a suplujících/odpadlých hodin v `app/parser_web.py` (`_correlate_teachers`) automaticky přiřazující zkratky učitelů (např. `Sl` -> `Sál Petr`).
- Přepínač režimu zobrazení `.view-tabs` se dvěma volbami: výchozí „Tabulka“ (`#grid-view`) a „Old (Seznam karet)“ (`#cards-view`) pro původní vertikální seznam karet tříd s podporou plynulého automatického posunu (kiosk auto-scroll).
- Klientská funkce `renderCards(day)`, `switchView(viewName)` a `renderViewTabs()` v `app/static/app.js` vykreslující strukturované karty `.group-card` po třídách s plným zněním organizačních poznámek striktně přes bezpečné DOM API bez `innerHTML`.
- Nové testovací specifikace v `tests/test_web_and_anonymization.py`: `TEST-CLEAN-HEADER-NO-ONLINE-01`, `TEST-DEFAULT-VIEW-IS-GRID-01`, `TEST-SWITCH-TO-CARDS-VIEW-01`, `TEST-CARDS-VIEW-CONTENT-01`, `TEST-CARDS-FILTER-INTERACTION-01`, `TEST-NO-HIDDEN-NOTES-ANYWHERE-01` a `TEST-SOURCE-BADGE-CLEAN-LOAD-01`.

### Removed
- Odstraněn prvek `#connection-indicator` (zelená pulzující tečka a nápis Online) z hlavičky aplikace pro čistý a nerušený produkční vzhled.
- Odstraněny statické textové placeholdery („Datum výpisu: načítám…“, „Poslední kontrola: —“, „Načítám zdroj…“, „Načítám rozvrh…“) z `index.html` a `app.js`.
- Syntetický testovací vzorek `supl_cp1250_vymena.html` s mock daty pro pondělí byl přesunut ze sledované složky `samples/` do `tests/fixtures/`.

### Changed
- V režimu Kiosk (celá obrazovka) je přepínač pohledů automaticky skryt (`body.kiosk .view-tabs { display: none !important; }`).
- Verzování assetů povýšeno na `styles.css?v=14` a `app.js?v=14` v šablonách i statickém exportu.
- Aktualizován statický export `dist/` a přegenerována PDF dokumentace v `docs/`.

### Changed
- Odstraněno skrývání poznámek textem `[poznámka skryta]` v `app/anonymizer.py` (`sanitize_note`); organizační poznámky k rozvrhu ("supluje", "odpadá", "spojí", "změna", "přesun z...", "Souvislá praxe", "Exkurze") jsou zachovány v plném skutečném znění v intranetu i v anonymizovaném statickém exportu `dist/`.
- Doplněn čas `Europe/Prague` do `exported_at_display` a `fetched_at` v `app/parser_web.py`.
- Neutrální výchozí stav `#source-badge` v `app/static/index.html` a `dist/index.html` zabraňující probliknutí souborového zdroje před inicializací.
- Navýšena verze stylů a skriptů na `?v=12` v HTML šablonách pro okamžité prolomení cache.
- Kompletně regenerován statický export `dist/` s nulovým výskytem skrytých poznámek a přegenerována PDF dokumentace v `docs/`.

### Added
- Odolný retry mechanismus v `app/fetcher.py` (`WebFetcher.fetch_once`) s až 3 pokusy a exponenciální prodlevou (1.0 s, 2.0 s) pro dočasné výpadky (HTTP 502, 503, 504 a `TimeoutException`) a moderními hlavičkami prohlížeče.
- Klientské funkce `formatTeacherWithCode` a `lookupTeacherCode` v `app/static/app.js` s obousměrným mapováním pro 55 pedagogů z `config.yaml` (`OFFICIAL_TEACHER_CODES`).
- Zobrazení oficiálních zkratek u suplujících pedagogů v bloku `Suplující učitelé` (`extractSubstitutingTeachers`) ve tvaru `Jméno (Zk)` (např. `Bajerová Markéta (Bj)`).
- Sada integračních a unit testů `TEST-FETCH-RETRY-01`, `TEST-FETCH-RETRY-FAIL-01`, `TEST-STORAGE-WEB-PRECEDENCE-01`, `TEST-TEACHER-ABBR-ABSENT-01`, `TEST-TEACHER-ABBR-SUBSTITUTING-01`, `TEST-TEACHER-ABBR-ANONYMIZED-01` a `TEST-STATIC-EXPORT-WEB-SOURCE-01`.

### Changed
- Aktivován `web_enabled: true` jako výchozí stav v `config.yaml` a `AppConfig` v `app/config.py`.
- Odstraněna blokující podmínka `existing_exported > web_timestamp` v `app/database.py` (`save_web_day`), webový export pro daný den má autoritativní přednost před starším týdenním souborovým exportem.
- Opravena logická chyba `indexOf < 0` v `app/static/app.js` pro pedagogy, jejichž příjmení začíná na zkratku (`Kodad Miloš (Ko)`, `Sobotová Dana (So)`, `Čermáková Irena (Če)`, `Fox Luděk (Fo)`).
- Aktualizována databáze a statický export `dist/` s označením `data_source = 'web'` a přegenerována PDF dokumentace (`docs/`).

- Integrace oficiálního adresáře 55 pedagogů VOŠ a SPŠE Františka Křižíka z `Učitelé_zkratky.xlsx` do konfigurace `teacher_codes`.
- Samostatný webový parser `app/parser_web.py` (`parse_web_zmeny_html`) pro zpracování jednodenních exportů Bakalářů z `next/zmeny.aspx` včetně titulkových atributů `title` pedagogů a mřížek nepřítomností a změn.
- Odolný asynchronní web fetcher `app/fetcher.py` (`WebFetcher`) s ochranou proti výpadkům Bakalářů (HTTP 503, 502, 500, timeouty), SSRF ochranou (striktní whitelist hostitele `klasifikace.skolakrizik.cz`) a manuálním triggerem `POST /api/fetch-web`.
- Hybridní SQLite úložiště v `app/database.py` s novými sloupci `data_source`, `source_label`, `fetched_at`, `source_hash` a metodou `save_web_day` pro selektivní aktualizaci vybraného dne bez ovlivnění ostatních dnů týdne.
- Vizuální stavový indikátor **Online / Offline** (`#connection-indicator`) s pulzujícím zeleným/červeným bodem a podpora detekce výpadku sítě v reálném čase.
- Přesný indikátor zdroje dat pro zobrazený den (`#source-badge`) rozlišující data ze souboru a z webu.
- Sada unit a integračních testů `TEST-TEACHERS-DICT-01`, `TEST-WEB-PARSE-01`, `TEST-WEB-PARSE-02`, `TEST-FETCH-RESILIENCE-01`, `TEST-STORAGE-HYBRID-01`, `TEST-API-SOURCE-01`, `TEST-UI-INDICATORS-01`.

- Nahrazení sekce učeben mimo provoz novou sekcí suplujících pedagogů (`strip-sub-teachers`) v souhrnné liště dne (`grid-strip`).
- Klientská deterministická extrakce suplujících pedagogů `extractSubstitutingTeachers` s kompresí a formátováním hodinových intervalů (`formatHoursList`, např. `1., 4. hod`, `2.–4. hod`).
- Komponenta štítků/pilulek (`.teacher-pill`) s variantami `.pill-absent` a `.pill-sub` a odděleným jménem a rozsahem hodin (`.pill-name`, `.pill-hours`).
- Ošetření prázdného stavu přes `.strip-empty` s textem `žádní`.
- Responzivní flex-wrap dvousloupcové rozložení `.strip-teachers` a `.strip-sub-teachers` v `styles.css`.
- Integrační a unit testy `TEST-STRIP-01` až `TEST-STRIP-06` v `tests/test_web_and_anonymization.py`.

### Removed
- Odstraněna sekce 'Učebny mimo provoz' (`strip-rooms`) a sekce 'Dohledy' (`strip-sup` / `supervisions`) ze souhrnné lišty dne pro čistší přehled a maximalizaci vertikálního prostoru.

### Changed
- Navýšena verze assetů v `index.html` na `?v=10` a synchronizován statický export v `dist/`.
