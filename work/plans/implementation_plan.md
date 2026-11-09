# Implementation Plan: Kiosk Fullscreen, Odstranění Stale Banneru a Odolnost Importů

**Role:** Lead Software Architect (Read-Only)  
**Dokumentace:** Návrh pro [work/plans/implementation_plan.md](file:///Users/filip/Downloads/krizik_supl/work/plans/implementation_plan.md)  

---

## 1. Summary

Tento implementační plán řeší:
1. **Úplné potlačení banneru zastaralosti dat (`#banner-stale`)**:
   - Vizuální odstranění varovné lišty („Upozornění: Data výpisu jsou starší než 24 hodin...“) z uživatelského rozhraní ([app/static/app.js](file:///Users/filip/Downloads/krizik_supl/app/static/app.js) a `dist/app.js`), aby nerušila velkoformátové informační kiosky a studenty/učitele.
   - Zachování diagnostických informací o stáří dat v administrátorském rozhraní `/admin/status` a `/api/status`.
2. **Okamžitý režim Fullscreen / Kiosk na serveru (`10.20.0.81:8080` / desktop non-static běh)**:
   - Automatická aplikace třídy `body.kiosk` ihned při startu na desktopu v režimu serveru (`!state.isStaticExport && !detectIsMobile()`), okamžité skrytí horní lišty a patičky a maximalizace plochy pro mřížku.
   - Plynulý automatický posun (`kioskStep`), pokud obsah rozvrhu přesahuje výšku okna (`maxY > 12px`), a klidový stav bez posunu, pokud se veškerý obsah na obrazovku vejde.
   - Spuštění `requestFullscreen()` při startu + registrace jednorázového gesture listeneru (`click`, `pointerdown`, `touchstart`) na okně pro okamžitou aktivaci nativního fullscreenu při prvním dotyku/kliknutí uživatele (bezpečné překonání browser autoplay/fullscreen restrikcí).
   - Zachování možnosti kdykoliv režim kiosk opustit stiskem klávesy `Escape` nebo kliknutím na exit tlačítko (`#btn-kiosk-exit`).
3. **Potvrzení a garance provozní logiky a integrity dat**:
   - **Import ze souboru** (Bakaláři export z `C:\Krizik`): modul [app/watcher.py](file:///Users/filip/Downloads/krizik_supl/app/watcher.py) s detekcí stability souborů (`wait_for_file_stability`) spolehlivě importuje data do SQLite s `data_source = 'file'`.
   - **Web fetcher**: asynchronní modul [app/fetcher.py](file:///Users/filip/Downloads/krizik_supl/app/fetcher.py) stahuje na pozadí `zmeny.aspx` s exponenciálním retry mechanismem (3 pokusy).
   - **Rozšíření povolených hostitelů**: přidání `'suplovani.skolakrizik.cz'` do `ALLOWED_HOSTS` ve [app/fetcher.py](file:///Users/filip/Downloads/krizik_supl/app/fetcher.py) vedle `'klasifikace.skolakrizik.cz'` a dynamický `source_label` (`Web ({hostname})`).
   - **Nulová ztráta dat při výpadku webu**: při chybě HTTP (502, 503, 504), timeoutu či síťovém výpadku fetcher pouze zaznamená varování a chybu; **žádná data v SQLite nejsou smazána ani přepsána**, v databázi i na obrazovce zůstávají poslední platná data.
   - **Automatické přepnutí na nový kalendářní den (půlnoc/ráno)**: klient detekuje změnu kalendářního dne v časové zóně `Europe/Prague`, o půlnoci či ráno resetuje případný ruční výběr a automaticky načte a zobrazí nový aktuální den přes `chooseDefaultDate()`.
4. **Verzování assetů**:
   - Povýšení assetů na `styles.css?v=19` a `app.js?v=19` pro okamžitou invalidaci klientské mezipaměti.

---

## 2. Interfaces & Datové toky

### A. Potlačení `#banner-stale` v klientské vrstvě
V [app/static/app.js](file:///Users/filip/Downloads/krizik_supl/app/static/app.js) a `dist/app.js`:
- V funkci `renderBannersAndHeader(st, day)`:
  - Odstranit větev `els.bannerStale.classList.remove("hidden")`.
  - Nahradit explicitním trvalým potlačením:
    ```javascript
    if (els.bannerStale) {
      els.bannerStale.classList.add("hidden");
    }
    ```
- V [app/static/index.html](file:///Users/filip/Downloads/krizik_supl/app/static/index.html) a `dist/index.html`:
  - Element `#banner-stale` zůstává v DOM s třídou `hidden` pro zachování zpětné kompatibility referencí v existujících skriptech.

### B. Kiosk režim: Okamžitý start, Autoscroll a Fullscreen gesto
1. **Detekce automatického spuštění kiosku**:
   ```javascript
   function shouldAutoStartKiosk() {
     const params = typeof window !== "undefined" && window.location
       ? new URLSearchParams(window.location.search)
       : null;
     if (params && params.get("kiosk") === "0") return false;
     if (params && params.get("kiosk") === "1") return true;
     // Non-static export na desktopu (server runtime):
     return !state.isStaticExport && !detectIsMobile();
   }
   ```
2. **Okamžitá inicializace při načtení stránky**:
   - Pokud `shouldAutoStartKiosk()` je `true`:
     - Spustí se `startKiosk()`, což okamžitě nastaví `document.body.classList.add("kiosk")`, zobrazí `#btn-kiosk-exit`, spustí animační smyčku posunu `requestAnimationFrame(kioskStep)` a pokusí se o `root.requestFullscreen().catch(() => {})`.
     - V mřížce rozvrhu se okamžitě počítá s výškou pro kiosk (`window.innerHeight - 110px`), čímž se maximalizuje vertikální prostor.
3. **Jednorázový First-Click Fullscreen Handler**:
   Moderní prohlížeče blokují volání `requestFullscreen()` bez předchozí uživatelské interakce (vyjma Chrome spuštěného s parametrem `--kiosk`). Pro hladké zajištění nativního fullscreenu se registruje jednorázový zachytávací posluchač:
   ```javascript
   function armKioskFullscreenGesture() {
     const onFirstInteraction = () => {
       if (kiosk.active && !document.fullscreenElement) {
         const root = document.documentElement;
         if (root.requestFullscreen) {
           root.requestFullscreen().catch(() => {});
         } else if (root.webkitRequestFullscreen) {
           root.webkitRequestFullscreen();
         }
       }
       window.removeEventListener("click", onFirstInteraction, true);
       window.removeEventListener("touchstart", onFirstInteraction, true);
       window.removeEventListener("pointerdown", onFirstInteraction, true);
     };
     window.addEventListener("click", onFirstInteraction, true);
     window.addEventListener("touchstart", onFirstInteraction, true);
     window.addEventListener("pointerdown", onFirstInteraction, true);
   }
   ```
4. **Ukončení Kiosku**:
   - `btnKioskExit.addEventListener("click", stopKiosk);`
   - Klávesa `Escape` -> `stopKiosk()`.
   - Událost `fullscreenchange` (`!document.fullscreenElement && kiosk.active`) -> `stopKiosk()`.
   - V `stopKiosk()` se odebere třída `body.kiosk`, zastaví autoscroll (`cancelAnimationFrame`), skryje exit tlačítko a vyvolá `renderAll()`.

### C. Whitelist domén ve Web Fetcheru a dynamický Source Label
1. Ve [app/fetcher.py](file:///Users/filip/Downloads/krizik_supl/app/fetcher.py):
   ```python
   ALLOWED_HOSTS = {
       "klasifikace.skolakrizik.cz",
       "suplovani.skolakrizik.cz",
   }
   ```
2. Dynamické určení `source_label` podle cílové URL:
   ```python
   host = urlsplit(url).hostname or "web"
   for day in parse_result.days:
       day.data_source = "web"
       day.source_label = f"Web ({host})"
       day.fetched_at = now_iso
       saved = self.storage.save_web_day(day, source_hash=content_hash)
   ```
3. V [app/database.py](file:///Users/filip/Downloads/krizik_supl/app/database.py) (`Storage.save_web_day`):
   - Místo hardcodovaného řetězce v SQL dotazu předat parametrizovanou hodnotu `day.source_label or f"Web ({host})"`.

### D. Automatické přepnutí na nový den (Midnight & Morning Rollover)
1. **Zjištění pražského kalendářního dne**:
   ```javascript
   function getPragueCalendarDate() {
     return new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Prague" });
   }
   ```
2. **Správa stavu klienta**:
   - `state.lastCalendarDate = getPragueCalendarDate();`
   - `state.userManuallySelectedDate = false;` (nastaveno na `true` pouze tehdy, klikne-li uživatel explicitně na záložku dne).
   - `state.lastUserInteraction = Date.now();`
3. **Logika v periodické smyčce (25 s) a SSE `update` listeneru**:
   - V `setupLiveUpdates()`:
     ```javascript
     function checkCalendarDayAndRefresh(isSseUpdate) {
       const today = getPragueCalendarDate();
       const dayChanged = today !== state.lastCalendarDate;
       const kioskInactivityExpired = kiosk.active && state.userManuallySelectedDate && (Date.now() - state.lastUserInteraction > 300000);

       if (dayChanged || kioskInactivityExpired || (!state.userManuallySelectedDate && isSseUpdate)) {
         if (dayChanged) state.lastCalendarDate = today;
         state.userManuallySelectedDate = false;
         loadData("", false); // Automatický výběr nového aktuálního dne
       } else {
         loadData(state.selectedDate, true); // Ponechání aktivní volby
       }
     }
     ```
   - Při půlnoci kiosek automaticky přepne na nový den.
   - Pokud ráno dorazí čerstvá data z webu pro dnešní den (který předtím neměl suplování vypsané), kiosek ihned přepne na dnešní rozvrh.

---

## 3. Dependencies (URL zdroje a licence)

Žádné nové externí knihovny nejsou pro realizaci vyžadovány. Řešení využívá výhradně standardizovaná webová API a stávající knihovny projektu:

| Závislost / Standard | Účel | Oficiální specifikace / Dokumentace | Licence | Známá CVE |
|---|---|---|---|---|
| **W3C Fullscreen API** | Celoobrazovkový režim (`requestFullscreen`, `exitFullscreen`, `fullscreenchange`) | https://developer.mozilla.org/en-US/docs/Web/API/Fullscreen_API | W3C Standard | N/A (prohlížečový standard) |
| **W3C DOM Animation & Events** | Plynulý autoscroll (`requestAnimationFrame`, `scrollTo`), dotyková gesta | https://developer.mozilla.org/en-US/docs/Web/API/window/requestAnimationFrame | W3C Standard | N/A (prohlížečový standard) |
| **ECMA-402 Intl / sv-SE** | Získání ISO data dne v časovém pásmu `Europe/Prague` (`toLocaleDateString`) | https://tc39.es/ecma402/#sec-intl.datetimeformat | ECMA Standard | N/A (JS standard) |
| **HTTPX (v0.27.x)** | Asynchronní HTTP klient pro fetcher s timeouty a retry logikou | https://www.python-httpx.org/ | BSD-3-Clause | Žádné v řadě 0.27.x |
| **FastAPI & Starlette** | Backend endpointy `/api/schedule`, `/api/events` a `/admin/status` | https://fastapi.tiangolo.com/ | MIT | Žádné kritické CVE |
| **Watchdog** | Sledování složky `C:\Krizik` pro okamžitou detekci souborového exportu | https://pythonhosted.org/watchdog/ | Apache-2.0 | Žádné |

---

## 4. Test Specs (ID, Typ, Edge-cases, Očekávaný výsledek)

| ID testu | Typ testu | Edge-cases | Očekávaný výsledek |
|---|---|---|---|
| `TEST-UI-SUPPRESS-STALE-BANNER-01` | Unit (Frontend DOM / Node.js) | Payload se stavem `is_stale: true`, `has_data: true`, `age_hours: 72`; vícenásobné volání `renderBannersAndHeader`. | `#banner-stale` má třídu `.hidden`, text varování se v DOM nezobrazí a neruší kiosek. |
| `TEST-KIOSK-AUTO-START-DESKTOP-01` | Unit (Frontend DOM) | Běh na desktopu (`innerWidth: 1920`) při `isStaticExport: false`; srovnání s `?kiosk=0` (escape hatch) a mobilní šířkou `375px`. | Na desktopovém serverovém běhu je automaticky aktivována třída `body.kiosk`, `kiosk.active: true`, `#btn-kiosk-exit` je viditelný. Na mobilu nebo s `?kiosk=0` zůstává standardní zobrazení. |
| `TEST-KIOSK-FIRST-CLICK-FULLSCREEN-01` | Unit (Interaction) | Browser zamítne `requestFullscreen()` při startu bez gesta; následně uživatel klikne na obrazovku (`click` / `touchstart`). | Po prvním kliknutí se vyvolá `requestFullscreen()`, listener se odregistruje a nezpůsobuje zbytečné opakované volání. |
| `TEST-KIOSK-EXIT-ESC-AND-BUTTON-01` | Unit (Frontend Events) | Stisk klávesy `Escape` nebo kliknutí na `#btn-kiosk-exit` během aktivního autoscrollu. | Autoscroll se zastaví (`cancelAnimationFrame`), třída `body.kiosk` je odebrána, obnoví se standardní záhlaví a ovládací prvky. |
| `TEST-FETCHER-ALLOWED-HOSTS-01` | Unit (Backend Security) | URL s `suplovani.skolakrizik.cz`, `klasifikace.skolakrizik.cz`, nepovolená doména `utocnik.cz`, plain HTTP schéma, nestandardní port 8080, privátní IP `10.20.0.81`. | `validate_web_url` úspěšně validuje obě školní subdomény na HTTPS/443; neznámé domény, HTTP a interní IP striktně odmítne s `FetchError`. |
| `TEST-FETCHER-SOURCE-LABEL-DYNAMIC-01` | Integration (Backend) | Fetcher nakonfigurován s `https://suplovani.skolakrizik.cz/next/zmeny.aspx`. | V SQLite i v odpovědi `/api/schedule` má den atribut `source_label = 'Web (suplovani.skolakrizik.cz)'`. |
| `TEST-FETCHER-DB-PRESERVATION-ON-FAILURE-01` | Integration (Backend Resilience) | Simulace HTTP 503 z Bakalářů po 3 pokusech, simulace síťového timeoutu, poškozené HTML. | `fetch_once()` vrátí `False`, do logu zapíše varování, v databázi SQLite zůstávají 100% zachována stávající platná data bez vymazání. |
| `TEST-FILE-IMPORT-PRESERVATION-ON-WATCHER-01` | Integration (Backend File Watcher) | Zápis validního exportu do `C:\Krizik` vs. zápis nevalidního/poškozeného souboru. | Validní export se bezchybně uloží s `data_source = 'file'`; poškozený soubor zapíše chybu do `import_runs`, ale existující rozvrhové tabulky zůstávají netknuté. |
| `TEST-CALENDAR-MIDNIGHT-ROLLOVER-01` | Unit (Frontend Rollover) | Kiosek běží přes noc s vybraným pondělím; o půlnoci se pražské datum změní na úterý. | Během 25s kontroly se detekuje změna dne, `userManuallySelectedDate` se resetuje na `false`, zavolá se `loadData("", false)` a kiosek automaticky přepne na nový den. |
| `TEST-CALENDAR-MORNING-DATA-ARRIVAL-01` | Integration (Client / Server) | Ráno v 06:00 dnešek nemá data (`has_data: false`); v 06:30 web fetcher stáhne dnešní zmeny.aspx a pošle SSE. | Klient bez ručního výběru automaticky přejde na dnes publikované suplování bez nutnosti zásahu obsluhy. |
| `TEST-STATIC-EXPORT-VERSION-19-01` | Integration (Asset Versioning) | Kontrola odkazů na skripty a styly v šablonách i statickém exportu. | `styles.css?v=19` a `app.js?v=19` jsou konzistentně nastaveny v celém projektu. |

---

## 5. Security Considerations

1. **SSRF Ochrana ve Web Fetcheru**:
   - Hostitel musí patřit striktně do `ALLOWED_HOSTS = {"klasifikace.skolakrizik.cz", "suplovani.skolakrizik.cz"}`.
   - Blokování privátních rozsahů RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16`), loopback (`127.0.0.0/8`, `::1`) a IPv6 prefixů.
   - Povolen výhradně bezpečný protokol HTTPS a port 443. Validace probíhá před odesláním i při případných přesměrováních.
2. **Klientská bezpečnost DOM & XSS prevence**:
   - Veškeré vykreslování v `app.js` probíhá striktně přes standardní bezpečné DOM metody (`document.createElement`, `textContent`, `setAttribute`), vylučující injection útoky.
   - Zachování souladu s politikou uživatelské aktivace prohlížečů (User Activation API).
3. **Integrita dat a odolnost vůči DoS / výpadkům**:
   - Selhání externího webu Bakalářů ani souborového importu nikdy nesmaže stávající data v SQLite úložišti (fail-safe zachování posledního konzistentního stavu).
   - Omezení velikosti stahovaných a importovaných souborů na `max_file_size_bytes` (5 MB).
