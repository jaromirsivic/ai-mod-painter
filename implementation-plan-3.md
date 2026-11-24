# Implementation plan 3: keyboard control, icon order, review log, hashed queue names

Source: Watch Me recording `20261124-063236` (6:17, Czech, whole range; instructions:
"implementation plan in English, do not implement yet, wait for approval"). Answers to
the open questions of draft 1 in chat (2026-11-24): ↑ / ↓ cross pages but stop at the
very first / last animation (no wrap-around); the JSON key is `approved_changed_at`;
A and D are switches and the last one pressed wins; Add stays on Ctrl+Space only.
Status: **draft 2, approved and implemented 2026-11-24.**

## Goal

1. **Keyboard control whenever the app has focus:** ↑ / ↓ move through the animation
   list, ← / → step through the frames (wrapping at both ends), **A** = thumbs-up of the
   selected row, **D** = trash of the selected row, **Ctrl+Space** = the **Add** button.
2. **Icon order:** thumbs-up first, the trash as the very last item of the row.
3. **`ai-mod-config.json` becomes a log:** approval records the time of the change;
   every Add records the prompt file name (with `.md`), the date and time and the frame.
4. **Queue file name:** `<first 16 hex chars of SHA-256>.md` instead of
   `prompt-YYYY-MM-DD-HH-MM-SS.md`; the hash is computed from
   `<absolute path of render.png>,<absolute path of the prompt .md>`.

How I read some words: "na význam" (0:17) = "na výběr"/anywhere in the app — the
sentence goes on "kdykoliv … ta aplikace má fokus", so: whenever the window has focus.
"zapíše do souboru … nový JSON" (2:34) = the existing `ai-mod-config.json` (you named it
right after). At 5:26 you first said a third comma-separated item would follow, then
"Ne, pak už tam nic nebude" — so the hash input has exactly two parts.

## Steps

### 1. Window-wide keys — `ui/main_window.py`

- One application event filter (installed by `MainWindow`) handles the keys before the
  focused widget does, so they work whether the focus is in the animation list, the
  layers list, a combo box or on a button:

  | Key | Action |
  |---|---|
  | ↑ / ↓ | previous / next animation in the list (opens it, as a click does) |
  | ← / → | previous / next frame; from the first frame ← goes to the last, from the last → goes to the first (what `,` / `.` do today, they stay) |
  | A | the thumbs-up of the selected animation (exactly like clicking it, see step 2) |
  | D | the trash of the selected animation (exactly like clicking it, see step 2) |
  | Ctrl+Space | Add (only when Add is enabled) |

- Exceptions, so normal typing keeps working: while the **path box** has focus, the
  arrows and A / D go to the text field (Enter or Esc leaves it); while a **combo
  popup** is open or a **dialog** (Delete Selected confirmation, folder picker) is
  active, nothing is intercepted. Ctrl+Space is intercepted everywhere in the window.
- ↑ / ↓ at the page edge: ↓ on the last row goes to the first row of the next page,
  ↑ on the first row to the last row of the previous page. On the very last animation
  ↓ does nothing, on the very first ↑ does nothing (no wrap-around).
- With no animation selected, ↓ selects the first row of the page, ↑ the last.
- New panel methods used by the filter: `AnimationPanel.select_next(delta)`,
  `toggle_approved_selected()`, `toggle_marked_selected()`.
- README shortcut table updated.
- **Verify:** main-window tests sending key events with focus on the animation list,
  the layers list and a combo: ↓/↑ change the open animation, cross pages and stop at
  the first / last animation; ←/→ wrap; A and D follow step 2; Ctrl+Space writes a
  queue file; with focus in the path box ← / A only edit the text.

### 2. Icon order and "the last one wins" — `ui/animation_panel.py`

- Swap `thumb_rect` / `trash_rect`: the trash sits at the right edge, the thumbs-up
  left of it.
- Both icons (and A / D) are switches, and the last one pressed wins:

  | Row before | A / thumbs-up | D / trash |
  |---|---|---|
  | gray | green (approved) | red (marked) |
  | green | gray (un-approved) | red: marked **and** un-approved |
  | red | green: approved, mark removed | gray (mark removed) |

  Every change of the approval is written to `ai-mod-config.json` with its time
  (step 3), also the un-approve caused by D. The deletion mark stays in memory.
  This changes today's trash click, which leaves the approval as it is.
- **Verify:** the sequences A, A → gray; A, D → red and the file says
  `"approved": false`; A, D, A → green, not marked; D, D → gray. A test that
  `trash_rect(row).left() > thumb_rect(row).left()`.

### 3. `ai-mod-config.json` as a log — `core/review.py`, `core/prompt_queue.py`, `ui/main_window.py`

New structure (unknown keys are still kept):

```json
{
  "approved": true,
  "approved_changed_at": "2026-11-24T06:35:12+01:00",
  "prompts": [
    {
      "prompt": "convert_autumn.md",
      "frame": "frame3",
      "queued_at": "2026-11-24T06:36:40+01:00",
      "queue_file": "3f9a0c1d2e4b5a67.md"
    }
  ]
}
```

- Times are local ISO 8601 with the UTC offset, to the second.
- `write_approved(folder, approved, now)` also writes `approved_changed_at` (updated on
  approve **and** un-approve, i.e. "when the user clicked the thumbs-up").
- New `append_prompt_record(folder, prompt_name, frame_name, queue_file, now)` appends
  to `prompts` (a history: every Add adds one entry). Same atomic write as today.
- `MainWindow.add_prompt`: write the queue file first, then the log entry. If the log
  cannot be written, the queue file stays and the status line says the log failed.
- `frame` is the frame folder name (universal; no file names assumed).
- **Verify:** `tests/test_review.py` — the timestamp on approve/un-approve (fixed
  `now`), appending two prompt records, other keys kept; main-window test that Add
  writes the record into the animation folder.

### 4. Hashed queue file name — `core/prompt_queue.py`

- `queue_file_name(source, template) -> str`:
  `sha256(f"{source},{template}".encode("utf-8")).hexdigest()[:16] + ".md"`, where
  `source` is the absolute path of `render.png` exactly as written into
  `{SOURCE_IMAGE}` (`os.path.abspath`, Windows backslashes) and `template` is the
  absolute path of the prompt `.md` (`os.path.abspath` of the file in
  `assets/prompts`). No spaces around the comma, no third part.
- The timestamp name and the `-2`, `-3` suffixes are removed. The same render.png with
  the same prompt always gives the same name, so a second Add **overwrites** that
  queue file (atomic replace) instead of creating a duplicate.
- **Verify:** `tests/test_prompt_queue.py` — the name equals a hash computed in the
  test from the two path strings; the same pair twice gives one file; another prompt
  or another frame gives another name.

### 5. Docs and checks

- README: shortcuts, icon order, the log fields in `ai-mod-config.json`, the queue file
  name. `implementation-plan-2.md` stays as the record of the previous step.
- `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`; then a manual run
  on the render folder: arrows, A / D, Ctrl+Space, check the JSON and the queue file.

## Risks

- **Ctrl+Space is Watch Me Recorder's global Draw hotkey.** While Watch Me runs, it
  probably takes Ctrl+Space before AI Mod Painter sees it (and on some Windows set-ups
  Ctrl+Space switches the input method). You chose to keep Ctrl+Space only; the Add
  button always works.
- Holding ↓ scans one animation after another; the scan token already drops stale
  results, so only the last one is shown, but the disk is read for each.
- Catching the arrows window-wide takes them away from the layers list and the combo
  boxes (they stay usable with the mouse).
- With the hash name, re-adding the same prompt for the same frame replaces the queue
  file; if the consumer already processed the first one, the second Add queues it again.
- The log grows with every Add (small entries; no limit planned).
