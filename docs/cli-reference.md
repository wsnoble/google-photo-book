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

Renders the actual Blurb-ready book PDF: panoramas get their own page,
everything else fills grid pages (mostly 4-5 photos, occasionally 2),
every photo shown uncropped at its own aspect ratio, captions below when
present.

| Option | Default | Description |
| --- | --- | --- |
| `PHOTOS_JSON` (argument) | — | Path to `photos.json` from `import`. Required. |
| `--output`, `-o` | `build/book.pdf` | Path to write the book PDF to. |
| `--config`, `-c` | — | Optional YAML config file (see [Workflow](workflow.md#config-file)). |
| `--manual-order` | — | Same as `proof`'s `--manual-order`. Ignored if `--review-file` is given. |
| `--guess-leftover-positions` | off | Same as `proof`'s. Ignored if `--review-file` is given. |
| `--chapters` | off | Groups photos into chapters by country (reverse-geocoded from GPS data), with a divider page between chapters. Photos without GPS inherit their chronologically-nearest geotagged photo's country, with no distance limit — verify visually for albums spanning long GPS gaps. First use is slow (~10s one-time cost to build the offline geocoding index). Ignored if `--review-file` is given. |
| `--review-file` | — | TSV file giving full manual control over order, chapter boundaries, captions, and solo-page placement. See [Review file format](review-file-format.md). Takes full precedence over `--manual-order`, `--guess-leftover-positions`, and `--chapters`. Cannot be combined with `--manual-order`. |

The command prints the number of photos actually included in the book —
with `--review-file`, that can be fewer than `photos.json` contains, since
a photo omitted from the review file is excluded.

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
index used for chapter assignment) — the command prints a note when this
is happening.
