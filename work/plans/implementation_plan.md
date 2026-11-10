# Implementační plán: Odolnost, Priorita dat, Kiosk větve a Multi-day forward fetch

## 1. Summary
Tento implementační plán řeší tři klíčové oblasti rozvoje systému Suplování Viewer pro VOŠ a SPŠE Františka Křižíka:
1. **Odolnost a autoritativní priorita**:
   - Aplikace konsoliduje data ze sdíleného souborového exportu (`C:\Krizik\suplprehtrid.html`) i z webu Bakalářů (`suplovani.skolakrizik.cz` / `klasifikace.skolakrizik.cz`).
   - Webová data mají pro daný den absolutní autoritativní přednost (`save_web_day`), souborový export aktualizuje zbývající dny týdne a nepřepisuje novější webová data.
   - Při síťovém nebo aplikačním výpadku Bakalářů (HTTP 502/503/timeout/poškozené HTML) se žádná existující data v SQLite nemažou.
   - Půlnoční a ranní automatický rollover spolehlivě přepíná na nový den v časovém pásmu `Europe/Prague` bez nutnosti reloadu.
2. **Architektura a rozdělení větví (`main` vs. `kiosk-server`)**:
   - **Větev `main`** (pro localhost vývoj a GitHub Pages static export):
     - Žádný automatický fullscreen/kiosk na desktopu.
     - Standardní plnohodnotné rozhraní: hlavička školy, patička s copyrightem, přepínač pohledů (výchozí „Tabulka“, druhý „Přehled po třídách“).
     - 6denní kalendářní řada Po–Pá + Po s neaktivními dny šedivě/disabled.
     - Periodická kontrola na pozadí (polling + SSE) a midnight rollover.
   - **Větev `kiosk-server`** (pro školní server 10.20.0.81:8080):
     - Automatický celoobrazovkový kiosk s plynulým autoscrollem na desktopu (`!detectIsMobile()`).
     - Automaticky skrytá horní lišta, přepínač i patička (`body.kiosk`).
     - Periodický update a plynulý rollover o půlnoci i po nečinnosti.
3. **Multi-day forward fetch (stahování až 2 následujících publikovaných dnů)**:
   - Web fetcher po stažení dneška (GET) simuluje kliknutí na ASP.NET tlačítko `ButtonNext` pomocí POST požadavků se zachováním `__VIEWSTATE` a `__EVENTVALIDATION`.
   - Iterativně stáhne a uloží až 2 následující publikované dny (např. úterý a středu) do SQLite.
   - Zastaví se, pokud Bakaláři vrátí stejný den (dosažen konec publikovaných změn) nebo tlačítko není přítomno.
   - V UI se pro tyto dny aktivují a zprovozní záložky (`has_data: true`).
   - Statický export (`export-static`) automaticky vygeneruje soubory `dist/data/day-YYYY-MM-DD.json` i pro tyto publikované dopředné dny.

---

## 2. Interfaces & Data Flow

### 2.1 Nové rozhraní: Extrakce ASP.NET formuláře
V modulu `app/fetcher.py`:
```python
def extract_asp_form_inputs(
    html_content: str | bytes,
    button_name: str = "ButtonNext",
) -> tuple[str, dict[str, str]]:
    """Extrahuje action URL a hodnoty formulářových polí ASP.NET pro odeslání tlačítka."""
```

### 2.2 Datový tok `WebFetcher.fetch_once()`
- Krok 1: GET výchozí `zmeny.aspx` -> uložit den 0 (`save_web_day`).
- Krok 2: Pokud je povolen dopředný fetch (až 2 dny), POST s `ButtonNext` s využitím ViewState/EventValidation -> pokud `day_1.date > day_0.date`, uložit den 1.
- Krok 3: POST s dalším `ButtonNext` z odpovědi 1 -> pokud `day_2.date > day_1.date`, uložit den 2.
- Jakmile datum nepokročí nebo nastane chyba, cyklus dopředného načítání bezpečně skončí.
- Při libovolném dílčím selhání dopředných kroků zůstávají již uložená data v DB nedotčena.

### 2.3 Klientské rozhraní Kiosk režimu (`app/static/app.js`)
Pro čisté rozdělení větví a prostředí bude `shouldAutoStartKiosk()` rozlišovat:
```javascript
function shouldAutoStartKiosk() {
  const params =
    typeof window !== "undefined" && window.location && window.location.search
      ? new URLSearchParams(window.location.search)
      : null;
  if (params && params.get("kiosk") === "0") return false;
  if (params && params.get("kiosk") === "1") return true;

  const isKioskHost =
    typeof window !== "undefined" &&
    (window.__AUTO_KIOSK__ === true ||
      (window.location && window.location.hostname === "10.20.0.81"));

  return Boolean(isKioskHost && !state.isStaticExport && !detectIsMobile());
}
```
Na větvi `kiosk-server` bude navíc v `index.html` nastaveno `window.__AUTO_KIOSK__ = true;` a v `app.js` výchozí `shouldAutoStartKiosk()` pro server, zatímco na větvi `main` je auto-kiosk vypnut (`window.__AUTO_KIOSK__ = false` / výchozí false pro localhost i GitHub Pages).

---

## 3. Dependencies

Všechny navrhované funkce využívají stávající auditované knihovny definované v projektu v `pyproject.toml`. Žádná nová externí závislost není potřeba:
- `httpx >= 0.27.0` (BSD-3-Clause)
- `beautifulsoup4 >= 4.12.3` (MIT)
- `lxml >= 5.2.0` (BSD-3-Clause)
- `pydantic >= 2.7.0` (MIT)

---

## 4. Test Specs

| Test ID | Typ | Popis a testované komponenty | Očekávaný výsledek |
|---|---|---|---|
| `TEST-ASP-FORM-EXTRACT-01` | Unit | Extrakce formuláře z reálného HTML Bakalářů (`extract_asp_form_inputs`) | Vrácena action URL, slovník obsahuje `__VIEWSTATE`, `__EVENTVALIDATION`, `__VIEWSTATEGENERATOR`, `DateEdit`, `ButtonNext: ""`; `ButtonPrev` je striktně vyloučen |
| `TEST-ASP-FORM-NO-BUTTON-02` | Unit | Extrakce z HTML bez `ButtonNext` | Slovník neobsahuje klíč `ButtonNext`, signalizuje nemožnost dalšího posunu |
| `TEST-FETCHER-FORWARD-FETCH-01` | Integration | Simulace stažení dneška a 2 následujících dnů | Všechny 3 dny jsou uloženy do SQLite s `data_source = 'web'`, vyvolány aktualizační události SSE, `fetch_once` vrátí `True` |
| `TEST-FETCHER-FORWARD-STOP-SAME-DATE-02` | Integration | Server vrátí po `ButtonNext` stejné datum | Stahování se po detekci `day_next.date <= last_date` čistě zastaví, nedojde k chybě |
| `TEST-FETCHER-FORWARD-PARTIAL-FAIL-03` | Integration | Dnešek a 1. den projdou, 2. den selže | Dnešek a 1. den zůstávají v DB, 2. krok zapíše varování, existující dny nejsou poškozeny |
| `TEST-FETCHER-OUTAGE-PRESERVES-DB-04` | Integration | Úplný výpadek Bakalářů při GET (HTTP 502/503/timeout) | Žádná data v SQLite nejsou smazána, stávající dny zachovány, status ERROR |
| `TEST-STORAGE-WEB-PRECEDENCE-05` | Integration | Souborový import týdenního rozvrhu nesmí přepsat existující webový den | Pondělí z webu je zachováno nedotčené (`data_source = 'web'`), zbývající dny jsou importovány |
| `TEST-BRANCH-MAIN-DESKTOP-NO-KIOSK-01` | Unit (JS) | Chování `shouldAutoStartKiosk()` na větvi `main` na desktopu | Vrátí striktně `false`. Aplikace zůstává v běžném interaktivním režimu s hlavičkou, patičkou a přepínačem pohledů |
| `TEST-BRANCH-MAIN-FORCE-KIOSK-PARAM-02` | Unit (JS) | Chování s parametrem `?kiosk=1` | Vrátí `true`, vyvolá `startKiosk()` |
| `TEST-BRANCH-KIOSK-SERVER-AUTO-DESKTOP-03` | Unit (JS) | Chování na hostiteli `10.20.0.81` nebo s `__AUTO_KIOSK__` | Vrátí `true`, automaticky se aktivuje kiosk s autoscrollem |
| `TEST-BRANCH-KIOSK-SERVER-ESCAPE-HATCH-04` | Unit (JS) | Únikový parametr `?kiosk=0` | Vrátí `false`, kiosk se nespustí |
| `TEST-UI-MULTI-DAY-TABS-ACTIVE-01` | Integration / UI | Stav záložek v 6denním kalendáři po stažení dopředných dnů | Záložky pro stažené dny mají `has_data: true`, nemají třídu `.disabled` ani atribut `disabled` |
| `TEST-STATIC-EXPORT-MULTI-DAY-FORWARD-01` | Integration | Příkaz `python -m app export-static` po uložení webových dnů | V `dist/data/` vzniknou platné JSONy pro všechny stažené dny a `index.json` obsahuje u všech `has_data: true` |
| `TEST-MIDNIGHT-ROLLOVER-AUTO-REFRESH-01` | Unit (JS) | Přechod půlnoci v pásmu `Europe/Prague` | `state.userManuallySelectedDate` se resetuje na `false`, vyvolá se `loadData('', false)` |

---

## 5. Security Considerations
1. SSRF ochrana: všechny odchozí URL prochází `validate_web_url()` (whitelist `ALLOWED_HOSTS`, blokování privátních IP, HTTPS only).
2. Ochrana tokenů ASP.NET: `__VIEWSTATE` a `__EVENTVALIDATION` jsou ošetřeny jako čistě neprůhledné textové řetězce.
3. Velikostní limity: max 5 MB na odpověď.
4. XSS ochrana: nulový `innerHTML`, výhradně `createElement` a `textContent`.
5. Anonymizace: i dopředné dny jsou v statickém exportu striktně anonymizovány.
