# Changelog

## [Unreleased]

### Added
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
