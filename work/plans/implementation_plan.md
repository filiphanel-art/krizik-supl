# Implementation Plan: Odstranění odznaku zdroje (#source-badge), přejmenování na „Přehled po třídách“ a deployment GitHub Pages

## Summary
Tento implementační plán řeší požadavky uživatele na finální úpravy klientského rozhraní a publikaci aplikace **Suplování Viewer**:

1. **Kompletní odebrání zobrazení zdroje dat (`#source-badge`)**:
   - Odstranění elementu `#source-badge` ("Zdroj: Soubor (Bakaláři export) · Export...") z [app/static/index.html](file:///Users/filip/Downloads/krizik_supl/app/static/index.html) i [dist/index.html](file:///Users/filip/Downloads/krizik_supl/dist/index.html).
   - Zajištění, že v záhlaví zůstává čistý a nerušený nadpis dne `#day-heading`.
   - Úprava v [app/static/app.js](file:///Users/filip/Downloads/krizik_supl/app/static/app.js) a [dist/app.js](file:///Users/filip/Downloads/krizik_supl/dist/app.js) garantující, že absence `#source-badge` nezpůsobí žádné JS runtime chyby.
2. **Přejmenování záložky 'Old' na profesionální název**:
   - Tlačítko `#btn-view-cards` přejmenovat z „Old (Seznam karet)“ na odborný název **„Přehled po třídách“**.
   - Doplnit přesný tooltip / atribut `title`: „Zobrazit rozpis změn rozdělený po jednotlivých třídách“.
   - Zachovat `Tabulka` jako výchozí zobrazení (`activeView = "grid"`).
3. **Analýza GitHub Pages a bezpečný postup nasazení**:
   - Vyjasnění architektury: interní server nesouvisí se statickými GitHub Pages. Uživatel na server nemusí.
   - Definice postupu publikace složky `dist/` do větve `gh-pages` bez nutnosti ručního přepínání větví.
4. **Aktualizace testovací sady**:
   - Odstranění zastaralých očekávání na přítomnost `#source-badge` v HTML z [tests/test_web_and_anonymization.py](file:///Users/filip/Downloads/krizik_supl/tests/test_web_and_anonymization.py).
   - Doplnění nových testů ověřujících čisté záhlaví bez odznaku a nový text tlačítka „Přehled po třídách“.
5. **Regenerace statického exportu a PDF dokumentace**:
   - Spuštění exportu `dist/` a přegenerování PDF manuálů v `docs/`.

---

## Interfaces & Architektonický návrh

### 1. Šablony HTML (`app/static/index.html` a `dist/index.html`)
1. **Horní lišta a záhlaví dne (.controls-top-row):**
   - Odstranit prvek `<span id="source-badge" ...>...</span>` z kontejneru `.heading-with-source`.
   - V `.heading-with-source` zůstává pouze:
     ```html
     <div class="heading-with-source">
       <h2 class="day-heading" id="day-heading"></h2>
     </div>
     ```
2. **Přepínač zobrazení (.view-tabs):**
   - Tlačítko `#btn-view-cards` se aktualizuje:
     ```html
     <div class="view-tabs" id="view-tabs" role="tablist" aria-label="Režim zobrazení">
       <button type="button" id="btn-view-grid" class="view-tab active" role="tab" aria-selected="true" data-view="grid" title="Zobrazit přehlednou tabulku dne na 1 stránku">Tabulka</button>
       <button type="button" id="btn-view-cards" class="view-tab" role="tab" aria-selected="false" data-view="cards" title="Zobrazit rozpis změn rozdělený po jednotlivých třídách">Přehled po třídách</button>
     </div>
     ```
3. **Komentář u sekce karet v `<main>`:**
   - Změna z `<!-- Původní vertikální seznam karet rozdělený po třídách (Old pohled) -->` na `<!-- Vertikální seznam rozdělený po třídách (Přehled po třídách) -->`.
4. **Povýšení verzování assetů (Cache Busting):**
   - V `index.html` povýšit na `styles.css?v=15` a `app.js?v=15`.

### 2. Klientská logika (`app/static/app.js` a `dist/app.js`)
1. **Inicializace elementů (`initElements`):**
   - `els.sourceBadge` a `els.sourceBadgeText` bezpečně vrací `null`, pokud element v DOMu neexistuje.
2. **Defenzivní chování `updateSourceBadge(day)`:**
   - Hned na začátku funkce existuje guard:
     ```javascript
     function updateSourceBadge(day) {
       if (!els.sourceBadge) return;
       // ... zbytek se bezpečně nevykoná
     }
     ```
   - Zajistit, že ani v `renderBannersAndHeader()` ani v `onDateChange()` nedojde k volání metod na `null`.
3. **Výchozí pohled a kiosk:**
   - Výchozím stavem zůstává `state.activeView = "grid"`.

### 3. Vizuální styly (`app/static/styles.css` a `dist/styles.css`)
- V CSS třídy `.source-badge` a `.heading-with-source` ponechat pro zpětnou kompatibilitu, případně upravit komentáře (odstranění zmínek o "Old").

---

## Dependencies

Pro tuto změnu nejsou vyžadovány žádné nové knihovny. Všechny komponenty staví na standardních, prověřených technologiích:

| Knihovna / Nástroj | Verze | Licence | Oficiální URL | Bezpečnostní status (CVE) |
|---|---|---|---|---|
| **Vanilla JavaScript (ES2022)** | ES2022 | N/A (Standard) | https://developer.mozilla.org/en-US/docs/Web/JavaScript | 0 známých CVE (nativní API) |
| **Python** | 3.12+ | PSF License | https://www.python.org/ | 0 známých CVE |
| **FastAPI** | >=0.110.0 | MIT | https://github.com/tiangolo/fastapi | 0 známých CVE |
| **HTTPX** | >=0.27.0 | BSD-3-Clause | https://www.python-httpx.org/ | 0 známých CVE |
| **Playwright** | >=1.42.0 | Apache 2.0 | https://playwright.dev/python/ | 0 známých CVE |
| **pytest** | >=8.0.0 | MIT | https://docs.pytest.org/ | 0 známých CVE |

---

## Test Specs

| Test ID | Typ testu | Testovací scénář a Edge-cases | Očekávaný výsledek |
|---|---|---|---|
| `TEST-CLEAN-HEADER-NO-SOURCE-BADGE-01` | Unit (Python/DOM) | Kontrola `index.html` a `dist/index.html`. | V DOMu neexistuje `#source-badge` ani `#source-badge-text`. V záhlaví je přítomen pouze čistý element `#day-heading`. Neobsahuje statické texty „Zdroj: Soubor“ ani „Zdroj: Web“. |
| `TEST-BTN-VIEW-CARDS-RENAMED-01` | Unit (Python/DOM) | Kontrola názvu a atributů tlačítka `#btn-view-cards` v šablonách. | Tlačítko `#btn-view-cards` obsahuje text `Přehled po třídách` a tooltip `title="Zobrazit rozpis změn rozdělený po jednotlivých třídách"`. V HTML se nevyskytuje řetězec `Old (Seznam karet)`. |
| `TEST-JS-GRACEFUL-WITHOUT-SOURCE-BADGE-01` | Unit (Node.js/DOM) | Inicializace `app.js` a volání `app.renderAll()` / `app.updateSourceBadge(day)` v prostředí, kde `document.getElementById('source-badge')` vrací `null`. | Funkce proběhnou bez vyhození výjimky (`TypeError: Cannot read properties of null`). |
| `TEST-DEFAULT-VIEW-IS-GRID-02` | Unit (Node.js/DOM) | Načtení aplikace v defaultním stavu. | `state.activeView === "grid"`. `#grid-view` je zobrazen, `#cards-view` má třídu `.hidden`. Tlačítko `#btn-view-grid` je aktivní, `#btn-view-cards` („Přehled po třídách“) není aktivní. |
| `TEST-SWITCH-TO-PREHLED-TRID-01` | Unit (Node.js/DOM) | Kliknutí na `#btn-view-cards` („Přehled po třídách“). | Přepne `state.activeView` na `"cards"`, zobrazí `#cards-view`, skryje `#grid-view`, nastaví třídu `.active` na `#btn-view-cards`. |
| `TEST-STATIC-EXPORT-NO-SOURCE-BADGE-01` | Integration (Python) | Spuštění `export_static_site` do dočasné složky. | `dist/index.html` neobsahuje `#source-badge`, obsahuje `Přehled po třídách` a odkazuje na assety s verzí `?v=15`. |
| `TEST-UI-INDICATORS-REGRESSION-01` | Regression (Python) | Regresní ověření `test_ui_indicators_01` v `tests/test_web_and_anonymization.py`. | Test úspěšně projde s novým assertem `assert 'id="source-badge"' not in index_html`. |

---

## Security Considerations

1. **Robustnost klientského DOM API:**
   Odstraněním `#source-badge` se zmenšuje plocha manipulace s DOMem. Ochranná podmínka `if (!els.sourceBadge) return;` v `updateSourceBadge` brání zhroucení skriptu při inicializaci.
2. **Ochrana osobních údajů a anonymizace:**
   Veřejný export pro GitHub Pages (`dist/`) zůstává 100% anonymizován podle pravidel GDPR (jména vyučujících nahrazena oficiálními zkratkami, veřejné organizační poznámky zachovány).
3. **Bezpečnost GitHub Pages deploymentu:**
   Do větve `gh-pages` se odesílá výhradně izolovaný obsah složky `dist/` (žádná databáze `supl.db`, privátní konfigurační soubory ani backendové Python skripty).
