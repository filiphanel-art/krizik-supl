# Implementační plán: Automatická aktualizace GitHub Pages (2–3 dny dopředu) a zpětné doplnění týdne

## 1. Summary

### Popis problému
Uživatel nahlásil (středa 11. 11. 2026):
> „Tak všiml jsem si že na 127.0.0.1 je to správně a ukazuje to dva dny dopředu ale na github to neukazuje 2 dny dopředu“

### Kořenová příčina
1. Na `127.0.0.1` (`localhost`) běží živý Python server (`python -m app serve`), jehož `WebFetcher` na pozadí dnes (`11. 11.`) automaticky stáhl ze serveru Bakalářů nově publikovaný **Pátek 13. 11.** (2 dny dopředu od středy `11. 11.`) a uložil jej do `data/suplovani.db`.
2. GitHub Pages (`filiphanel-art.github.io`) však servíruje statické JSON soubory z větve `gh-pages` (`dist/data/*.json`), které byly vygenerovány včera v úterý `10. 11.` (kdy byl 2 dny dopředu čtvrtek `12. 11.` a pátek `13. 11.` ještě neexistoval).
3. V repozitáři chyběla automatická GitHub Actions úloha (`.github/workflows/update-gh-pages.yml`), která by pravidelně v cloudu spouštěla `python -m app export-static` a nahrávala čerstvé `dist/data/*.json` do větve `gh-pages`.

---

## 2. Interfaces & Data Flow

### 2.1 Zpětné doplnění aktuálního týdne v `app/fetcher.py` (`fetch_past_week`)
Když `export-static` běží v čistém prostředí (např. GitHub Actions runner uprostřed týdne ve středu nebo ve čtvrtek), `zmeny.aspx` při prvotním GET dotazu vrátí dnešní den (`11. 11.`). Aby v kalendáři na GitHub Pages nechyběly dřívější dny aktuálního týdne (`Pondělí 9. 11.`, `Úterý 10. 11.`), rozšíříme `WebFetcher.fetch_once()`:
```python
async def fetch_once(self, fetch_past_week: bool = False) -> bool:
```
- Výchozí hodnota `fetch_past_week: bool = False` zachovává 100% zpětnou kompatibilitu se všemi stávajícími unit testy.
- Pokud je `fetch_past_week=True` (voláno z `export_static_site(..., fetch_online=True)`):
  - Po stažení dnešního dne (`day0`) a až 3 dopředných dnů přes `ButtonNext` zkontroluje, zda je `day0` v pracovním týdnu (`weekday() in (1, 2, 3, 4)` – Út až Pá) a zda v `self.storage` chybí některý ze dnů od pondělí aktuálního týdne do včerejška.
  - Pokud některý předchozí den aktuálního týdne v DB chybí, použije výchozí HTML dnešního dne (`initial_html`, `initial_url`) a pomocí POST dotazů s `ButtonPrev` (max `day0.weekday()` kroků, nejvýše 4) stáhne a uloží předchozí dny aktuálního týdne až po pondělí (`day_prev.date >= monday_iso`).

### 2.2 GitHub Actions Workflow (`.github/workflows/update-gh-pages.yml`)
- Automatický workflow spouštěný:
  - Periodicky každých 30 minut během dne (`cron: '*/30 * * * *'`),
  - Při každém `push` do větve `main`,
  - Ručně přes `workflow_dispatch`.
- Kroky:
  1. `actions/checkout@v4` (větev `main`)
  2. `actions/setup-python@v5` (`python-version: '3.12'`)
  3. `pip install -r requirements.txt`
  4. `python -m app export-static --output dist` (stáhne z Bakalářů dnešek + až 3 dny dopředu + případně chybějící dny od pondělí a vygeneruje anonymizované `dist/data/*.json`)
  5. Nasazení obsahu složky `dist/` do větve `gh-pages`.

### 2.3 Okamžitá aktualizace `dist/data/`
- Spuštění `.venv/bin/python -m app export-static` vygeneruje `dist/data/day-2026-11-13.json` a aktualizuje `dist/data/index.json`, takže na GitHub Pages budou ihned aktivní záložky:
  - `Pondělí 9. 11.` (`has_data: true`)
  - `Úterý 10. 11.` (`has_data: true`)
  - `Středa 11. 11.` (`has_data: true` – dnešek)
  - `Čtvrtek 12. 11.` (`has_data: true` – 1 den dopředu)
  - `Pátek 13. 11.` (`has_data: true` – 2 dny dopředu)

---

## 3. Dependencies
Žádné nové Python ani JS závislosti.

---

## 4. Test Specs

| Test ID | Typ | Scénář | Očekávaný výsledek |
|---|---|---|---|
| `TEST-FETCHER-PAST-WEEK-BACKFILL-01` | Integration | `fetch_once(fetch_past_week=True)` spuštěno ve středu `2026-11-11` na prázdné DB | Stáhne dopředné dny přes `ButtonNext` (`12. 11.`, `13. 11.`) a zároveň doplní chybějící dny aktuálního týdne přes `ButtonPrev` (`10. 11.`, `9. 11.`) |
| `TEST-GITHUB-WORKFLOW-VALID-01` | Unit | Kontrola existence a platné YAML struktury `.github/workflows/update-gh-pages.yml` | Soubor existuje, je validní YAML, obsahuje `schedule`, `workflow_dispatch`, `export-static` a bezpečné permissions |

---

## 5. Security Considerations
- **GitHub Actions bezpečné oprávnění**: Workflow má explicitně deklarované minimální oprávnění `permissions: contents: write` a žádné secrets nejsou vypisovány do logu.
- **SSRF & Input Validation**: Zpětné kroky přes `ButtonPrev` používají stejnou funkci `extract_asp_form_inputs(..., button_name="ButtonPrev")` a validaci `validate_web_url()`.
- **Anonymizace**: Všechny exportované dny v `dist/data/*.json` zůstávají plně anonymizované (pouze zkratky učitelů).
