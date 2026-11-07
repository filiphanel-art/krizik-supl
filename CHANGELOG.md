# Changelog

## [Unreleased]
### Added
- Zobrazení celých jmen pedagogů se zkratkami v přirozeném slovosledu `Jméno Příjmení (Zkratka)` (např. `Filip Hanel (Hf)`) na desktopu v blocích „Nepřítomní učitelé“ a „Suplující učitelé“.
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
