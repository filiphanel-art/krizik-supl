# Provozní příručka pro IT správce (`docs/provoz.md`)

Tento dokument slouží školnímu IT správci pro běžnou údržbu aplikace **Suplování Viewer** a pro řešení krizových stavů (změna struktury exportu po aktualizaci Bakalářů, výpadek sdílené složky nebo ztráta dat).

---

## 1. Kde sledovat stav aplikace

1. **Webová diagnostika `/admin/status`:**
   - Otevřete v prohlížeči `http://<adresa-serveru>:8000/admin/status` (nebo s `?format=json` pro strojové čtení do monitoringu Zabbix / Uptime Kuma).
   - Stránka zobrazuje:
     - zda běží sledování složky (`FolderWatcher`),
     - čas a název posledního úspěšně zpracovaného souboru,
     - případnou chybu posledního importu (`ERROR`),
     - tabulku **nerozpoznaných položek** (`unrecognized_items`), pokud se v HTML exportu objevila nová zkratka nebo neznámý typ řádku.
2. **Strukturované logy (`logs/suplovani.log`):**
   - Logy jsou ve formátu JSON (jeden záznam na řádek), automaticky rotované (`5 × 5 MB`) a neobsahují osobní údaje.
   - Zobrazení posledních chyb v Dockeru:
     ```bash
     docker compose logs --tail=50 suplovani-viewer
     ```

---

## 2. Scénář A: Zobrazuje se varování „Nelze zpracovat nový export“ (změna formátu HTML)

Pokud aplikace zobrazuje červený varovný pruh **„Nelze zpracovat nový export. Zobrazují se poslední platná data.“**, znamená to, že uživatelé **stále vidí poslední platný rozvrh**, ale nový soubor ve sdílené složce měl neočekávanou strukturu nebo byl poškozen.

### Postup řešení krok za krokem:
1. **Zkontrolujte detail chyby na `/admin/status`:**
   - V sekci *Historie posledních importů* zjistěte název souboru a přesný text chyby (`error_message`).
2. **Ověřte, zda nejde o chybně vyexportovaný soubor:**
   - Zkontrolujte soubor ve sdílené složce (`HOST_EXPORTS_DIR`).
   - Častá příčina: zástupkyně omylem vyexportovala jinou sestavu (např. *Rozvrh tříd* místo *Přehled suplování pro třídy*) nebo export přerušila.
   - Řešení: požádejte zástupkyni o nový export sestavy **Přehled suplování pro třídy** (`suplprehtrid.html`). Jakmile se uloží platný soubor, varování automaticky zmizí do 30 sekund.
3. **Pokud se změnila struktura po aktualizaci programu Bakaláři:**
   - Zkopírujte nový HTML soubor do složky `samples/` ve vývojovém prostředí (po případné anonymizaci).
   - Spusťte diagnostiku parseru:
     ```bash
     .venv/bin/pytest -v
     ```
   - Upravte pravidla v `app/parser.py` podle nové struktury tabulky (viz dokumentace `docs/format-analysis.md`), přidejte vzorek do testů a nasaďte novou verzi kontejneru:
     ```bash
     docker compose up -d --build
     ```

---

## 3. Scénář B: Objevily se „Nerozpoznané položky“ na `/admin/status`

Pokud se v Bakalářích objeví nový typ změny nebo neznámá značka v mřížce nepřítomných učitelů:
- Aplikace **nespadne** a celý den normálně zobrazí.
- Nerozpoznaný řádek nebo buňka je uložena do sekce *Nerozpoznané položky* (dole na stránce dne i v `/admin/status`).
- **Postup:** Podívejte se na surový obsah v `/admin/status`. Pokud jde o nový legitimní typ změny v Bakalářích, přidejte jej do funkce `_classify_change_type()` v `app/parser.py`.

---

## 4. Scénář C: Data jsou zastaralá nebo se neaktualizují (výpadek SMB/CIFS)

Pokud se zobrazí oranžové varování **„Upozornění: Data výpisu jsou starší než N hodin“**:
1. **Ověřte, zda zástupkyně uložila nový export** a zda se v Bakalářích změnilo *datum výpisu*.
2. **Ověřte připojení sdílené složky na hostitelském serveru:**
   - Na Linuxu zkontrolujte připojení CIFS mountu (`mount | grep cifs` nebo `ls -la /mnt/bakalari_supl`).
   - Pokud došlo k odpojení síťového disku po restartu Windows serveru, znovu připojte sdílenou složku (`mount -a`) a prípadně restartujte kontejner:
     ```bash
     docker compose restart suplovani-viewer
     ```

---

## 5. Scénář D: Zmizela data nebo je databáze poškozena

1. **Smazaný HTML soubor ve sdílené složce:**
   - Smazání souboru ve sdílené složce **nevymaže** data z aplikace – SQLite databáze (`data/suplovani.db`) si pamatuje posledních 14 dní (`SUPL_RETENTION_DAYS`).
2. **Obnova po smazání databáze `data/suplovani.db`:**
   - Pokud dojde ke ztrátě souboru `data/suplovani.db`, stačí nechat ve sdílené složce aktuální HTML export a restartovat službu (`docker compose restart`). Služba při startu složku ihned načte a databázi znovu vytvoří.
3. **Týdenní prázdniny / stará data po více než 14 dnech:**
   - Pokud nebyl po dobu delší než `SUPL_RETENTION_DAYS` (výchozí 14 dní) proveden žádný nový export, automatické чиštění vymaže dny starší než 14 dní. Pro prodloužení historie nastavte v `.env` např. `SUPL_RETENTION_DAYS=30`.
