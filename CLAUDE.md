# Project rules

## No backward compatibility

AI Mod Painter is not deployed anywhere yet and nobody depends on it. When changing
anything (settings keys, CLI arguments, module layout), do not keep backward
compatibility and do not write migrations: rename, remove or change things directly and
update the code, tests and docs that use them.

## Universal folder rules

Never depend on folder or image names of a particular render output. The app works on
the shape root -> animation folders -> frame folders -> image files (PNG/JPG); every other
file is ignored. See `src/ai_mod_painter/core/library.py`.

## Checks

```
uv run ruff check
uv run ruff format --check
uv run pytest
```
