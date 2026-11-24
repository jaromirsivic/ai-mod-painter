# Implementation plan 4: prompt marks on the frame slider

Source: Watch Me recording `20261124-065248` (2:10, Czech, whole range; instructions:
"implementation plan in English, do not implement yet, wait for approval"). Answers to
the open questions of draft 1 in chat (2026-11-24): the mark is a short vertical line;
colors are assigned from the palette in alphabetical order of the templates (shifting
when templates are added or removed is fine); the slider may be up to 400 px wide.
Status: **draft 2, approved and implemented 2026-11-24.**

## Goal

1. **Prompt marks above the frame slider:** every frame for which a prompt was added
   (Add or Ctrl+Space) gets a clearly visible short vertical line, at least 2 px thick,
   right above its position on the slider. When a frame has several prompts, the color of the **last**
   one wins.
2. **A color per prompt template:** each of the 9 templates in `assets/prompts` gets
   its own color. The first seven are the Watch Me drawing palette; the rest are new
   colors; never white or black.
3. **Repeated Add** for the same frame and prompt writes the same hashed file in
   `prompt_queue/` again. You confirmed at 1:55 that this is what you want: **no change.**

## Steps

### 1. Prompt colors — new `src/ai_mod_painter/core/prompt_colors.py`

- `PROMPT_PALETTE` (12 colors, none white or black):

  | # | Color | Hex | Source |
  |---|---|---|---|
  | 1 | Red | `#FF0000` | Watch Me palette |
  | 2 | Orange | `#FF8C00` | Watch Me palette |
  | 3 | Yellow | `#FFFF00` | Watch Me palette |
  | 4 | Green | `#00C000` | Watch Me palette |
  | 5 | Cyan | `#00E5FF` | Watch Me palette |
  | 6 | Blue | `#0055FF` | Watch Me palette |
  | 7 | Magenta | `#FF00FF` | Watch Me palette |
  | 8 | Purple | `#8A2BE2` | new |
  | 9 | Lime | `#9AFF3C` | new |
  | 10 | Pink | `#FF7FB0` | new |
  | 11 | Brown | `#A0522D` | new |
  | 12 | Teal | `#00A08A` | new |

- `prompt_color(name, prompts) -> QColor`: the color of a template is given by its
  position in the alphabetically (naturally) sorted list of `assets/prompts/*.md`;
  adding or removing a template shifts the colors after it, which is accepted
  (today: `convert` red,
  `convert_autumn` orange, … `convert_winter_no_snow` lime). More than 12 templates
  start the palette again. A template that is no longer in the folder (only in an old
  log entry) is drawn **gray**.
- The prompt combo shows a small square of the color in front of each name, so you can
  see which color means which prompt.
- **Verify:** `tests/test_prompt_colors.py` — the first seven equal the Watch Me
  palette, no white or black, the order follows the sorted names, unknown → gray.

### 2. Marks per frame — `core/review.py`

- `prompt_marks(folder) -> dict[str, str]`: frame name → prompt file name of the
  **last** entry for that frame in `prompts` of `ai-mod-config.json` (the log is in
  time order, so the last entry wins). Broken or missing entries are skipped.
- The log is the source, so the marks are there again after a restart or when you come
  back to the animation.
- **Verify:** `tests/test_review.py` — two entries for one frame → the later prompt;
  missing file → no marks.

### 3. Slider with marks — `ui/master_bar.py`

- `MarkedSlider(QSlider)`: draws the slider as today and, above the groove, one short
  **vertical line** per marked frame in its color, centred on the frame's position (the
  same x the handle centre takes for that frame, from `QStyle.sliderPositionFromValue`
  and the groove rectangle). The line is **3 px wide and 8 px tall**, with round caps,
  ending just above the handle. The slider gets a few pixels of extra height so the
  lines never touch the handle.
- The slider may now grow to **400 px** (`SLIDER_MAX_WIDTH` 200 → 400); it still
  shrinks when the window is narrow.
- `MasterBar.set_marks(dict[int, QColor])` (frame index → color).
- **Verify:** a widget test that grabs the slider image and finds the mark color above
  the position of the marked frame and not above an unmarked one.

### 4. Wiring — `ui/main_window.py`

- After an animation is opened or rescanned (F5, Reload) read `prompt_marks` of its
  folder, map frame names to indexes and set the marks.
- After a successful **Add** (button or Ctrl+Space) update the mark of the current
  frame at once (the color of the prompt just added).
- When the prompt list is reloaded, recompute the colors.
- **Verify:** main-window test: Add on frame 0 with prompt A, then with prompt B →
  frame 0 has B's color; reopening the animation shows the same mark; a frame without
  prompts has none.

### 5. Docs and checks

- README: the marks and the color of each prompt.
- `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`; then a manual run.

## Risks

- **Color by position in the list** changes the colors of the following templates when
  a template is added or renamed (old marks then take the new color of their name);
  accepted.
- At 400 px the frame step is under 4 px from about 100 frames on; then the 3 px lines
  of neighbouring frames start to touch.
- Yellow, lime and cyan are bright on the light parts of a light theme; the app runs
  dark here, so they read well.

## Notes

- The app window in the recording still shows the trash left of the thumbs-up: that
  instance was started before plan 3 was committed. Restart it to get the plan 3
  changes (keys, icon order, the log, hashed names).
