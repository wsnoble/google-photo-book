# google-photo-book

Converts a Google Takeout export of a Google Photos album into a
Blurb-ready photo book PDF. See
[`google_photos_blurb_project_plan.md`](google_photos_blurb_project_plan.md)
for the full design, architecture, and milestone plan.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) and, on macOS, two Homebrew
system libraries used by the PDF renderer:

```sh
brew install uv pango
uv sync
```

### macOS: WeasyPrint / pango caveat

WeasyPrint (used for HTML → PDF rendering) loads `pango`/`glib` via
`dlopen`, which on Apple Silicon Homebrew installs doesn't find them on
the default library search path. If you see an error like
`OSError: cannot load library 'libgobject-2.0-0'`, set:

```sh
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

(or `/usr/local/lib` on Intel Macs) before running `uv run ...`, or add
it to your shell profile.

## Usage

```sh
uv run photobook --help
```

## Development

```sh
uv run pytest        # run tests
uv run ruff check .  # lint
uv run ruff format . # format
```
