# Implementační plán 5: klávesa S, tlačítko Photo a kontrola rozlišení

Zdroj: nahrávka Watch Me `20261124-145239` (5:53, česky, celý rozsah; instrukce:
„implementační plán v češtině, zatím nic neimplementuj, počkej na schválení“).
Stav: **draft 1, schváleno a implementováno 2026-11-24.** Otázky zůstaly bez
odpovědi, takže platí návrhy z plánu: S bez `render.png` jen schválí a ukáže chybu;
prompta je čistě náhodná; tlačítko se jmenuje „Photo“, stav se neukládá; reload
drží frame; přehrávání běží dál; panel ukazuje i text s rozměry; počítají se
všechny obrázky.

## Cíl

1. **Klávesa S = „schválit a poslat náhodnou promptu“** (0:44–2:34). Stisk S udělá
   totéž co A (zelený řádek), pak v comboboxu náhodně vybere jednu z promptů
   v `assets/prompts` a stiskne **Add**. Opakovaný stisk S udělá totéž znovu, ale
   schválení **nikdy nevezme zpět**: řádek zůstane zelený, jen se znovu náhodně vybere
   prompta a znovu se stiskne Add.
2. **Přepínací tlačítko „Photo“ mezi Reload a Delete Selected** (2:47–5:06).
   Výchozí stav je nezamáčknuté. Když je zamáčknuté, při každém vstupu na animaci
   (kliknutím myší nebo šipkami) se posuvník postaví na **první** frame, který obsahuje
   `render-photo.png`. Platí to od chvíle zamáčknutí, **včetně právě zobrazené
   animace**.
3. **Kontrola rozlišení** (5:13–5:45). Při načtení animace se porovnají rozměry všech
   obrázků ve všech framech. Když nejsou všechny stejné, pozadí celého panelu Layers
   bude **tmavě červené** (ne ostře červené).

Na začátku nahrávky (0:12–0:44) je jen shrnutí stávajících zkratek A, D a
Ctrl+Mezerník, které se nemění. Větu „což ale zatím není plná sada“ čtu tak, že S je
doplňuje.

## Kroky

### 1. Název `render-photo.png` na jednom místě — `core/prompt_queue.py`

- Přidat `PHOTO_LAYER = layer_key("render-photo.png")`. Má platit
  `destination_for(render.png).name == "render-photo.png"`: konstanta se bude
  odvozovat ze `SOURCE_LAYER` a `DESTINATION_SUFFIX`, takže se tyto hodnoty nemůžou
  rozejít.
- Přidat `first_photo_frame(animation) -> int | None`: index prvního framu (v
  přirozeném pořadí), jehož `files` obsahuje `PHOTO_LAYER`. Když takový frame není,
  vrátí `None`.
- Pravidlo z CLAUDE.md zůstává splněné: jméno žije jen v `prompt_queue.py`. Na
  stromech bez `render-photo.png` tlačítko Photo jen nic nenajde.
- V CLAUDE.md doplnit `render-photo.png` do výčtu jmen v sekci „Universal folder
  rules“.
- **Ověření:** `tests/test_prompt_queue.py` ověří, že se najde první frame z několika,
  že bez fotky se vrátí `None` a že se nerozlišuje velikost písmen.

### 2. Schválení, které nic nevrací zpět — `ui/animation_panel.py`

- Přidat `approve(path)`. Když řádek ještě není schválený, zapíše `approved: true`
  (tím se nastaví i `approved_changed_at`) a zruší značku smazání. Když už schválený
  je, **nic nezapisuje**: čas zůstane z prvního schválení. Při chybě zápisu vrátí
  `False`; chyba se ukáže stejně jako dnes.
- Přidat `approve_selected() -> bool`.
- **Ověření:** dvojí `approve` nechá řádek zelený a soubor se podruhé nezmění. Po
  `approve` na označeném řádku zmizí značka.

### 3. Klávesa S — `ui/main_window.py`, `ui/master_bar.py`

- V `MasterBar` přidat `select_prompt(path)`, který v comboboxu viditelně vybere danou
  promptu. Uživatel tak vidí, co padlo; mění se tím i prompta uložená do QSettings při
  zavření.
- `MainWindow` dostane parametr `rng: random.Random | None = None`, aby šla náhoda v
  testech zafixovat.
- `_key_action`: `Qt.Key.Key_S` → `self.approve_and_add_random`. Platí pro S bez
  modifikátorů a ne v textovém poli, stejně jako A a D.
- `approve_and_add_random()`:
  1. Když vybraná animace v seznamu ještě není načtená animace (sken běží na pozadí),
     neudělá nic. Prompta tak nemůže odejít ke starému snímku, viz Rizika.
  2. `animations.approve_selected()`. Když zápis selže, skončí.
  3. Když Add jde použít (frame má `render.png` a nějaká prompta existuje): náhodná
     prompta (`rng.choice` ze všech promptů v comboboxu), pak `select_prompt` a
     `add_prompt()`. Značka nad posuvníkem a zpráva ve stavovém řádku se ukážou jako
     dnes.
  4. Když Add použít nejde, zůstane jen schválení a ve stavovém řádku se ukáže chyba
     „No render.png in this frame“ nebo „No prompts in assets/prompts“. Viz otázka 1.
- **Ověření** (`tests/test_main_window.py`):
  - S na neschválené animaci: řádek je zelený, v `prompt_queue/` je soubor, v logu je
    záznam a nad framem je značka.
  - Druhé S: řádek zůstává zelený, `approved_changed_at` se nezměnil a v logu je druhý
    záznam.
  - S na framu bez `render.png` jen schválí a ukáže chybu.
  - S v textovém poli cesty nic nedělá.

### 4. Tlačítko Photo — `ui/animation_panel.py`, `ui/main_window.py`

- V `AnimationPanel` přidat `photo_button = QPushButton("Photo")` s
  `setCheckable(True)`. V řádku tlačítek bude mezi `reload_button` a `delete_button`.
  Dostane tooltip „Jump to the first frame with render-photo.png“ a signál
  `photo_toggled(bool)`. Popisek je anglicky jako ostatní tlačítka, viz otázka 3.
- Ve výchozím stavu je nezamáčknuté a stav se **neukládá** do QSettings, takže každé
  spuštění začne nezamáčknuté. Viz otázka 4.
- V `MainWindow._on_scanned` se po výpočtu `index`:
  - Když je Photo zamáčknuté a nejde o reload téže animace, použije se
    `first_photo_frame(animation)`, pokud není `None`. Tím se přebije pravidlo „zůstaň
    na stejném čísle framu“.
  - Když animace fotku nemá, platí stávající pravidlo.
  - Reload (F5 nebo tlačítko Reload) dál drží aktuální frame. Viz otázka 5.
- Zamáčknutí tlačítka (`photo_toggled(True)`) se hned postaví na první fotku v otevřené
  animaci. Vymáčknutí nic nemění.
- Přehrávání: když běží, pokračuje od framu s fotkou. Pro prohlížení fotky je asi
  lepší ho zastavit, viz otázka 6.
- **Ověření:**
  - Strom, kde `a1` má `render-photo.png` ve frame1 a frame2 a `a2` ve frame0.
  - Se zamáčknutým Photo: `a1` → index 1, šipka dolů → `a2` → index 0.
  - Bez Photo: stávající chování.
  - Zamáčknutí na otevřené `a1` skočí na frame1.
  - Animace bez fotky drží číslo framu.

### 5. Kontrola rozlišení — nový `core/resolution.py`, `ui/layers_panel.py`, `ui/main_window.py`

- `core/resolution.py` (univerzální, bez jmen):
  - `image_sizes(animation) -> dict[tuple[int, int], int]` vrátí rozměr a počet
    obrázků. Pro každý soubor každého framu čte jen hlavičku
    (`QImageReader(path).size()`, bez dekódování). Nečitelné soubory, s neplatnou
    velikostí, vynechá.
  - `is_uniform(sizes) -> bool`.
- Rozměry se počítají ve **stejném vlákně na pozadí** jako `scan_animation`. Úloha
  vrátí `(animation, sizes)`, aby GUI nečekalo; při 10 framech a 15 vrstvách je to asi
  150 čtení hlaviček.
- `LayersPanel.set_size_warning(sizes | None)`:
  - Při různých rozměrech nastaví panelu (včetně seznamu vrstev) tmavě červené pozadí
    `#5A1A1A`.
  - Do řádku s nápovědou dole přidá text, např. „Images differ in size: 1672 x 941 (140),
    1920 x 1080 (10)“, aby bylo vidět, co nesedí. Viz otázka 7.
  - Při stejných rozměrech nebo bez animace vrátí normální barvu.
- Kontrola proběhne při každém načtení i reloadu animace. Při zavření animace se
  varování smaže.
- **Ověření:**
  - `tests/test_resolution.py`: stejné rozměry, různé rozměry, nečitelný soubor se
    přeskočí.
  - `tests/test_main_window.py`: animace s obrázkem 8 x 4 a 16 x 8 dá červené pozadí
    (zkontroluje se barva pozadí panelu nebo vlastnost, kterou panel vystaví), přepnutí
    na animaci se stejnými rozměry pozadí vrátí.
  - Existující testy, které schválně míchají rozměry (test roztažení), jen ukážou
    varování; to nevadí.

### 6. Dokumentace a kontroly

- `README.md`: klávesa S v tabulce kláves, tlačítko Photo v popisu levého panelu,
  červené pozadí panelu Layers.
- Odkaz na `implementation-plan-5.md` v seznamu plánů.
- Spustit `uv run ruff check`, `uv run ruff format --check` a `uv run pytest`.
- Vizuální kontrola na `D:\git\airplane-models-custom-engine\Output\render`
  (jen čtení, stav v paměti): tlačítko Photo v řadě, skok na frame s fotkou, červený
  panel na animaci s různými rozměry, pokud tam taková je.

## Rizika a předpoklady

- **S během načítání:** výběr v seznamu se mění hned, sken animace běží na pozadí.
  Kdyby S při rychlém posunu šipkami schválilo novou animaci a pak poslalo promptu pro
  frame **staré** animace, byl by to tichý omyl. Proto S nic neudělá, dokud vybraná
  animace není načtená (krok 3.1). Při velmi rychlém mačkání se tak může stát, že S
  „nic neudělá“.
- **Náhoda:** volí se rovnoměrně ze všech promptů a může padnout stejná prompta jako
  minule. Pak vznikne stejný soubor ve frontě, přepíše se a v logu bude další záznam.
  Viz otázka 2.
- **Ctrl+Space a Watch Me:** nic nového, S nemá modifikátor, takže se s Watch Me
  nekříží.
- **Photo a přehrávání:** při zamáčknutém Photo se ztrácí „zůstaň na stejném framu“
  mezi animacemi, ale jen u animací, které fotku mají.
- **Čtení hlaviček:** velmi velké animace (stovky framů) přidají ke skenu desítky ms.
  Hlavičky PNG/JPG jsou malé, takže to nepovažuji za problém.
- Předpokládám, že **„všechny snímky“** v kroku 3 znamená všechny obrázky (všechny
  vrstvy) ve všech framech, ne jen `render.png`. Masky `aircraft_*` se tedy počítají
  taky. Viz otázka 8.

## Otázky

1. Když frame nemá `render.png` (Add je šedé): má S aspoň schválit animaci a ukázat
   chybu (můj návrh), nebo nemá udělat vůbec nic?
2. Má opakované S vybírat **jinou** promptu než minule (nebo než všechny, které už
   frame má), nebo stačí čistá náhoda?
3. Popisek tlačítka: „Photo“ (anglicky jako Reload a Delete Selected), nebo doslova
   „Foto“?
4. Má si aplikace stav Photo pamatovat mezi spuštěními, nebo vždy začít nezamáčknutá
   (můj návrh podle 3:23)?
5. Má Reload (F5 nebo tlačítko) se zamáčknutým Photo také skočit na první fotku?
   Návrh: ne, reload drží aktuální frame. Typicky se reloaduje právě proto, že
   `render-photo.png` mezitím vznikla, a pak by skok mohl být vítaný.
6. Má skok na fotku zastavit přehrávání, nebo ho nechat běžet?
7. Stačí tmavě červené pozadí, nebo přidat i text s nalezenými rozměry (můj návrh)?
8. Kontrola rozlišení: všechny obrázky všech vrstev (můj návrh), nebo jen některé
   vrstvy?
