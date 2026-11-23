# Implementation plan: AI Mod Painter (frame and layer viewer)

Source: Watch Me recording `20261123-234042` (9:38, Czech, whole range, instructions
"implementation plan in English, do not implement yet"). Follow-ups in chat (2026-11-24):
the example root folder `D:\git\airplane-models-custom-engine\Output\render`, and
"it is only an example, other folders will have a similar subfolder structure and
differently named images; make it universal". Answers to the open questions of draft 2
(2026-11-24): layers present in most frames go to the bottom; frames without images are
skipped; animations are sorted ascending; layer state carries over to the next animation;
zoom goes from 1/64× to 64×; playback at a fixed 10 fps loops until Stop; the status line
shows size, zoom and the pixel under the cursor; the name is AI Mod Painter, run with
`uv run`, no installer.
Status: **draft 3, approved and implemented 2026-11-24.** Beyond the plan, the
implementation adds the shortcuts `,` / `.` (previous / next frame), F (fit) and 1
(100 %), an optional root folder argument (`ai-mod-painter <folder>`), and the
`ai-mod-painter-gui` entry point (no console window on Windows). Checked on the example
folder: 501 animations listed in 6 ms; the first frame shows 70 ms after a click;
playback runs at 10.0 fps after the first loop; composing a cached frame takes 4 ms; one
animation uses 246 MiB of cache.

## Goal

A new desktop application in this repository (`ai-mod-painter`), the "smart drawing
board". In practice it is a viewer and compositor for animation frames:

- The user picks a **root folder**. It holds many (hundreds to thousands of)
  **animation folders**. Each animation folder holds **frame folders**. Each frame folder
  holds **images** (PNG and JPG).
- Each distinct image file name in an animation becomes a **layer**. The user orders the
  layers, hides them, or turns one into a red mask. A **slider** scrubs through the frames
  (or **plays** them in a loop at 10 fps), and the main area shows the composited frame,
  with zoom from 1/64× to 64×.
- **Universal**: nothing depends on the folder or image names of the example. Any root →
  animation → frame → image tree with this shape works. Only the shape and the image
  extensions matter.
- Tech stack: the same as Watch Me Recorder / Video Editor. That means Python 3.12–3.13,
  **PySide6 (Qt 6)**, `uv` + `uv.lock`, hatchling, a `src/` layout, pytest + pytest-qt and
  ruff. It is developed on Windows first and must also run on macOS and Linux.

### What the example folder shows (surveyed 2026-11-24, 50 of 501 animations sampled)

```
render/                                   root: 501 animation folders, no files
  2026-11-23-16-46-32/                    animation folder (timestamp name)
    animation.json                        animation-level file -> ignored
    frame0/ … frame29/                    frame folders: "frame" + number, no space
      render.png                          images = layers (all PNG, 1672x941 RGBA,
      render_aircraft.png                 ~130 KB each, ~6.3 MB decoded)
      render_scene.png                    (only in frame0)
      aircraft_aircraft-01_sun.png
      aircraft_aircraft-04_sun.png
      scene.json                          non-image file -> ignored
```

Facts that shape the plan:

- **Frames without images exist.** In the sampled animations only `frame0` to `frame9`
  hold PNGs, and `frame10` to `frame29` hold only `scene.json`. One animation
  (`2026-11-23-15-49-16`) has a single, empty `frame0`.
- **Layers differ between frames.** `render_scene.png` is only in `frame0`, and the
  `aircraft_*` names differ per animation.
- **Natural sort is required.** Plain text sorting puts `frame10` before `frame2`.
- Each frame folder and the animation folder also hold JSON metadata (`scene.json`,
  `animation.json`). They are ignored, because other folders may not have them.

### Layout (from the sketch, 0:49–4:20)

```
+------------------------------------------------------------------+
| Menu bar                                                         |
+-------------+--------------------------------------+-------------+
| [path...][…]| [▶] [===slider===]  frame3  (4 / 10) |  Layers     |
|-------------+--------------------------------------|  👁 R render.png
| animation 1 |                                      |  👁 R object1.png
| animation 2 |          main image area             |  👁 R object2.png
| animation 3 |          (zoom 1/64x .. 64x)         |             |
| ...         |                                      |             |
| (100/page)  |                                      |             |
|-------------+--------------------------------------|             |
| < 1 / 6 >   | 1672 x 941 | 125 % | 812,440 #FF8800FF|             |
+-------------+--------------------------------------+-------------+
  collapsible                                          collapsible
```

## Steps

### 1. Project scaffold

- What changes: add `pyproject.toml` (copied from the Watch Me pattern: `requires-python
  >=3.12,<3.14`, dependency `pyside6-essentials>=6.8,<7`, dev group `pytest`,
  `pytest-qt`, `ruff`, ruff config line-length 100), `uv.lock`, and
  `src/ai_mod_painter/{__init__,__main__,app}.py` with entry point
  `ai-mod-painter = "ai_mod_painter.app:main"`. Also `README.md`, `.gitignore`, `tests/`,
  a `CLAUDE.md` with the "no backward compatibility" rule (as in Watch Me), and launcher
  scripts `scripts/launch.bat` / `scripts/launch.sh` (a simple `uv run` wrapper; the
  full Watch Me bootstrap and JSON error contract are not needed).
- Verify: `uv sync`, `uv run ai-mod-painter` opens an empty main window,
  `uv run pytest` and `uv run ruff check` pass.

### 2. Folder model (pure Python, no Qt), universal

Module `core/library.py`. The rules are generic and do not depend on any name:

- **Animations**: every direct subfolder of the root, sorted naturally **ascending**
  (timestamps: oldest first; `os.scandir` only, no recursion, no look inside). Files in the root are ignored.
  `page(items, index, size=100)` handles pagination.
- **Frames**: every direct subfolder of an animation folder, sorted naturally
  (`natural_key` splits the name into text and numbers: `frame2` < `frame10`,
  `f_9` < `f_10`). No `frame` prefix is required, and any name works. The folder name is
  shown as the frame label. Files directly in the animation folder (`animation.json`)
  are ignored. Deeper subfolders are not searched.
- **Images**: files in a frame folder with the extension `.png`, `.jpg` or `.jpeg`
  (case-insensitive). Everything else (`scene.json`, …) is ignored.
  `IMAGE_EXTENSIONS` is a single constant, so adding `.webp`/`.bmp` later is a one-line
  change (Qt reads them).
- **Frames without images are skipped**: a frame folder with no image (in the example
  `frame10`…`frame29`, which hold only `scene.json`) is not part of the animation. An
  animation whose frames are all empty has no frames.
- **Layers**: a layer is identified by the **file name**, compared case-insensitively.
  The layer list is the union over all frames. The **default order** (bottom → top) is
  by the **number of frames that contain the layer, most frequent at the bottom**, with
  ties broken by natural sort of the name. In the example the layers present in all 10
  frames (`aircraft_aircraft-01_sun.png`, `aircraft_aircraft-04_sun.png`, `render.png`,
  `render_aircraft.png`) come first, and `render_scene.png` (1 frame) goes on top. The
  most frequent layer at the bottom also gives the canvas size in most frames.
  The user can reorder.
- `scan_animation(folder) -> Animation(frames, layers)`, where
  `frames: list[Frame(name, path, files: dict[layer_key, Path])]` and each layer
  carries its frame count. A layer missing from a frame is simply not drawn in that
  frame.
- Verify: unit tests on `tmp_path` trees:
  - a copy of the example's shape: `frame0`…`frame29`, images only in 0–9, JSON files
    everywhere, a layer only in `frame0` (expected: 10 frames, `render_scene.png` on
    top);
  - the default layer order: by frame count, then by name;
  - a tree with completely different names (`shot_01/a.jpg`, `shot_02/b.PNG`, …);
  - natural sort (`frame2` before `frame10`);
  - 250 animations split into 3 pages;
  - an animation with one empty frame;
  - an animation with no subfolders;
  - an unreadable folder.

### 3. Compositor (Qt `QImage`, testable headless)

Module `core/compositor.py`:
`compose(frame, layer_states, cache) -> QImage | None`.

- `layer_states` is an ordered list of `LayerState(key, visible, red)`, bottom first.
- The **bottom-most layer defines the canvas size** (4:12–4:27). Every other image is
  scaled to that size with no aspect ratio kept ("stretch",
  `Qt.IgnoreAspectRatio`, smooth). If the bottom layer is not present in the current
  frame, the bottom-most layer that is present gives the size.
- Layers are drawn bottom → top with `CompositionMode_SourceOver`, so PNG alpha stacks
  and an opaque image (JPG) covers everything below it.
- **Red** (8:05–8:30): the image is copied, then filled with red using
  `CompositionMode_SourceIn`. Opaque pixels turn red, transparent pixels stay
  transparent, and partial alpha is kept. This makes a mask. A JPG turns fully red.
- Hidden layers are skipped. When every layer of the frame is hidden, the canvas stays
  at its size and is empty.
- Verify: tests with tiny synthetic images (2×2 / 4×4). Cover stacking order, an
  opaque top layer covering the rest, the red mask keeping alpha, stretching to the
  bottom layer's size, a missing bottom layer, and all layers hidden.

### 4. Image cache and background loading

Module `core/image_cache.py`:

- An LRU cache of decoded `QImage`s with a **memory cap** (default 1.5 GB, a constant).
  For scale, one example animation is about 30 frames × 4–5 layers × 6.3 MB ≈ 0.9 GB
  decoded, and images of other folders may be larger. Images are decoded on a
  `QThreadPool` worker.
- When a frame is shown, the current frame is loaded first, then its neighbours
  (±N frames), so dragging the slider stays smooth. During playback the prefetch looks
  ahead in the play direction and wraps around to the first frame. A late result for a
  frame that is no longer current is dropped.
- Image sizes come from `QImageReader.size()` (no decoding) for the status bar.
- Verify: unit tests for LRU eviction by size; a manual test of scrubbing an example
  animation from `Output\render` while watching memory in Task Manager.

### 5. Main window and collapsible panels

Module `ui/main_window.py`:

- `QMainWindow` with a **menu bar** across the full width:
  - File: Open folder…, Exit
  - View: Show controls panel, Show layers panel (both checkable), Zoom to fit, 100 %
- The central widget is a horizontal `QSplitter` with the **left controls panel**, the
  **centre** (master bar / image view / status line) and the **right layers panel**.
  - Both side panels can be hidden: from the View menu, with small toggle buttons on the
    inner edge of each panel, and by collapsing the splitter. Sizes and visibility are
    kept in `QSettings`.
- The centre's status line sits **under the image only**, as in the sketch, not across
  the full window.
- Verify: a pytest-qt test that toggles each panel, plus a manual check of the layout
  against the sketch.

### 6. Left panel: folder picker, animation list, pagination

- At the top, a `QLineEdit` path box and a small "…" button that opens
  `QFileDialog.getExistingDirectory`. Pressing Enter in the box, or choosing a folder,
  loads the root. An invalid path shows an error in the status line.
- In the middle, a `QListView` with one row per animation folder (current page only,
  **max 100 rows**). The example root has 501 animations, which makes 6 pages.
- At the bottom, a pager: `‹  page 1 / 6  ›` plus a total count.
- Clicking a row runs `scan_animation` on a worker, then fills the layers panel and the
  slider and shows the first frame. An animation with no images at all shows "No images
  in this animation" in the image area, with the slider and Play disabled. Switching to
  another animation stops playback.
- The last root folder is remembered in `QSettings`.
- Verify: a pytest-qt test with a generated tree of 250 animations (3 pages, page
  switching); a manual run on `D:\git\airplane-models-custom-engine\Output\render`.

### 7. Master bar: frame slider and playback

- A horizontal `QSlider` over the frames that have images (empty frame folders are
  skipped, step 2), range `0 .. frames-1`, **at most 200 px wide** (frames are expected
  to be ≤ 100, typically far fewer). Next to it is the label with the frame folder name
  and position, for example `frame3  (4 / 10)`.
- Moving the slider (dragging, clicking, or the arrow keys Qt provides) changes the
  shown frame at once, using cached images when it can. The view keeps its zoom and
  position between frames.
- **Playback**: a **Play / Stop** button left of the slider (and the Space key). Play
  advances one frame every 100 ms (**fixed 10 fps**, a `QTimer`) and **loops** from the
  last frame back to the first **until the user presses Stop**. The slider follows the
  playing frame. Dragging the slider while playing moves the position, and playback
  continues from there after release. Playback stops only with Stop, or when another
  animation or root folder is opened.
- If the next frame is not decoded yet, the current frame stays on screen until it is
  ready; frames are never skipped. The first loop of a heavy animation can therefore run
  slower than 10 fps, and later loops come from the cache.
- Verify: pytest-qt tests that moving the slider changes the composed frame, and that
  playback (with a fake timer) advances, wraps from the last frame to the first, and
  stops on Stop and on switching the animation. A manual check on an example animation
  that playback is smooth after the first loop.

### 8. Image view with zoom

`ui/image_view.py` (`QGraphicsView` with one pixmap item, or a custom `QWidget`):

- **Mouse wheel zoom**, anchored at the cursor, in steps of ×2^(1/4). The range is
  **1/64× to 64×** (9:11–9:29).
- When zoomed in, pixels are drawn with nearest-neighbour sampling (no smoothing) so
  they can be inspected. When zoomed out, smooth sampling is used.
- Panning works by dragging with the left or middle mouse button. The first image of an
  animation is fit to the window. The zoom is kept when the frame changes.
- Verify: unit tests of the zoom clamp; a manual check that 64× shows sharp pixels on
  an example render.

### 9. Right panel: layers

- A `QListWidget`/`QListView` with drag-and-drop reordering. **The top row is drawn
  last** (on top) and the bottom row first, as in image editors.
- Each row has an **eye** toggle (show/hide) and a **red** toggle ("Červená", red mask),
  then the layer (file) name. The tooltip says in how many frames the layer exists
  (for example `render_scene.png – 1 of 30 frames`). A layer missing from the current
  frame is shown dimmed.
- Any change re-composes the current frame. The layer state applies to all frames of
  the animation.
- **The state carries over to the next animation** (in memory only, not saved to disk).
  When another animation opens, its layers start in the default order (step 2). Then the
  layers whose names were in the previous animation take the visible and red flags they
  had there, and their remembered relative order. They are sorted among the positions
  those known layers occupy, while new layers keep their default positions and default
  flags (visible, not red). This makes browsing many similar animations keep a set-up
  such as "render.png hidden, render_aircraft.png red". A layer that does not exist in
  the new animation is still remembered for later ones.
- Verify: a pytest-qt test that reordering, hiding and red each change the composed
  image as expected. A unit test of the carry-over merge: known layers keep their flags
  and relative order, new layers get the defaults, and an absent layer is remembered.

### 10. Status line

Three fields under the image:

- **Width × height** of the bottom layer (the canvas size; `1672 x 941` in the example).
- **Zoom %** (`125 %`; from `1.6 %` at 1/64× to `6400 %` at 64×).
- **Pixel under the cursor**: `x,y` in canvas pixels and the colour of the composed
  image there as `#RRGGBBAA`. The field is empty when the cursor is outside the image.
  The values update on mouse move and on frame change, including during playback.

Verify: a pytest-qt test that moving the mouse over a known synthetic image shows the
right coordinates and colour at 1× and at 4×.

### 11. Docs and cross-platform check

- `README.md`: how to install (`uv sync`), run, and the expected folder **shape**
  (root → animations → frames → images; any names; PNG/JPG; other files ignored).
- A manual test checklist on Windows against the example folder. A smoke test on macOS
  and Linux (X11 and Wayland; Qt itself runs on Wayland, unlike the recorder).

## Risks

- **Memory**: one example animation is already about 0.9 GB decoded, and other folders
  can have more frames, more layers or larger images. This is why step 4 has a capped
  LRU cache and loads neighbours only, not the whole animation.
- **Scan speed**: hundreds to thousands of animation folders, possibly on a network
  drive. Only folder names are listed up front; frames are scanned on click, off the UI
  thread.
- **Universal rules may pick up unwanted folders**: any subfolder of an animation counts
  as a frame (for example a stray `thumbnails/` folder would become one extra frame).
  This was accepted as the price of not depending on `frame` naming.
- **Stretching** layers with different aspect ratios distorts them. This is intended per
  the recording, but it can be surprising.
- **Renders in progress**: the example's `animation.json` announces 30 frames, but
  frames 10–29 have no images yet. Because empty frames are skipped, the app shows only
  what exists on disk, and a **Reload** (F5) of the current animation picks up new
  frames and files.
- **Playback speed**: decoding 4–5 PNGs of 1672×941 per frame may take longer than
  100 ms on the first loop. The plan holds the frame rather than skipping, and the cache
  makes later loops smooth as long as the animation fits under the memory cap. An
  animation larger than the cap is decoded again on every loop and may never reach
  10 fps.

## Assumptions

- The **controls panel is on the left** and the **layers panel is on the right**, and both
  are collapsible. At 1:04 the narration says "a collapsible panel on the right" while
  the drawing is on the left, then "Pardon", a redraw, and "the control panel, which will
  be collapsible" on the left. The layers are placed on the right at 4:10, and at
  8:34–8:52 "the left and the right part will both be collapsible".
- **Canvas size**: at 7:06 the narration first says "maximum width and height of all
  images", then at 7:32 changes it to "the bottom-most layer decides the size". The plan
  follows the later statement.
- Folder and file names are never interpreted, so the example's JSON metadata is not
  used.
- The "táhlo" (slider) of up to 200 px is a fixed maximum width, not a size per frame.
- The layer order, visibility and red flag carry over between animations in memory, but
  are not saved to disk; a new start of the app begins with the defaults.
- Packaging is not part of this plan: the app runs from the repository with `uv run`
  (or the launcher scripts).
- Red means solid red (`#FF0000`) on the opaque pixels, not a semi-transparent tint.
- The transcript wording "pochu" was read as "plochu" (the drawing area), and
  "scalenou vylouženě" as "scaled using stretch".

## Decisions (answers of 2026-11-24)

| Question | Decision | Where |
|---|---|---|
| Default layer order | Most frequent layer (in most frames) at the bottom, ties by name | Step 2 |
| Frames without images | Skipped | Steps 2, 7 |
| Animation list order | Ascending (natural sort, oldest timestamp first) | Step 2 |
| Layer state | Carried over to the next animation by layer name, in memory only | Step 9 |
| Zoom range | 1/64× to 64× | Step 8 |
| Playback | Play / Stop, fixed 10 fps, loops until Stop | Step 7 |
| Status line | Width × height, zoom %, pixel `x,y` and colour under the cursor | Step 10 |
| Name and distribution | AI Mod Painter (`ai-mod-painter` / `ai_mod_painter`), `uv run`, no installer | Step 1 |

## Open questions

None blocking. Two details are settled by assumption and are easy to change:

1. Dragging the slider during playback moves the position, and playback continues from
   there (step 7). The alternative is that grabbing the slider stops playback.
2. Space toggles Play / Stop (step 7).
