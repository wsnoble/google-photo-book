# CLI reference

Every command supports `--help` for the authoritative, always-up-to-date
option list (e.g. `uv run photobook build --help`); this page explains
the same options with more context.

## `version`

```sh
uv run photobook version
```

Prints the installed `photobook` version. No options.

## `import`

```sh
uv run photobook import TAKEOUT_DIR [--output DIR] [--config FILE]
```

Scans a Google Takeout album folder and writes `photos.json`,
`report.csv`, and `report.txt` into the output directory.

| Option | Default | Description |
| --- | --- | --- |
| `TAKEOUT_DIR` (argument) | — | Path to the Takeout album folder. Required. |
| `--output`, `-o` | `build` | Directory to write the three output files into. |
| `--config`, `-c` | — | Optional YAML config file (see [Workflow](workflow.md#config-file)). |

## `proof`

```sh
uv run photobook proof PHOTOS_JSON [--output FILE] [--manual-order FILE] [--guess-leftover-positions]
```

Renders a compact, text-heavy PDF (thumbnail, filename, date, caption,
warnings) listing every photo in book order — for reviewing the raw
data, not the final layout.

| Option | Default | Description |
| --- | --- | --- |
| `PHOTOS_JSON` (argument) | — | Path to `photos.json` from `import`. Required. |
| `--output`, `-o` | `build/proof.pdf` | Path to write the proof PDF to. |
| `--manual-order` | — | JSON file listing `image_path` strings in a specific order. Photos not listed are appended at the end (dated ones sorted by timestamp, undated ones last). |
| `--guess-leftover-positions` | off | With `--manual-order`, insert leftover (unlisted) photos next to their chronologically-closest neighbor instead of appending them at the end. A best-effort guess, not a recovered fact — check the result visually. |

## `build`

```sh
uv run photobook build PHOTOS_JSON [--output FILE] [--config FILE] [--manual-order FILE]
                        [--guess-leftover-positions] [--chapters] [--review-file FILE]
```

Renders the actual Blurb-ready book PDF: a title page comes first (see
`book.title`/`book.subtitle` in [Workflow](workflow.md#config-file)), then
panoramas get their own page, everything else fills grid pages (mostly
4-5 photos, occasionally 2), every photo shown uncropped at its own
aspect ratio, captions below when present.

| Option | Default | Description |
| --- | --- | --- |
| `PHOTOS_JSON` (argument) | — | Path to `photos.json` from `import`. Required. |
| `--output`, `-o` | `build/book.pdf` | Path to write the book PDF to. |
| `--config`, `-c` | — | Optional YAML config file (see [Workflow](workflow.md#config-file)). |
| `--manual-order` | — | Same as `proof`'s `--manual-order`. Ignored if `--review-file` is given. |
| `--guess-leftover-positions` | off | Same as `proof`'s. Ignored if `--review-file` is given. |
| `--chapters` | off | Groups photos into chapters by country (reverse-geocoded from GPS data), with a divider page between chapters. Photos without GPS inherit their chronologically-nearest geotagged photo's country, with no distance limit — verify visually for albums spanning long GPS gaps. First use is slow (~10s one-time cost to build the offline geocoding index) *if the album has any geotagged photos* — skipped entirely otherwise. Ignored if `--review-file` is given. |
| `--review-file` | — | TSV file giving full manual control over order, chapter boundaries, captions, and solo-page placement. See [Review file format](review-file-format.md). Takes full precedence over `--manual-order`, `--guess-leftover-positions`, and `--chapters`. Cannot be combined with `--manual-order`. |

The command prints the number of photos actually included in the book —
with `--review-file`, that can be fewer than `photos.json` contains, since
a photo omitted from the review file is excluded.

Blurb's preflight check requires an even page count. After writing the
PDF, the command re-opens it and prints a warning if the total (including
the title page) comes out odd — it doesn't try to fix this automatically,
since padding with a blank page is a layout decision, not just a
mechanical one.

## `cover`

```sh
uv run photobook cover PHOTOS_JSON --front FILENAME --back FILENAME --interior FILE
                        [--output FILE] [--config FILE]
```

Renders the single-spread cover PDF (back cover, spine, front cover, left
to right) for Blurb's Hardcover ImageWrap: `--front` and `--back` are
center-cropped to fill their panel edge-to-edge (the only place in this
codebase that crops a photo — every interior page shows photos uncropped),
the spine shows the title reading bottom-to-top, and the front panel
shows the title/subtitle.

| Option | Default | Description |
| --- | --- | --- |
| `PHOTOS_JSON` (argument) | — | Path to `photos.json` from `import`. Required. |
| `--front` | — | Filename of the photo (e.g. `IMG_1234.jpg`, matched by filename against `photos.json`) to use for the front cover. Required. |
| `--back` | — | Same, for the back cover. Required. |
| `--interior` | — | Path to the already-built interior PDF (from `build`). Its page count is read and checked against the cover's spine width — see below. Required. |
| `--output`, `-o` | `build/cover.pdf` | Path to write the cover PDF to. |
| `--config`, `-c` | — | Optional YAML config file (see [Workflow](workflow.md#config-file)) — supplies the title/subtitle shown on the cover. |

The cover's exact dimensions (including spine width) are fixed constants
in `cover.py`, hand-verified against Blurb's live PDF-uploader preflight
for one specific interior page count — **not** Blurb's own Specification
Calculator, which was found to report a slightly wrong size for this
book's configuration. The command refuses to run if `--interior`'s page
count doesn't match what those constants were verified for, rather than
silently generating a wrong-width spine on a physical, unreturnable
printed book. If your interior page count is different, you'll need to
re-verify: upload a test cover to Blurb, read the corrected size from the
preflight error if it's rejected, and update the constants in `cover.py`
accordingly.

## `review-export`

```sh
uv run photobook review-export PHOTOS_JSON [--output FILE] [--force]
```

Generates an editable review TSV from `photos.json`: photos ordered by
timestamp (undated ones last), chapters auto-assigned by country,
existing captions carried over, and a best-effort `solo` column. See
[Workflow](workflow.md#4-generate-a-review-file) and
[Review file format](review-file-format.md) for details.

| Option | Default | Description |
| --- | --- | --- |
| `PHOTOS_JSON` (argument) | — | Path to `photos.json` from `import`. Required. |
| `--output`, `-o` | `build/review.tsv` | Path to write the review TSV to. |
| `--force` | off | Overwrite an existing file at the output path. Without it, the command refuses to touch a file that already exists, since it may contain hand edits. |

First use is slow (~10s one-time cost to build the offline geocoding
index used for chapter assignment) *if the album has any geotagged
photos* — skipped entirely otherwise. The command prints a note when the
slow path is happening.
