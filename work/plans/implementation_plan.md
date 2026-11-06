# Implementation Plan: Nahrazení učeben mimo provoz suplujícími učiteli a modernizace štítků dne

## Summary
Tento implementační plán řeší Požadavek 3 zadavatele na úpravu souhrnné lišty dne (`grid-strip` v hlavním rozhraní `app/static/app.js` a `app/static/styles.css`):
1. Nahrazení bloku 'Učebny mimo provoz' (`strip-rooms`) novým blokem 'Suplující učitelé' (`strip-sub-teachers`).
2. Implementaci deterministické klientské logiky pro extrakci, dedupikaci a seskupení vyučovacích hodin suplujících pedagogů (např. 'Novák Zdeněk (1., 3. hod)').
3. Úplné odstranění bloku 'Dohledy' (`strip-sup` / `supervisions`) ze souhrnné lišty dne pro odlehčení vizuálního smogu a zachování maximálního vertikálního prostoru pro hlavní rozvrhovou tabulku.
4. Přechod od nepřehledných textových řetězců oddělených svislítky k moderním, vysoce kontrastním vizuálním štítkům (pilulkám / tagům) s vizuálně odděleným jménem a rozsahem hodin pro nepřítomné i suplující učitele.
5. Zajištění plné kompatibility s anonymizovaným režimem (`export-static`, kde se zobrazují zkratky/iniciály), responsivním zobrazením pro mobilní telefony a automatickým kiosk režimem.

## Interfaces
Změna se dotýká výhradně prezentační vrstvy (Frontend DOM & CSS). Datová schémata backendu (`ScheduleDay`, `ClassChange`) a REST API kontrakty `/api/schedule` zůstávají plně zachovány (Backward Compatible).

### 1. Klientské datové rozhraní (Vanilla JS logika):
- **Funkce `extractSubstitutingTeachers(changes: Array<ClassChange>): Array<{ teacher: string, hoursText: string }>`**:
  - Filtruje změny z `day.class_changes`, kde je neprázdný `sub_teacher` a změna představuje aktivní zásah pedagoga (`change_type === "SUPLOVANI" || change_type === "SPOJENO" || (sub_teacher_changed && change_type !== "ZMENA_UCEBNY")`).
  - Seskupuje unikátní vyučovací hodiny (`hour_from..hour_to`) pro každého suplujícího pedagoga do `Set<number>`.
  - Řadí seznam pedagogů abecedně podle českých pravidel (`localeCompare("cs")`).
  - Formátuje hodiny pomocí kompresního algoritmu souvislých rozsahů: např. `[1, 3]` -> `"1., 3. hod"`, `[2, 3, 4]` -> `"2.–4. hod"`, `[1, 2, 5]` -> `"1.–2., 5. hod"`.

- **Funkce `formatHoursList(hours: Array<number>): string`**:
  - Deterministický formátovač intervalů s podporou nesouvislých hodin.

- **Funkce `createTeacherPill(name: string, hoursText: string, variant: 'absent' | 'sub'): HTMLElement`**:
  - Vytváří DOM element `<div class="teacher-pill pill-{variant}">`:
    - `<span class="pill-name">Jméno Učitele</span>`
    - `<span class="pill-hours">1., 3. hod</span>`

### 2. DOM struktura v `.grid-strip`:
```html
<div class="grid-strip">
  <!-- Blok 1: Nepřítomní učitelé -->
  <div class="strip-box strip-teachers">
    <div class="strip-header">Nepřítomní učitelé:</div>
    <div class="strip-pills">
      <div class="teacher-pill pill-absent">
        <span class="pill-name">Kodad Miloš (Ko)</span>
        <span class="pill-hours">1.–7. hod</span>
      </div>
    </div>
  </div>

  <!-- Blok 2: Suplující učitelé (nahrazuje původní strip-rooms a strip-sup) -->
  <div class="strip-box strip-sub-teachers">
    <div class="strip-header">Suplující učitelé:</div>
    <div class="strip-pills">
      <div class="teacher-pill pill-sub">
        <span class="pill-name">Valtr Pavel (Vl)</span>
        <span class="pill-hours">1., 4. hod</span>
      </div>
    </div>
  </div>
</div>
```

### 3. CSS rozhraní (`styles.css`):
- Přidání tříd `.strip-header`, `.strip-pills`, `.teacher-pill`, `.pill-absent`, `.pill-sub`, `.pill-name`, `.pill-hours`, `.strip-empty`.
- Úprava rozložení `.strip-teachers` a `.strip-sub-teachers`: obě komponenty mají symetrický `flex: 1 1 320px;`, což zajišťuje perfektní dvousloupcový layout na širokoúhlých obrazovkách a čisté zalomení pod sebe na mobilních zařízeních.

## Dependencies
Pro tuto změnu **nejsou navrhovány žádné nové externí knihovny**. Implementace striktně dodržuje stávající architekturu projektu (Vanilla JS + čisté CSS bez build dependencies).

Přehled stávajících schválených závislostí projektu:
1. **FastAPI (`>=0.115.0`)** – URL: https://fastapi.tiangolo.com/ – Licence: MIT
2. **Pydantic (`>=2.7.0`)** – URL: https://docs.pydantic.dev/ – Licence: MIT
3. **BeautifulSoup4 (`>=4.12.3`) & lxml (`>=5.2.0`)** – URL: https://www.crummy.com/software/BeautifulSoup/ – Licence: MIT / BSD-3-Clause
4. **Charset-normalizer (`>=3.3.2`)** – URL: https://charset-normalizer.readthedocs.io/ – Licence: MIT
5. **Watchdog (`>=4.0.0`)** – URL: https://gorakhargosh.github.io/watchdog/ – Licence: Apache-2.0

## Test Specs

| Test ID | Typ testu | Testovací scénář a Edge-cases | Očekávaný výsledek |
|---|---|---|---|
| `TEST-STRIP-01` | Unit (Frontend Logic) | Žádný suplující učitel v daném dni (pouze ODPADA nebo CELODENNI_AKCE). | V bloku 'Suplující učitelé' se vykreslí `<span class="strip-empty">žádní</span>`. |
| `TEST-STRIP-02` | Unit (Frontend Logic) | Vícenásobné a nesouvislé hodiny téhož pedagoga (např. 1., 3., 7. hodina). | Učitel je v seznamu obsažen právě jednou se správně seřazenými hodinami `'1., 3., 7. hod'`. |
| `TEST-STRIP-03` | Unit (Frontend Logic) | Souvislý blok suplování (Range Compression): hodiny 2, 3, 4. | Hodiny jsou zkomprimovány do rozsahu `'2.–4. hod'`. |
| `TEST-STRIP-04` | Integration (DOM & API) | Kompletní vykreslení vzorku `suplprehtrid.html` (5. 11. 2026). | Bloky `strip-rooms` a `strip-sup` nejsou v DOMu. Jsou přítomny bloky `strip-teachers` a `strip-sub-teachers`. |
| `TEST-STRIP-05` | Integration (Security & Anonymization) | Anonymizovaný režim (`export-static`). | Štítky zobrazují výhradně zkratky či iniciály, žádné plné příjmení učitele neunikne. |
| `TEST-STRIP-06` | Regression (Layout & Kiosk) | Dlouhý seznam učitelů (např. 15 nepřítomných a 12 suplujících). | Flex-wrap layout přirozeně zalomí pilulky do více řádků, nepřeteče přes okraj obrazovky. |

## Security Considerations
1. Ochrana proti XSS: Všechna jména a texty vkládány výhradně přes `textContent`. Přísný zákaz `innerHTML`.
2. Content-Security-Policy (CSP): Veškeré stylování v externím CSS souboru `styles.css`.
3. GDPR: V anonymizovaném režimu se uplatní anonymizační slovník; do DOMu nesmí proniknout plná jména.

## Open Questions & Doporučení
1. *Otázka ke specifikaci typu změny:* Zahrnovat i `SPOJENO`?
   *Doporučení:* Ano, pedagog přebírá zodpovědnost za spojenou třídu.
2. *Otázka k formátu jmen:* Zobrazovat 'Valtr Pavel (1., 4. hod)' bez detailu za koho?
   *Doporučení:* Ano, pro přehlednost v hlavičce pouze suplující učitel a hodiny. Detailní vazba je v konkrétní buňce rozvrhu.
