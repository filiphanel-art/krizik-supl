# Implementation Plan: Přidání záložky „Old (Seznam karet)“, odstranění zeleného online a placeholderů pro čistý produkční vzhled

## Summary
Tento implementační plán řeší požadavky uživatele na dokončení produkční verze aplikace **Suplování Viewer**:

1. **Odebrání `[poznámka skryta]` a zachování veřejných poznámek rozvrhu:**
   - Garantovat, že v celém repozitáři, v logice (`app/anonymizer.py`), v databázi, v klientském rozhraní i ve vygenerovaném statickém exportu v `dist/` se nikde nezobrazuje text `"[poznámka skryta]"`.
   - Všechny organizační poznámky k rozvrhu (*„odpadá“*, *„supluje“*, *„spojí“*, *„změna učebny“*, *„přesun z...“*, *„Exkurze“*, *„Souvislá praxe“*) jsou veřejné a zůstávají zachovány v plném skutečném znění.

2. **Přidání staré záložky „Old (Seznam karet)“ vedle výchozí „Tabulky“:**
   - Přidat přepínač režimu zobrazení:
     - **„Tabulka“** (výchozí / default – stávající přehledná jednodenní matice změn na 1 obrazovku `#grid-view`).
     - **„Old (Seznam karet)“** (vertikální seznam karet `.group-card` rozdělený po třídách s jednotlivými položkami změn v `#cards-view`, který se v režimu Celá obrazovka / Kiosk plynule posouvá shora dolů a zpět).
   - Výchozím stavem při načtení stránky (včetně obnovení a statického exportu) MUSÍ být vždy **„Tabulka“** (`activeView = "grid"`).
   - Plynulý posun (kiosk auto-scroll) funguje na kartách při zobrazení „Old (Seznam karet)“.

3. **Čistý a profesionální produkční vzhled (odstranění zeleného online a placeholderů):**
   - **Odstranění zeleného online indikátoru:** Prvek `#connection-indicator` (zelená tečka a nápis „Online“) se z hlavičky odstraní. (V případě skutečného výpadku sítě zůstává funkční varovný pruh `#banner-offline`, ale zelená pulzující tečka v běžném provozu nepůsobí rušivě ani jako ladicí prvek).
   - **Odstranění rušivých statických placeholderů:** V `index.html` a `app.js` odstranit surové texty jako `Datum výpisu: načítám…`, `Poslední kontrola: —`, `Načítám zdroj…`, `Načítám rozvrh…`. Místo nich se použije čistý prázdný výchozí stav, který se po načtení dat elegantně naplní skutečnými údaji.
   - Čas výpisu a zdroj dat se zobrazují čistě, sjednoceně a bez duplicit.

---

## Interfaces & Architektonický návrh

### 1. Šablony HTML (`app/static/index.html` a `dist/index.html`)

1. **Záhlaví `.app-header`:**
   - Odstraněn element `#connection-indicator`.
   - V `.meta-box` vyčištěny statické texty `načítám…` na čisté prázdné elementy, které JS po načtení korektně naplní:
   ```html
   <div class="header-actions">
     <button
       type="button"
       id="btn-fullscreen"
       class="btn-fs"
       title="Celá obrazovka s automatickým posunem"
       aria-label="Celá obrazovka s automatickým posunem"
     >
       <svg class="icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
         <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
       </svg>
       <span>Celá obrazovka</span>
     </button>
     <div class="meta-box" aria-live="polite">
       <div id="exported-at-label"></div>
       <div id="updated-at-label"></div>
     </div>
   </div>
   ```

2. **Ovládací lišta `.controls-top-row`:**
   - Přepínač zobrazení se dvěma volbami za záložkami dnů `#date-tabs`:
   ```html
   <div class="view-tabs" id="view-tabs" role="tablist" aria-label="Režim zobrazení">
     <button type="button" id="btn-view-grid" class="view-tab active" role="tab" aria-selected="true" data-view="grid" title="Zobrazit přehlednou tabulku dne na 1 stránku">Tabulka</button>
     <button type="button" id="btn-view-cards" class="view-tab" role="tab" aria-selected="false" data-view="cards" title="Zobrazit původní seznam karet tříd s plynulým posunem">Old (Seznam karet)</button>
   </div>
   ```
   - V `.heading-with-source`:
   ```html
   <div class="heading-with-source">
     <h2 class="day-heading" id="day-heading"></h2>
     <span id="source-badge" class="source-badge hidden" role="status" title="Zdroj dat">
       <span class="source-icon" aria-hidden="true"></span>
       <span class="source-text" id="source-badge-text"></span>
     </span>
   </div>
   ```

3. **Obsahový kontejner `<main>`:**
   ```html
   <!-- Hlavní tabulka celého dne na 1 stránku (výchozí pohled) -->
   <section id="grid-view" class="grid-view" aria-live="polite" aria-label="Přehled dne v tabulce"></section>

   <!-- Původní vertikální seznam karet rozdělený po třídách (Old pohled) -->
   <section id="cards-view" class="cards-view hidden" aria-live="polite" aria-label="Seznam karet po třídách"></section>
   ```

4. **Navýšení verzování assetů:**
   `styles.css?v=14` a `app.js?v=14`.

---

### 2. Klientská logika (`app/static/app.js` a `dist/app.js`)

1. **Stav aplikace (`state`):**
   - `activeView: "grid"` jako pevná výchozí hodnota.
   - Odstraněna závislost na zeleném indikátoru v `renderStatusIndicators` (neexistující element se ignoruje, případný offline stav nadále ovládá `#banner-offline`).

2. **Přepínání pohledů `switchView(viewName)`:**
   - Při kliknutí na `#btn-view-grid` nebo `#btn-view-cards` nastaví `state.activeView`, resetuje `kiosk.pos = 0`, provede `setScrollTop(0)` a zavolá `renderAll()`.
   - V `renderViewTabs()` aplikuje třídu `.active` na aktivní tlačítko.

3. **Vykreslení seznamu karet `renderCards(day)`:**
   - Do `#cards-view` vloží `.grid-strip` s nepřítomnými a suplujícími pedagogy.
   - Sestaví karty `.group-card` pro jednotlivé třídy se změnami vyfiltrovanými podle `selectedEntity` a textového vyhledávání.
   - Položky obsahují rozsah hodin, odznaky typů změn, předmět, skupinu, učebnu, učitele se zkratkou a plné znění poznámky `ch.note` (bez `[poznámka skryta]`).
   - Veškerý obsah je bezpečně vkládán přes `.textContent` (žádný `innerHTML`).

4. **Formátování času a indikátoru zdroje bez placeholderů:**
   - `#source-badge` je před načtením dat skrytý (`.hidden`), po načtení se zobrazí čistý text:
     - Pro web: `Zdroj: Web (klasifikace.skolakrizik.cz) · Načteno 6. 11. 2026 v 22:17`
     - Pro soubor: `Zdroj: Soubor (Bakaláři export) · Export 5. 11. 2026 v 08:26`
   - Záhlaví výpisu v `#exported-at-label` a `#updated-at-label` se plní pouze tehdy, jsou-li data k dispozici. Žádné surové texty „načítám…“.

5. **Plynulý Kiosk posun:**
   - V režimu „Old (Seznam karet)“ kiosk automaticky detekuje vertikální přesah a plynule posouvá seznam karet shora dolů s 2,5s pauzou na koncích.

---

### 3. Vizuální styly (`app/static/styles.css` a `dist/styles.css`)

- Doplnění stylů pro `.view-tabs`, `.view-tab`, `.view-tab.active`.
- Doplnění stylů pro `.cards-view`, `.cards-container`, `.group-card`, `.group-card-header`, `.group-card-items`, `.group-card-item`, `.item-header`, `.item-detail`.
- Skrytí `.view-tabs` v režimu Kiosk (`body.kiosk .view-tabs { display: none !important; }`).
- Čisté zarovnání hlavičky po odstranění connection indicatoru.

---

## Dependencies

Žádné nové externí závislosti nejsou potřeba. Projekt využívá standardní čistý stack:
- **Vanilla JavaScript (ES2022 / DOM API)**
- **Python 3.12+**
- **FastAPI**, **HTTPX**

---

## Test Specs

| Test ID | Typ testu | Testovací scénář a Edge-cases | Očekávaný výsledek |
|---|---|---|---|
| `TEST-CLEAN-HEADER-NO-ONLINE-01` | Unit (DOM/JS) | Kontrola prvků v hlavičce aplikace. | Element `#connection-indicator` neexistuje v DOMu nebo je bezpečně odstraněn. V hlavičce se nezobrazují surové texty `Datum výpisu: načítám…` ani `Poslední kontrola: —`. |
| `TEST-DEFAULT-VIEW-IS-GRID-01` | Unit (DOM/JS) | Načtení aplikace v defaultním stavu. | `state.activeView === "grid"`. `#grid-view` je viditelný, `#cards-view` je skrytý (`.hidden`). Tlačítko `#btn-view-grid` má třídu `.active`. |
| `TEST-SWITCH-TO-CARDS-VIEW-01` | Unit (DOM/JS) | Kliknutí na `#btn-view-cards`. | `state.activeView === "cards"`. `#cards-view` je viditelný, `#grid-view` je skrytý (`.hidden`). Tlačítko `#btn-view-cards` má třídu `.active`. V `#cards-view` jsou vykresleny karty `.group-card`. |
| `TEST-CARDS-VIEW-CONTENT-01` | Unit (DOM/JS) | Kontrola obsahu karet v `#cards-view`. | Každá třída se změnami má kartu `.group-card` s hlavičkou a položkami `.group-card-item`. Poznámky jsou vykresleny v plném znění bez řetězce `[poznámka skryta]`. |
| `TEST-CARDS-FILTER-INTERACTION-01` | Unit (DOM/JS) | Změna filtru třídy v režimu karet. | V `#cards-view` se zobrazí pouze karty odpovídající vybrané třídě. |
| `TEST-NO-HIDDEN-NOTES-ANYWHERE-01` | Integration (Python) | Kontrola celého repozitáře a výstupu statického exportu v `dist/data/*.json`. | 0 výskytů řetězce `[poznámka skryta]`. |
| `TEST-SOURCE-BADGE-CLEAN-LOAD-01` | Unit (DOM/JS) | Stav `#source-badge` před a po načtení dat. | Před načtením dat je badge skrytý nebo bez placeholderu `Načítám zdroj…`. Po načtení zobrazuje formátovaný čas a zdroj. |

---

## Security Considerations

1. **XSS prevence:** V novém pohledu karet se veškerá data (třídy, předměty, učebny, jména učitelů, poznámky) vkládají striktně přes `node.textContent` a `el(tag, className, text)`. Žádný `innerHTML`.
2. **GDPR a ochrana osobních údajů:** Veřejný export `dist/` zůstává 100% anonymizován (všechna jména učitelů jsou nahrazena oficiálními zkratkami). Poznámky jsou veřejné organizační informace.
3. **Kiosk bezpečnost:** V režimu Kiosk jsou přepínače pohledů a ovládací prvky skryty.
