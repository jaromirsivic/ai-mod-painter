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

## Using it

| Where | What |
|---|---|
| Left panel | A path box and a **…** button to choose the folder. Animations are listed 100 per page, with **‹ ›** to change pages. |
| Bar above the image | **◧ / ◨** show or hide the side panels. **▶ / ■** plays the frames in a loop at 10 fps until Stop. The slider and its label show the current frame. |
| Image | Mouse wheel zooms (1/64×–64×) around the cursor. Drag with the left or middle button to pan. |
| Right panel | Layers, with the top row drawn on top. Drag a row to reorder. The **eye** shows or hides a layer, and **R** draws its opaque pixels red with their alpha kept, which works as a mask. Rows dim when the layer is missing from the current frame. |
| Status line | The canvas size (from the bottom-most layer), the zoom, and the pixel under the cursor (`x,y #RRGGBBAA`). |

Defaults and rules:

- **Default layer order:** the layer present in the most frames goes to the bottom,
  and ties are ordered by name.
- **Canvas size:** the bottom-most layer present in a frame gives the size. Other
  layers are stretched to it.
- **Carry-over:** the layer set-up (order, eye, R) carries over to the next animation
  with the same layer names. It is kept in memory only.

### Shortcuts

| Key | Action |
|---|---|
| Space | Play / Stop |
| `,` / `.` | Previous / next frame |
| F | Zoom to fit |
| 1 | 100 % |
| F5 | Reload (new animations, frames and files) |
| Ctrl+O | Open folder |

## Development

```
uv run pytest
uv run ruff check
uv run ruff format --check
```

The source is in `src/ai_mod_painter`:

- `core/` holds the folder model, the layer state, the compositor and the image cache.
- `ui/` holds the widgets.

The design and the decisions behind it are in `implementation-plan.md`.
