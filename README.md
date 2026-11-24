# AI Mod Painter

A desktop viewer for rendered animation frames that are made of several image layers.
Pick a folder of animations, choose an animation, and scrub or play its frames. The
layers can be reordered, hidden or turned into a red mask, and the image zooms from
1/64× to 64×.

Python 3.12–3.13 and PySide6 (Qt 6). It runs on Windows, macOS and Linux.

## Run

You need [uv](https://docs.astral.sh/uv/).

The simplest way:

- **Windows:** double-click `start.bat`. You can also run `start.bat D:\path\to\render`.
- **macOS / Linux:** run `./start.sh` or `./start.sh /path/to/render`.

Both scripts prepare the Python environment on the first start (`uv sync --locked`), then
open the app. Without a folder argument the app opens the last folder. On Windows the
app runs without a console window, and the start window closes on its own.

From a terminal:

```
uv sync
uv run ai-mod-painter                       # opens the last folder
uv run ai-mod-painter D:\path\to\render     # opens this folder
```

`scripts\launch.bat` and `scripts/launch.sh` are thin `uv run` wrappers for the same
command.

## Expected folder shape

```
<root>/                      the folder you open
  <animation>/               every subfolder of the root is an animation
    <frame>/                 every subfolder of an animation is a frame
      <layer>.png|.jpg|.jpeg every image file is a layer
```

- No names are fixed. Folders are sorted naturally (`frame2` before `frame10`), and the
  folder names are only shown as labels.
- Files that are not images (for example `scene.json` or `animation.json`) are ignored.
  A frame folder without images is skipped.
- A layer is identified by its file name, without regard to letter case. A layer that
  is missing from a frame is simply not drawn in that frame.
- The app writes one file of its own into an animation folder: `ai-mod-config.json`,
  a small log (see [Review log](#review-log)).

## Using it

| Where | What |
|---|---|
| Left panel | A path box and a **…** button to choose the folder. Animations are listed 100 per page, with **‹ ›** to change pages. Rows are gray; the **thumbs-up** near the end of a row approves the animation (green row, `ai-mod-config.json` is written; click again to take it back), the **trash**, the last icon, marks it for deletion (red row, nothing is deleted yet). The last one wins: marking an approved row takes the approval back, approving a marked row removes the mark. **Reload** lists the folder again, clears the deletion marks and goes to page 1. **Delete Selected** asks once more and then deletes the marked animation folders **permanently** (no Recycle Bin). |
| Bar above the image | **◧ / ◨** show or hide the side panels. **▶ / ■** plays the frames in a loop at 10 fps until Stop. The slider and its label show the current frame. On the right, the prompt combo and **Add** put a prompt into the queue (see below). |
| Image | Mouse wheel zooms (1/64×–64×) around the cursor. Drag with the left or middle button to pan. |
| Right panel | Layers, with the top row drawn on top. The combo next to the title shows **Default** or **Custom** (see below). Drag a row to reorder. The **eye** shows or hides a layer, and **R** draws its opaque pixels red with their alpha kept, which works as a mask. Rows dim when the layer is missing from the current frame. |
| Status line | The canvas size (from the bottom-most layer), the zoom, and the pixel under the cursor (`x,y #RRGGBBAA`). |

Defaults and rules:

- **Default layer set-up:** every animation opens in **Default**:
  `render_scene.png` at the bottom (eye off), `render.png` above it (eye on), and all
  other layers above, ordered by the number of frames they are in (most at the bottom,
  ties by name); a layer with `aircraft` in its name gets **R** on and the eye off.
  Without these names the layers simply follow the frame-count order, all visible.
- **Custom:** any change of the eye, R or the order switches the combo to Custom.
  Choosing Default applies the preset again. Opening another animation always returns
  to Default; F5 and Reload keep the set-up of the open animation.
- **Canvas size:** the bottom-most layer present in a frame gives the size. Other
  layers are stretched to it.
- **Switching animations:** playback keeps running, and the frame number stays when
  the new animation has that many frames; otherwise it starts at the first frame.

### Prompt queue

The combo on the right of the bar lists the templates in `assets/prompts/*.md` (file
names without `.md`). **Add** is enabled when the current frame has `render.png`. It
takes the chosen template, replaces `{SOURCE_IMAGE}` with the absolute path of that
`render.png` and `{DESTINATION_IMAGE}` with `render-photo.png` in the same folder, and
writes the result to `prompt_queue/<hash>.md` in this repository. The hash is the
first 16 hex characters of the SHA-256 of `<absolute render.png path>,<absolute
template path>`, so the same frame with the same prompt always gets the same file, and
adding it again replaces it. Every Add is also recorded in the review log. Another
program processes the queue; the app only fills it.

### Review log

`ai-mod-config.json` in the animation folder (times are local, with the UTC offset):

```json
{
  "approved": true,
  "approved_changed_at": "2026-11-24T06:35:12+01:00",
  "prompts": [
    {"prompt": "convert_autumn.md", "frame": "frame3",
     "queued_at": "2026-11-24T06:36:40+01:00", "queue_file": "3f9a0c1d2e4b5a67.md"}
  ]
}
```

`approved_changed_at` changes with every approve and un-approve; `prompts` gets one
entry per Add. Other keys in the file are kept.

### Shortcuts

| Key | Action |
|---|---|
| Space | Play / Stop |
| ↑ / ↓ | Previous / next animation (across pages; stops at the first and the last) |
| ← / → or `,` / `.` | Previous / next frame (wraps around) |
| A | Thumbs-up of the selected animation |
| D | Trash of the selected animation |
| Ctrl+Space | Add the prompt to the queue (Watch Me Recorder also uses Ctrl+Space while it runs) |
| F | Zoom to fit |
| 1 | 100 % |
| F5 | Reload (new animations, frames, files and prompts; keeps the page and the deletion marks) |
| Ctrl+O | Open folder |

The arrows, A, D and Ctrl+Space work wherever the focus is in the window; only the path
box keeps the arrows and letters for typing.

## Development

```
uv run pytest
uv run ruff check
uv run ruff format --check
```

The source is in `src/ai_mod_painter`:

- `core/` holds the folder model, the layer state, the Default layer preset, the
  review file and deletion, the prompt queue, the compositor and the image cache.
- `ui/` holds the widgets.

The design and the decisions behind it are in `implementation-plan.md`,
`implementation-plan-2.md` and `implementation-plan-3.md`.
