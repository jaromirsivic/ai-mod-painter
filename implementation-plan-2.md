# Implementation plan 2: review, layer preset, playback continuity, prompt queue

Source: Watch Me recording `20261124-050956` (10:41, Czech, whole range; instructions:
"implementation plan in English, do not implement yet, wait for approval"). Answers to
the open questions of draft 1 in chat (2026-11-24): the CLAUDE.md amendment is accepted;
Delete Selected deletes permanently after a confirmation dialog, no Recycle Bin; any
manual layer change switches the combo to Custom, and every animation opens in Default;
F5 stays as it is; the frame position is kept also while stopped; queue files are named
`prompt-YYYY-MM-DD-HH-MM-SS`; `assets/prompts` is committed ("prompts - Copy" was
deleted by the user).
Status: **draft 2, approved and implemented 2026-11-24.**

## Goal

Four changes to AI Mod Painter:

1. **Review of animations** (left panel): each animation row gets a **thumbs-up** icon
   (approve: the row turns green and `ai-mod-config.json` is written into the animation
   folder) and a **trash** icon (mark for deletion: the row turns red, nothing is deleted
   yet). A new row under the path box holds **Reload** and **Delete Selected**.
2. **Layer preset** (right panel): a combo box next to the "Layers" title with
   **Default** and **Custom**. Default stacks the layers by fixed rules
   (`render_scene.png` at the bottom, `render.png` above it, everything else above,
   `*aircraft*` layers red and hidden). Any manual change switches to Custom; opening
   another animation always returns to Default.
3. **Frame position and playback** survive switching animations: playback keeps running,
   and the frame number stays when the new animation has enough frames (else frame 1).
4. **Prompt queue** (master bar, far right): a combo box of the prompt templates in
   `assets/prompts/*.md` and an **Add** button. Add fills the template with the current
   frame's `render.png` and writes the result into `prompt_queue/`.

How I read some words of the transcript: "AI pomlčka mod pomlčka config.json" =
`ai-mod-config.json`; "prompt QE / QEUE s podtržítkem" = `prompt_queue`; "render
potržítko scéne" = `render_scene.png`; "source potržítko image" = `{SOURCE_IMAGE}`;
"render pomlčka foto" was corrected in speech to "render pomlčka photo" =
`render-photo.png`.

## Steps

### 1. CLAUDE.md amendment

Extend "Universal folder rules": the folder model (`core/library.py`) stays universal;
name-based rules (`render_scene.png`, `render.png`, `aircraft`) live only in
`core/layer_presets.py` and `core/prompt_queue.py`, and the app must keep working on
trees without these names (generic layer order, Add disabled).

### 2. Review state in the core — new `src/ai_mod_painter/core/review.py`

- `CONFIG_NAME = "ai-mod-config.json"`, written directly into the animation folder
  (the folder that holds the frame folders). The library already ignores it (it is a
  file, not a subfolder).
- Structure: `{"approved": true}` (a JSON object, so more keys can come later; unknown
  keys are kept when rewriting).
- `read_approved(folder) -> bool`: missing file, unreadable or invalid JSON → `False`.
- `write_approved(folder, approved: bool)`: read-modify-write, write to a temp file in
  the same folder and `os.replace` it (atomic). Un-approving writes `false`.
- `delete_animation(folder)`: **permanent** delete with `shutil.rmtree` (no Recycle
  Bin); read-only files are made writable and retried (`onexc` handler, common on
  Windows); returns the error text on failure.
- **Verify:** `tests/test_review.py` — round trip, missing/broken file, other keys kept,
  delete of a tree with a read-only file.

### 3. Animation list rows — `ui/animation_panel.py`

- New delegate (same pattern as `_LayerDelegate` in `layers_panel.py`): paints the name
  and, at the right end of the row, a **trash** and a **thumbs-up** icon; clicks on the
  icons are handled in `editorEvent` and do not change the selection.
- Row background: **gray** by default, **green** when approved, **red** when marked for
  deletion (red wins). The current-row highlight stays visible (accent bar on the left,
  like today).
- Thumbs-up toggles approval and calls `write_approved` at once; it also clears a
  deletion mark. Trash toggles the mark (in memory only, kept across pages, cleared by
  Reload); it does not change the approval file.
- On every page fill (`_fill`), read `ai-mod-config.json` of the up to 100 visible
  folders (synchronous; 100 small reads on a local disk take a few ms).
- New row under the path row: **Reload** and **Delete Selected** buttons.
  - **Reload:** list the root again, re-read approvals, clear deletion marks, jump to
    **page 1**; the open animation is rescanned. **F5 stays as today** (lists the root
    again, keeps the page and the marks).
  - **Delete Selected:** enabled only when something is marked. A modal dialog asks
    "Permanently delete N animation folders? This cannot be undone." with Yes / No
    (No is the default button). On Yes, every marked folder (on all pages) is deleted
    permanently; failures are reported in the status line; the list is reloaded
    keeping the page. If the open animation is among them, it is closed first.
- **Verify:** `tests/test_animation_panel.py` (new) on a temp tree from `conftest.py`:
  click the icons via the delegate rects, check colors/roles, the JSON file, Reload
  returning to page 1 while F5 keeps the page, Delete Selected (dialog answered by a
  monkeypatched `QMessageBox`) removing exactly the marked folders, No removing nothing.

### 4. Layer preset — new `core/layer_presets.py`, `ui/layers_panel.py`, `ui/main_window.py`

- `default_preset(layers) -> list[LayerState]` (bottom first), names compared
  case-insensitively by layer key:
  1. `render_scene.png` (if present) at the bottom: eye **off**, R **off**;
  2. `render.png` above it (or at the bottom without a scene): eye **on**, R **off**;
  3. every other layer above, in today's default order (most frames lower, then name);
     a layer whose name contains `aircraft` gets R **on** and eye **off**, others eye
     on, R off.
  (This is the set-up visible in the recording at 4:38.)
- `LayersPanel`: a `QComboBox` right of the "Layers" title with `Default` / `Custom`.
  - Any manual change — eye, R, or reordering a row — switches the combo to
    **Custom** (without re-applying anything).
  - Choosing **Default** in the combo re-applies `default_preset` to the open
    animation. Choosing **Custom** by hand changes nothing.
  - Opening **another animation always sets Default** and applies the preset, even if
    the combo was on Custom.
  - Reload / F5 of the **same** animation keeps the current layer states (and the
    combo); layers new in the rescan get their preset position and flags.
- The carry-over of the layer set-up between animations is replaced by this rule, so
  `LayerMemory` (`core/layer_state.py`), its tests in `tests/test_layer_state.py`,
  `test_layer_state_carries_over_to_next_animation` and the README "Carry-over" line are
  removed (no backward compatibility). `LayerState` stays.
- **Verify:** `tests/test_layer_presets.py` (with/without scene, without `render.png`,
  `Aircraft` in different case, a tree with none of the names); main-window tests: a
  toggle or a reorder switches to Custom; opening another animation returns to Default;
  choosing Default re-applies the preset.

### 5. Frame position and playback — `ui/main_window.py`

- `open_animation` no longer calls `stop()`; the timer keeps running.
- In `_on_scanned` for a *new* animation, playing or stopped: keep the current frame
  index if the new animation has enough frames (`index < len(frames)`), otherwise go to
  frame 1. Example: on frame 10 of 10, a 5-frame animation opens on frame 1, a
  20-frame animation on frame 10.
- An animation without frames still stops playback.
- **Verify:** `tests/test_main_window.py` — stopped and playing, switch to a longer and
  to a shorter animation, check `is_playing()` and `frame_index`.

### 6. Prompt queue — new `core/prompt_queue.py`, `ui/master_bar.py`, `ui/main_window.py`

- Paths: `PROJECT_DIR = Path(__file__).resolve().parents[2]` (the repository; uv
  installs the project editable), `PROMPTS_DIR = PROJECT_DIR / "assets" / "prompts"`,
  `QUEUE_DIR = PROJECT_DIR / "prompt_queue"` (created on first Add).
- `list_prompts() -> list[Path]`: `*.md` in `PROMPTS_DIR`, sorted naturally; the combo
  shows the file name without `.md`.
- `destination_for(source)`: same folder, `<stem>-photo<suffix>` → `render-photo.png`.
- `enqueue(template, source) -> Path`: read the template (UTF-8), replace every
  `{SOURCE_IMAGE}` and `{DESTINATION_IMAGE}` with absolute paths, write
  `QUEUE_DIR/prompt-YYYY-MM-DD-HH-MM-SS.md` (local time) atomically (temp file +
  `os.replace`, so a consumer never reads a half-written file). Two Adds within the same
  second get `-2`, `-3`, … appended so nothing is overwritten.
- `MasterBar`: after the stretch, before the right panel toggle: `QComboBox` + **Add**
  button. MainWindow fills the combo at start and on Reload/F5.
- **Add** is enabled only when an animation is open, a prompt is chosen and the
  **current frame** has `render.png`; it updates on every frame change. Clicking uses
  the frame on screen at that moment; the status line confirms what was queued. An
  existing `render-photo.png` does not block Add (the consumer overwrites it).
- `.gitignore`: add `prompt_queue/`.
- **Verify:** `tests/test_prompt_queue.py` — substitution of both placeholders, the
  destination name, the file name format and the same-second suffix, UTF-8 Czech text;
  a main-window test for the enabled state of Add.

### 7. Docs, assets and checks

- README: the review icons and buttons (permanent delete), `ai-mod-config.json`, the
  Default / Custom layer modes (replacing "Carry-over"), the frame position on switching,
  the prompt queue.
- Commit `assets/prompts/*.md` with the implementation. `assets/scripts/` stays
  untracked unless you say otherwise.
- `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`; then a manual run
  on `D:\git\airplane-models-custom-engine\Output\render`.

## Risks

- **Permanent delete** cannot be undone; the only safeguard is the modal confirmation
  with the folder count (No as the default button). A folder with a file locked by
  another program is deleted only partly; the error is reported.
- Writing `ai-mod-config.json` into the render output may be unexpected for the
  rendering pipeline, if it rewrites or cleans those folders.
- Approval reads on a slow/network disk could make paging laggy (then move them to the
  worker thread).
- The generated `render-photo.png` becomes a new layer after Reload (it lands among
  "other" layers, visible).
- `PROJECT_DIR` relies on running from the repository (true for `start.bat` / `uv run`).

## Assumptions (say if any is wrong)

- Deletion marks live in memory only; approvals live in `ai-mod-config.json`.
- Queue files have the `.md` extension.
