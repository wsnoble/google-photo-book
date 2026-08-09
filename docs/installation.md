# Installation

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management and
  running the tool
- On macOS: the `pango` system library (via Homebrew), needed by
  [WeasyPrint](https://weasyprint.org/) for PDF rendering. Only the
  `proof` and `build` commands touch WeasyPrint — `import` and
  `review-export` don't need it.

## Setup

```sh
brew install uv pango   # macOS; skip `pango` on Linux if already present
uv sync
```

`uv sync` creates a `.venv` and installs everything declared in
`pyproject.toml`, including the offline reverse-geocoding library used
for chapter detection (`reverse-geocode`) and WeasyPrint.

### macOS: WeasyPrint / pango

WeasyPrint loads `pango`/`glib` via `dlopen`, which on Apple Silicon
Homebrew installs isn't on the default library search path. `photobook`
detects and works around this automatically (it patches
`DYLD_FALLBACK_LIBRARY_PATH` before importing WeasyPrint) — you shouldn't
need to do anything beyond `brew install pango`. If you still see an
error like `OSError: cannot load library 'libgobject-2.0-0'`, confirm
`pango` is actually installed (`brew list pango`) and that Homebrew's
lib directory is `/opt/homebrew/lib` (Apple Silicon) or `/usr/local/lib`
(Intel) — those are the only two paths the workaround checks.

## Verify it's working

```sh
uv run photobook --help
uv run photobook version
```

Next: the [Workflow](workflow.md) page walks through the full pipeline
on a real Takeout export.
