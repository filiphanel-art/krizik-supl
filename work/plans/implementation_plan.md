# Implementation Plan: Název školy, copyright v patičce, řada dnů od pondělí do pondělí a oprava klientského běhu (dataset getter bug)

## Summary
Tento implementační plán řeší:
1. **Kritická oprava klientského běhu („aplikace neběží“):**
   - Odstranění nepovoleného přiřazení do read-only getteru `pill.dataset = pill.dataset || {};` v [app/static/app.js](file:///Users/filip/Downloads/krizik_supl/app/static/app.js) a `dist/app.js`, které v reálných prohlížečích vyvolalo `TypeError` a zastavilo vykreslení stránky.
2. **Úprava názvu školy v hlavičce:**
   - Zkrácení na oficiální kratší formu **„VOŠ a SPŠE Františka Křižíka“** v [app/static/index.html](file:///Users/filip/Downloads/krizik_supl/app/static/index.html), `dist/index.html`, [app/parser_web.py](file:///Users/filip/Downloads/krizik_supl/app/parser_web.py) a klientském JS.
3. **Patička s copyrightem:**
   - Přidání čisté responzivní patičky `<footer>` s textem `© 2026 VOŠ a SPŠE Františka Křižíka · Všechna práva vyhrazena` (v režimu kiosk skryté).
4. **Řada dnů v záložkách: od pondělí do pondělí (6 školních dnů):**
   - Fixní zobrazení 6 dnů: Po, Út, St, Čt, Pá aktuálního týdne + Po příštího týdne (pro aktuální týden od 9. 11. to je řada `9. 11. – 13. 11. + 16. 11.`).
   - Příznak `has_data: boolean` pro každý den.
   - Pro dny bez dat (`has_data: false`): tlačítko záložky je šedivé, má atribut `disabled`, `aria-disabled="true"` a tooltip `title="Pro tento den zatím není suplování vypsáno"`. Kliknutí je zablokováno.
   - Pro dny s daty (`has_data: true`, např. pondělí 9. 11.): tlačítko je plně funkční a aktivní. Pokud dorazí data z webu pro aktuální den, záložka se automaticky odemkne.
5. **Verzování assetů a publikace:**
   - Povýšení na `?v=18` a nasazení na GitHub Pages do větve `gh-pages`.

---

## Interfaces & Architektonický návrh

### 1. Oprava chyby s `dataset` v `app.js`
V `createTeacherPill`:
```javascript
// Původní chybný kód:
// pill.dataset = pill.dataset || {};
// pill.dataset.fullName = fullName;
// pill.dataset.shortName = shortText;

// Nový bezpečný kód:
if (typeof pill.setAttribute === "function") {
  pill.setAttribute("data-full-name", fullName);
  pill.setAttribute("data-short-name", shortText);
}
if (pill.dataset) {
  try {
    pill.dataset.fullName = fullName;
    pill.dataset.shortName = shortText;
  } catch (_e) {
    // Ignoruj v prostředích s striktním getterem
  }
}
```

### 2. Název školy a patička v HTML
V `app/static/index.html` a `dist/index.html`:
- `<h1 class="school-title" id="school-name">VOŠ a SPŠE Františka Křižíka</h1>`
- Patička před `</body>`:
  ```html
  <footer class="app-footer">
    <div class="footer-inner">
      <p class="footer-copy">&copy; <span id="footer-year">2026</span> VOŠ a SPŠE Františka Křižíka &middot; Všechna práva vyhrazena</p>
    </div>
  </footer>
  ```

### 3. Algoritmus pro 6denní školní okno (Po–Pá + Po)
V `app/database.py` a `app/web.py` i `app/static_export.py`:
- Funkce `compute_school_week_dates(reference_date, stored_days) -> list[dict]`:
  - Určí pondělí týdne (pro víkend 7.–8. 11. vezme nadcházející pondělí 9. 11.).
  - Vygeneruje dny s offsety `[0, 1, 2, 3, 4, 7]` (Po, Út, St, Čt, Pá + následující Po).
  - Každý den označí `has_data: true`, pokud existují v DB/exportu data pro dané datum, jinak `has_data: false`.
- V `app.js` (`renderDateTabs`):
  - Pokud `!d.has_data`, přidá třídu `.disabled`, nastaví `btn.disabled = true`, `btn.setAttribute("aria-disabled", "true")`, a tooltip `title="Pro tento den zatím není suplování vypsáno"`.
  - Pro dny s `has_data: true` ponechá plnou interaktivitu.
- V `chooseDefaultDate`:
  - Automaticky vybere nejbližší den s `has_data: true` (pondělí 9. 11.), takže uživatel nepřistane na prázdném dni.

### 4. Styly pro disabled záložky a patičku
V `app/static/styles.css`:
```css
.date-tab.disabled,
.date-tab:disabled {
  background: #f1f5f9;
  color: #94a3b8;
  border-color: #cbd5e1;
  cursor: not-allowed;
  opacity: 0.6;
}

.app-footer {
  margin-top: 2.5rem;
  padding: 1.25rem 1rem;
  border-top: 1px solid var(--border-color);
  background: #ffffff;
  color: var(--text-muted);
  font-size: 0.82rem;
  text-align: center;
}

body.kiosk .app-footer {
  display: none !important;
}
```

---

## Test Specs

| Test ID | Popis | Očekávaný výsledek |
|---|---|---|
| `TEST-FIX-DATASET-GETTER-01` | Spuštění reálného prohlížeče Chromium na stránce | Nulový výskyt chyby `Cannot set property dataset`, tabulka a karty se úspěšně vykreslí. |
| `TEST-SCHOOL-NAME-HEADER-01` | Kontrola textu `#school-name` | Obsahuje přesně `VOŠ a SPŠE Františka Křižíka`. |
| `TEST-FOOTER-HTML-01` | Kontrola patičky `.app-footer` | Obsahuje copyright `© 2026 VOŠ a SPŠE Františka Křižíka · Všechna práva vyhrazena`. |
| `TEST-CALENDAR-MONDAY-RANGE-01` | Výpočet řady pro pondělí 9. 11. | Vrátí přesně 6 prvků: 9. 11. (Po) až 13. 11. (Pá) + 16. 11. (Po). |
| `TEST-CALENDAR-FLAGS-01` | Kontrola příznaků `has_data` | Pro 9. 11. je `has_data: true`, pro ostatní dny `has_data: false`. |
| `TEST-UI-DATE-TABS-DISABLED-01` | Vykreslení záložek v DOMu | Dny bez dat mají třídu `.disabled` a atribut `disabled`. |
| `TEST-STATIC-EXPORT-VERSION-18-01` | Verzování assetů | V index.html je `styles.css?v=18` a `app.js?v=18`. |

---

## Security Considerations
- Všechny DOM prvky vytvářeny pomocí `document.createElement()` a `textContent`.
- Žádné `innerHTML`, žádné bezpečnostní regrese.
