# Implementační plán 6: fronta promptů do `prompt_queue/to_process`

Zdroj: nahrávka Watch Me `20261124-150955` (1:18, česky, celý rozsah; instrukce:
„implementační plán v češtině, zatím nic neimplementuj, počkej na schválení“).
Stav: **draft 1, schváleno a implementováno 2026-11-24.** Otázky zůstaly bez
odpovědi, takže platí návrhy z plánu: aplikace do `processed` nesahá a cesta je
pevná.

## Cíl

Všechno, co přidá promptu do fronty, má zapisovat soubor do složky
`D:\git\ai-mod-painter\prompt_queue\to_process`, ne přímo do `prompt_queue`
(0:47–1:12). Týká se to tlačítka **Add**, klávesy **Ctrl+Mezerník** a klávesy **S**.

Na obrazovce (1:02) je vidět nové uspořádání složky `prompt_queue`:

- `to_process/` – sem patří nová zadání;
- `processed/` – sem je přesouvá zpracovatel;
- `master_prompt.md` – pokyny pro zpracovatele. Ten bere soubory přímo z `to_process`.

Všechny tři cesty volají stejnou funkci `add_prompt` → `enqueue(..., QUEUE_DIR)`, takže
stačí změnit jedno místo.

## Kroky

### 1. Cílová složka — `src/ai_mod_painter/core/prompt_queue.py`

- Rozdělit konstantu na dvě:
  - `QUEUE_ROOT = PROJECT_DIR / "prompt_queue"`
  - `QUEUE_DIR = QUEUE_ROOT / "to_process"`
- Upravit docstring modulu: soubor vzniká v `prompt_queue/to_process/<hash>.md`, kde ho
  vyzvedne zpracovatel. Ten ho po zpracování přesune do `prompt_queue/processed`; aplikace
  do `processed` nesahá.
- `enqueue` už dnes složku vytváří (`mkdir(parents=True, exist_ok=True)`), takže
  funguje i tehdy, když `to_process` chybí.
- Název souboru (hash), jeho obsah, atomický zápis i záznam v
  `ai-mod-config.json` (`queue_file` = jen název souboru) zůstávají beze změny.
- Žádná migrace, viz CLAUDE.md. Ve složce `prompt_queue` teď stejně žádné staré
  soubory fronty nejsou, jen `master_prompt.md` a dvě podsložky.

### 2. Okno — `src/ai_mod_painter/ui/main_window.py`

- Beze změny logiky: výchozí `queue_dir=QUEUE_DIR` teď ukazuje na `to_process`.
- Zpráva po Add ve stavovém řádku zůstává („Queued … as <hash>.md“).

### 3. Testy

- `tests/test_prompt_queue.py`: nový test, že
  `QUEUE_DIR == PROJECT_DIR / "prompt_queue" / "to_process"`, a test, že
  `enqueue` vytvoří chybějící vnořenou složku `…/prompt_queue/to_process` (v `tmp_path`).
- Testy okna mají vlastní `queue_dir` v `tmp_path`, takže se nemění.

### 4. Dokumentace a kontroly

- `README.md`, sekce Prompt queue: `prompt_queue/to_process/<hash>.md`. Přidat
  větu, že zpracovatel přesouvá hotové soubory do `prompt_queue/processed`.
- Odkaz na `implementation-plan-6.md` v seznamu plánů.
- `.gitignore` už ignoruje celé `prompt_queue/`, takže se nemění.
- Spustit `uv run ruff check`, `uv run ruff format --check` a `uv run pytest`.
- Ruční ověření: v aplikaci stisknout Add (nebo Ctrl+Mezerník nebo S). Nový
  `<hash>.md` se musí objevit v `prompt_queue\to_process` a ne přímo v
  `prompt_queue`.

## Rizika a předpoklady

- **Opakované přidání téže prompty pro týž frame:** hash je stále stejný. Soubor tak
  vznikne v `to_process` znovu, i když stejnojmenný soubor už leží v `processed`.
  `master_prompt.md` si tu odporuje:
  - krok 2 chce před spuštěním ověřit, že v `processed` soubor stejného názvu ještě
    není (zpracovatel by se mohl zastavit s chybou);
  - krok 4 říká, že se má v `processed` přepsat.

  Aplikace s tím nic nedělá. `master_prompt.md` je mimo git a patří tobě, viz
  otázka 1.
- Předpokládám, že „To Process“ z nahrávky (0:47) je složka `to_process`, kterou jsi
  ukázal v Průzkumníku (1:02) a jejíž rodičovskou cestu jsi zkopíroval do schránky.
- Předpokládám, že aplikace do `processed` nijak nezasahuje: nečte ji, nemaže a
  neukazuje stav zpracování.

## Otázky

1. Má Add vědět o `processed`? Například varovat nebo nejdřív smazat stejnojmenný soubor
   v `processed`, aby zpracovatel podle kroku 2 v `master_prompt.md` nenarazil na
   chybu. Návrh: aplikace nic nedělá a v `master_prompt.md` se sjednotí krok 2 s
   krokem 4 (přepsat).
2. Stačí natvrdo `prompt_queue/to_process` v repozitáři, nebo má jít cesta nastavit
   (např. v QSettings)? Návrh: natvrdo, jako dnes.
