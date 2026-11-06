# Changelog

## [Unreleased]

### Added
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
