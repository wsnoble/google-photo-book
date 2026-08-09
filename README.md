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
`dlopen`, which on Apple Silicon Homebrew installs isn't on the default
library search path. `photobook` detects and works around this
automatically, so this normally doesn't need any manual setup. If you
still see an error like `OSError: cannot load library
'libgobject-2.0-0'`, confirm `pango` is actually installed (`brew list
pango`).

## Usage

```sh
uv run photobook --help
```

Full docs (workflow walkthrough, CLI reference, review-file format) are
in [`docs/`](docs/) — see [`docs/index.md`](docs/index.md) to start, or
build them locally:

```sh
uv sync --group docs
uv run mkdocs serve   # http://127.0.0.1:8000, live-reloads on edit
```

They're set up to publish on [Read the Docs](https://readthedocs.org/)
via `.readthedocs.yaml` and `mkdocs.yml` — importing the repo on
readthedocs.org (not done yet) is what actually makes them live at a
public URL.

## Development

```sh
uv run pytest        # run tests
uv run ruff check .  # lint
uv run ruff format . # format
```

## Contributing

All changes land via pull request — `main` requires at least one
approving review, and the CI workflow (`ruff check`, `ruff format
--check`, `pytest`) must pass before merging.
