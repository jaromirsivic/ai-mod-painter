# Implementation plan 7: A, S and D move down, render-photo.png above render.png

Source: Watch Me recording `20261125-002758` (2:08, Czech, whole range; instructions:
"implementation plan in English, do not implement yet, wait for approval"), plus your
answers in chat on 2026-11-25.
Status: **draft 5, approved and implemented 2026-11-25.** Draft 2 adds A
(chat), keeps `render-photo.png` visible, and confirms that S moves down after
approving even when it then shows an error. Draft 3 adds the new Ctrl+Space (chat):
it shows or hides `render_aircraft.png`. Draft 4 spells out A on a red row and D on a
green row (chat). Draft 5 settles the same key twice: A on a green row and D on a red
row turn it grey (chat).

## Goal

1. **A, S and D move to the next animation** (0:00–0:37 for S and D; A from the
   chat). After the key does what it does today, the focus moves one row down, as if
   the user then pressed ↓. The point is faster deleting and approving:
   - **A** approves the animation (the row turns green), then moves down;
   - **S** approves the animation (green), saves a random prompt for the frame that is
     selected now into `prompt_queue/to_process`, then moves down;
   - **D** marks the animation for deletion (the row turns red), then moves down.
2. **`render-photo.png` sits directly above `render.png`** in the Default layer
   preset (0:42–1:01, arrows #1 and #2). Today it ends up at the top of the list, above
   the aircraft mask layers.
3. **Ctrl+Space shows or hides `render_aircraft.png`** (1:09–2:08, arrows #3 and #4
   at that layer; the wording is from the chat, because that speech was not
   transcribed). It is the same as clicking the eye of that layer. When the animation,
   or the frame shown now, has no `render_aircraft.png`, Ctrl+Space does nothing.
   Ctrl+Space no longer adds a prompt; the **Add** button and S still do.

## Steps

### 1. A, S and D then ↓ — `src/ai_mod_painter/ui/main_window.py`

- New methods `approve_and_next()`, `mark_and_next()` and `approve_add_and_next()`,
  mapped to A, D and S in `_key_action`. Each runs today's action, then calls
  `self.animations.select_next(1)`.
- **A:** `toggle_approved_selected()`, then `select_next(1)`.
- **D:** `toggle_marked_selected()`, then `select_next(1)`. This happens on every
  press, also when D takes a mark away, because the recording says "whenever the user
  presses S or D".
- What A and D do to the row, by its state before the key (draft 4, from the chat):

  | Row before | A | D |
  |---|---|---|
  | plain | green (approved) | red (marked for deletion) |
  | red (marked) | **green**: approved, mark removed | **grey** (plain): mark removed |
  | green (approved) | **grey** (plain): approval taken back | **red**: marked, approval taken back |

  In every case the focus then moves one row down. All four cases you described
  already work this way today: `toggle_approved` removes the deletion mark when it
  approves and takes the approval back on a green row; `toggle_marked` takes the
  approval back when it marks and removes the mark on a red row. So the action methods in `animation_panel.py` stay unchanged; only the move
  down is new.
- A and D move only when a row was selected; with no selection they do nothing, as
  today.
- **S:** `approve_and_add_random()` returns `True` once it got past its guards and
  approved the animation, and `False` when it did nothing:
  - no animation is loaded;
  - the selected animation is still loading;
  - the approval could not be written.

  On `True` the selection moves down, also in the cases that only approve and show an
  error (no prompts, or no `render.png` in the frame). On `False` it stays, so a
  quick second S that comes before the next animation has loaded does not skip a row
  that was never approved.
- Order: the Add runs before the move. It is synchronous and uses the current frame
  of the animation just approved, so the queue file is always for the right animation.
- `select_next(1)` already goes on to the next page and stops at the last animation.
  At the very end A, S and D do their action and the selection simply stays.
- The thumb and trash buttons in the list rows do **not** move the selection; only
  the keys do.
- Docstrings of `approve_and_add_random` and `eventFilter`, plus `_key_action`.

### 1b. Ctrl+Space shows or hides render_aircraft.png

- `src/ai_mod_painter/core/layer_presets.py`: new constant
  `AIRCRAFT_LAYER = layer_key("render_aircraft.png")`. The name lives only here
  (CLAUDE.md), and it is compared without regard to letter case like the other names.
- `src/ai_mod_painter/ui/layers_panel.py`: new `toggle_visible(key) -> bool`. It flips
  the eye of that row, through the same path as a click on the eye, so the picture is
  redrawn and the preset combo switches to Custom exactly as after a click. It returns
  `False` when the panel has no such row.
- `src/ai_mod_painter/ui/main_window.py`:
  - new method `toggle_aircraft_layer()`. It does nothing when no animation is loaded
    or when the frame shown now has no `render_aircraft.png`
    (`AIRCRAFT_LAYER not in frame.files`). That check also covers an animation without
    the layer. Otherwise it calls `self.layers.toggle_visible(AIRCRAFT_LAYER)`;
  - `_key_action` maps Ctrl+Space to it. Like today, Ctrl+Space works wherever the
    focus is in the window, text fields included, and never starts Play;
  - remove `_add_from_key`.
- The eye state then stays as it is for the next frames and animations, like any eye
  click. It is not reset when the frame changes.

### 2. render-photo.png above render.png — `src/ai_mod_painter/core/layer_presets.py`

- `PHOTO_LAYER` moves from `core/prompt_queue.py` to `core/layer_presets.py`, and
  `prompt_queue.py` imports it from there like `RENDER_LAYER` (the other way round
  would be a circular import). The test that it equals the queue's destination name
  stays.
- `default_preset`: bottom first, `render_scene.png`, then `render.png`, then
  **`render-photo.png`**, then every other layer as today. Without `render.png` it goes
  just above the scene layer, or to the bottom.
- Its flags stay as they are today: eye on (visible, as you confirmed), R off.
- `keep_states` needs no change. A layer that is new to the current set-up goes right
  above the nearest layer below it in the preset. So when the next animation is the
  first one with `render-photo.png`, the layer lands right above `render.png`.
- Update the module docstring list (1. scene, 2. render, 3. render-photo,
  4. the rest).

### 3. Tests

- `tests/test_layer_presets.py`:
  - `render-photo.png` comes right after `render.png` (bottom first), also when
    aircraft layers and other layers are present;
  - without `render.png` it sits above `render_scene.png`;
  - the flags are eye on and R off;
  - names are compared without regard to letter case.
- `tests/test_main_window.py`:
  - A approves (green) and moves to the next row;
  - D marks (red) and moves to the next row;
  - A on a red row turns it green (mark removed, approval written) and moves;
  - D on a green row turns it red (approval taken back, mark set) and moves;
  - A on a green row and D on a red row turn it grey (plain) and move;
  - S approves, queues the file for the frame selected in the *first* animation,
    then selects the next one;
  - S without `render.png` and S without prompts approve and move;
  - S while the animation is still loading neither approves nor moves;
  - A, S and D on the last animation of the last page keep the selection;
  - A, S and D on the last row of a page go to page 2;
  - the thumb and trash buttons do not move the selection;
  - Ctrl+Space hides a visible `render_aircraft.png` and shows it again on the second
    press, the picture changes, and no queue file is written;
  - Ctrl+Space does nothing on a frame without `render_aircraft.png`, in an animation
    whose other frames have it, and in an animation without it; other layers stay
    as they are;
  - Ctrl+Space with the focus in a text field still toggles and does not start Play.
- `test_ctrl_space_adds_the_prompt` is replaced by those tests.
- New `tests/test_layers_panel.py`: `toggle_visible` flips the eye, emits `changed`,
  switches to Custom, and returns `False` for an unknown key.
- Existing A, S and D tests that check the selection afterwards get updated.

### 4. Docs and checks

- `README.md`:
  - key table: A, S and D each end with "… then the next animation";
  - Ctrl+Space: "Show / hide `render_aircraft.png` (nothing when the frame has no
    such image)". The note that Watch Me Recorder also uses Ctrl+Space while it runs
    stays;
  - Prompt queue section: Add is the button (and S), no longer Ctrl+Space;
  - Layers / Default preset description: `render-photo.png` right above `render.png`;
  - add `implementation-plan-7.md` to the list of plans.
- Run `uv run ruff check`, `uv run ruff format --check` and `uv run pytest`.
- Visual check on the real render folder, in memory only, without pressing A, S or D
  there, so that nothing is written:
  - in a screenshot, the Layers list shows `render-photo.png` directly above
    `render.png`;
  - the A, S and D movement is covered by the tests on a temporary tree.

## Risks and assumptions

- Opening another animation always applies Default again, so the new order shows on
  the next animation opened after a restart. (Found while implementing: the risk in
  the earlier drafts, that a running window keeps the old order, does not apply.)
- With `render-photo.png` visible and directly above `render.png`, it covers
  `render.png` exactly as it does today. Only its position against the aircraft mask
  layers changes.
- **A mistaken key press moves on.** To undo one, press ↑ and the same key again (it
  toggles), which then moves down once more.
- After S moves on, the status line still shows "Queued … as <hash>.md" for the
  animation just approved. The new animation's frame and prompt combo do not change
  that message.
- Moving down after S loads the next animation in the background. With Photo pressed,
  it opens at its first photo frame (plan 5) as with ↓.
- **Adding a chosen prompt from the keyboard goes away.** After the change, only the
  **Add** button adds the prompt picked in the combo; S adds a random one.
- While Watch Me Recorder runs, its Draw shortcut is also Ctrl+Space, so the two can
  clash during a recording, as today.
- "In the animation or in the frame" is read as: the frame shown now must contain
  `render_aircraft.png`. When only some frames have it, Ctrl+Space works on those
  frames and does nothing on the others.
- I read "render foto" as the layer `render-photo.png`, which was on screen at 0:49
  (arrow #1 points at it).

## Open questions

None left.

Answered in chat: `render-photo.png` stays visible in Default; S moves down after
approving, also when it then shows an error (draft 2); Ctrl+Space shows or hides
`render_aircraft.png` (draft 3); A on a red row turns it green and D on a green row
turns it red, then the focus moves down (draft 4); A on a green row and D on a red
row turn it grey, then the focus moves down (draft 5).
