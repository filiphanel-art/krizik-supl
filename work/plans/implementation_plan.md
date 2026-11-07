# Implementation Plan: Plná jména vyučujících na desktopu a mobilní přepínač zobrazení

## Summary
Tento implementační plán reaguje na nový požadavek uživatele:
1. **Desktop (> 768px):** V blocích „Nepřítomní učitelé:“ a „Suplující učitelé:“ (`renderGridStrip`) vrátit zobrazení celých jmen vyučujících se zkratkou ve formátu `Filip Hanel (Hf)` (resp. `Jméno Příjmení (Zkratka)`). Žádné přepínací tlačítko se na desktopu nezobrazuje (`display: none`).
2. **Mobilní zařízení (<= 768px):** Výchozím stavem jsou úsporné oficiální zkratky (např. `Hf`, `Bj`), aby nedocházelo k přeplnění úzké mobilní obrazovky. V hlavičce stripu se zobrazí přístupné tlačítko „Zobrazit celá jména“. Po kliknutí se štítky přepnou na celá jména (`Filip Hanel (Hf)`) a tlačítko změní text na „Skrýt celá jména“.
3. **Statický export (`dist/` / GitHub Pages):** Skript `app/static_export.py` již nesmí vymazávat `OFFICIAL_TEACHER_CODES` z `dist/app.js`. Datové JSONy v `dist/data/*.json` zůstávají anonymizované (obsahují pouze kódy jako `Hf`), ale klientský skript `dist/app.js` díky zachovanému adresáři 55 pedagogů dokáže na desktopu (a po kliknutí na mobilu) expandovat kód na celé jméno s kódem.
4. **Verzování assetů:** Povýšení na `?v=17` pro okamžité prolomení vyrovnávací paměti prohlížečů.

---

## Interfaces & Architektonický návrh

### 1. Rozšíření mapování a formátování jmen v `app/static/app.js` (a `dist/app.js`)

#### A. Pomocná funkce `lookupTeacherFullName(codeOrName, dayOrMap, naturalOrder = true)`
```javascript
function lookupTeacherFullName(codeOrName, dayOrMap, naturalOrder = true) {
  const str = String(codeOrName || "").trim();
  if (!str) return "";

  let rawFullName = OFFICIAL_TEACHER_CODES[str] || "";

  if (!rawFullName && dayOrMap && typeof dayOrMap === "object") {
    if (Array.isArray(dayOrMap.derived_teachers)) {
      const dt = dayOrMap.derived_teachers.find(
        (t) => t.teacher_code === str && t.teacher_full_name && t.teacher_full_name !== str
      );
      if (dt) rawFullName = dt.teacher_full_name;
    }
    if (!rawFullName && Array.isArray(dayOrMap.absent_teachers)) {
      const at = dayOrMap.absent_teachers.find(
        (t) => t.teacher_code === str && t.teacher_full_name && t.teacher_full_name !== str
      );
      if (at) rawFullName = at.teacher_full_name;
    }
  }

  if (!rawFullName && NAME_TO_CODE[str]) {
    rawFullName = OFFICIAL_TEACHER_CODES[NAME_TO_CODE[str]] || str;
  }
  if (!rawFullName) {
    const cleaned = str.replace(/^(?:Mgr\.|Ing\.|Bc\.|PaedDr\.|RNDr\.|PhDr\.|DiS\.)\s+/i, "").trim();
    if (NAME_TO_CODE[cleaned]) {
      rawFullName = OFFICIAL_TEACHER_CODES[NAME_TO_CODE[cleaned]] || cleaned;
    }
  }

  if (!rawFullName) return str;

  let cleanName = rawFullName.replace(/^(?:Mgr\.|Ing\.|Bc\.|PaedDr\.|RNDr\.|PhDr\.|DiS\.)\s+/i, "").trim();

  if (naturalOrder) {
    const parts = cleanName.split(/\s+/);
    if (parts.length === 2) {
      cleanName = parts[1] + " " + parts[0];
    }
  }

  return cleanName;
}
```

#### B. Úprava funkce `formatTeacherWithCode(fullNameOrCode, code, dayOrMap, naturalOrder = true)`
```javascript
function formatTeacherWithCode(fullNameOrCode, code, dayOrMap, naturalOrder = true) {
  let name = (fullNameOrCode || "").trim();
  const c = (code || lookupTeacherCode(name, dayOrMap) || "").trim();

  if (!name && c) {
    name = lookupTeacherFullName(c, dayOrMap, naturalOrder);
  } else if (name && c && name === c) {
    const resolved = lookupTeacherFullName(c, dayOrMap, naturalOrder);
    if (resolved && resolved !== c) {
      name = resolved;
    }
  } else if (name && naturalOrder) {
    const cleaned = name.replace(/^(?:Mgr\.|Ing\.|Bc\.|PaedDr\.|RNDr\.|PhDr\.|DiS\.)\s+/i, "").trim();
    const parts = cleaned.split(/\s+/);
    if (parts.length === 2 && OFFICIAL_TEACHER_CODES[c] === parts[0] + " " + parts[1]) {
      name = parts[1] + " " + parts[0];
    }
  }

  if (!name) return c ? "(" + c + ")" : "";
  if (!c) return name;
  if (name.includes("(" + c + ")")) return name;
  if (name === c) return name;
  return name + " (" + c + ")";
}
```

#### C. Rozšíření funkce `createTeacherPill`
```javascript
function createTeacherPill(fullName, hoursText, variant, shortCode) {
  const pill = el("div", "teacher-pill pill-" + variant);
  const shortText = shortCode || fullName;
  if (typeof pill.setAttribute === "function") {
    pill.setAttribute("data-full-name", fullName);
    pill.setAttribute("data-short-name", shortText);
  }
  pill.dataset = pill.dataset || {};
  pill.dataset.fullName = fullName;
  pill.dataset.shortName = shortText;

  const isMobile = detectIsMobile();
  const showFull = !isMobile || Boolean(state.showFullTeacherNamesOnMobile);

  const nameSpan = el("span", "pill-name", showFull ? fullName : shortText);
  pill.appendChild(nameSpan);

  if (hoursText) {
    pill.appendChild(el("span", "pill-hours", hoursText));
  }
  return pill;
}
```

#### D. Úprava `renderGridStrip(day)` a přepínání `toggleStripTeacherNames`
Tlačítko `.btn-strip-toggle` se umístí do `.strip-teachers .strip-header`:
- Na mobilu (<= 768px): výchozí text "Zobrazit celá jména", po kliknutí "Skrýt celá jména".
- Na desktopu (> 768px): v CSS skryto pomocí `@media (min-width: 769px) { .btn-strip-toggle { display: none !important; } }`.

### 2. Úprava `app/static_export.py`
Zachovat deklaraci `const OFFICIAL_TEACHER_CODES` v `dist/app.js` beze změny (nemazat slovník).

### 3. Verzování assetů
Povýšit na `styles.css?v=17` a `app.js?v=17` v `app/static/index.html` a `dist/index.html`.

---

## Test Specs

| Test ID | Typ testu | Testovací scénář a Edge-cases | Očekávaný výsledek |
|---|---|---|---|
| `TEST-EXPAND-TEACHER-CODE-01` | Unit (Node.js) | Test `lookupTeacherFullName` a `formatTeacherWithCode` pro kódy `"Hf"`, `"Ko"`, `"Bj"` a neznámý kód `"Xy"`. | `"Hf"` -> `"Filip Hanel (Hf)"`; `"Ko"` -> `"Miloš Kodad (Ko)"`; `"Bj"` -> `"Markéta Bajerová (Bj)"`; neznámý `"Xy"` -> `"Xy"`. |
| `TEST-STRIP-DESKTOP-FULL-NAMES-01` | Unit (Node.js) | Volání `renderGridStrip(day)` v desktopovém prostředí (`detectIsMobile() === false`). | Všechny vygenerované `.pill-name` obsahují celá jména i se zkratkami (např. `Filip Hanel (Hf)`). Tlačítko `.btn-strip-toggle` je přítomno. |
| `TEST-STRIP-MOBILE-DEFAULT-ABBR-01` | Unit (Node.js) | Volání `renderGridStrip(day)` v simulovaném mobilním prostředí (`innerWidth <= 768` nebo `isMobile: true`). | `.pill-name` zobrazuje pouze zkratky (např. `Hf`, `Bj`), tlačítko `.btn-strip-toggle` existuje s textem `"Zobrazit celá jména"` a `aria-expanded="false"`. |
| `TEST-STRIP-MOBILE-TOGGLE-CLICK-01` | Integration (Node.js/DOM) | Kliknutí na `.btn-strip-toggle` v mobilním režimu. | Texty ve všech štítcích `.pill-name` se změní na celá jména (`Filip Hanel (Hf)`). Text tlačítka se změní na `"Skrýt celá jména"`. Druhé kliknutí vrátí zkratky. |
| `TEST-STATIC-EXPORT-PRESERVES-CODES-01` | Integration (Python) | Spuštění `export_static_site()`. | `dist/app.js` obsahuje kompletní deklaraci `const OFFICIAL_TEACHER_CODES` s 55 pedagogy (není prázdný `{}`). |
| `TEST-STATIC-EXPORT-EXPANSION-01` | Integration (Node.js) | Načtení `dist/app.js` a souboru `dist/data/day-2026-11-06.json`. Volání `renderGridStrip(day)`. | Na desktopu se v `dist/app.js` kód `"Hf"` úspěšně expanduje na `"Filip Hanel (Hf)"`. |

---

## Security Considerations
1. Bezpečné DOM manipulace: Použití `textContent`, žádné `innerHTML`.
2. Žádný únik soukromých údajů: Veřejný seznam učitelů SPŠE Křižík je plně v souladu s veřejným charakterem rozvrhu a požadavkem školy.
