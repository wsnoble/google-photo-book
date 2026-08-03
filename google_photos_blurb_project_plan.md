# Google Photos → Blurb Photo Book Project Plan

## Goal

Create a reusable pipeline that converts a Google Photos album exported
with Google Takeout into a professionally formatted, Blurb-ready
hardcover photo book while preserving photo captions.

## Design Principles

-   Reproducible: rerun on future albums with minimal changes.
-   Robust: tolerate Google Takeout quirks (edited photos, duplicate
    names, missing JSON files).
-   Configurable: behavior controlled by YAML rather than code changes.
-   Incremental: verify each stage before moving on, with automated
    tests backing each stage rather than just manual proof-PDF review.

## Inputs

-   Google Takeout export of a single album.
-   Image files (JPG/JPEG/HEIC/PNG).
-   `*.supplemental-metadata.json` sidecar files.
-   Optional YAML configuration.

## Outputs

### Intermediate

-   `photos.json`
-   `report.csv`
-   `report.txt`
-   Low-resolution proof PDF

### Final

-   Print-ready PDF sized for Blurb.
-   Optional HTML version.
-   Optional archive of processed metadata.

------------------------------------------------------------------------

# Tooling & Project Setup

-   **Environment**: [`uv`](https://docs.astral.sh/uv/) manages the
    Python version, virtual environment, and dependencies
    (`uv init`, `uv add`, `uv run`). Target Python 3.12+.
-   **Testing**: `pytest`, run via `uv run pytest`. See
    [Testing Strategy](#testing-strategy) below.
-   **Linting/formatting**: `ruff` (fast, single tool for both).
-   **CLI**: `typer` for subcommands (`import`, `validate`, `proof`,
    `build`) — thin, well-typed, plays nicely with `uv run`.
-   **Core libraries**:
    -   `Pillow` + `pillow-heif` — image reading, EXIF, dimensions,
        HEIC decoding. Verified (via `otool -L` on the installed wheel)
        that `pillow-heif`'s macOS wheel bundles its own `libheif`
        (`@loader_path/pillow_heif/.dylibs/...`) rather than linking a
        system one, so no `brew install libheif` step is needed.
    -   `pydantic` — YAML config validation with clear error messages.
    -   `PyYAML` — config parsing.
    -   `Jinja2` + `WeasyPrint` — HTML/CSS → PDF rendering (WeasyPrint
        honors CSS `@page` rules for trim size, bleed, and margins,
        and embeds fonts natively). Note the WeasyPrint system
        dependency (`pango`, `cairo`, `gdk-pixbuf` via
        `brew install pango`) — flag this in the README as an install
        prerequisite.
    -   `pypdf` — structural verification of generated PDFs (page
        count, page size, metadata) in tests and the build script.

### Suggested repo layout

```
google-photo-book/
  pyproject.toml
  README.md
  src/
    photobook/
      __init__.py
      cli.py            # typer entry point
      config.py         # YAML loading + pydantic models
      model.py           # Photo dataclass
      importer.py        # Takeout scanning + metadata matching
      validation.py       # report.csv / report.txt generation
      ordering.py
      classify.py          # portrait / landscape / square / panorama
      layout.py             # page layout engine
      render.py              # Jinja2 + WeasyPrint rendering
      proof.py                # proof PDF generation
      frontmatter.py           # title/copyright/TOC/chapter pages
      templates/                # inside the package (not repo root), so
        proof.html.jinja        # FileSystemLoader finds them regardless
        book.html.jinja         # of install location
  tests/
    fixtures/
      sample_takeout/          # tiny synthetic Takeout export, checked in
    test_importer.py
    test_ordering.py
    test_classify.py
    test_layout.py
    test_render.py
    test_config.py
```

------------------------------------------------------------------------

# Architecture

## 1. Import

Responsibilities:

-   Scan recursively.
-   Ignore videos.
-   Detect edited images.
-   Match images with metadata.
-   Read:
    -   caption
    -   timestamps
    -   Google Photos URL
    -   EXIF orientation
    -   image size

Priority for timestamps:

1.  `photoTakenTime`
2.  `creationTime`
3.  EXIF
4.  Unknown (flagged)

Metadata matching:

1.  Exact filename.
2.  Original image for `-edited`.
3.  Duplicate suffixes such as `(1)` and `(2)`.
4.  Report unmatched files.

------------------------------------------------------------------------

## 2. Validation

Generate summary statistics:

-   Printable images
-   Videos skipped
-   Captions found
-   Missing captions
-   Metadata inherited
-   Unmatched images
-   Unused JSON files

Produce `report.csv` for manual inspection.

------------------------------------------------------------------------

## 3. Internal Data Model

Each image becomes one object:

``` python
@dataclass
class Photo:
    image_path: Path
    metadata_path: Path | None
    timestamp: datetime | None
    timestamp_source: Literal["photoTakenTime", "creationTime", "exif", "unknown"]
    caption: str | None
    width: int
    height: int
    orientation: int
    edited: bool
```

The remainder of the pipeline operates only on these objects.

------------------------------------------------------------------------

## 4. Ordering

Initial ordering:

-   Sort by `photoTakenTime`.

Fallbacks:

-   `creationTime`
-   EXIF
-   Unknown: appended at the end, in scan order (implemented in
    `ordering.py` as Milestone 2's stopgap; see caveat below).

Verified (2026-08-02) that Google Photos' custom manual album
ordering — dragging photos into a deliberate sequence in the album UI,
distinct from chronological order — is **not recoverable from a
Takeout export itself**: the per-photo JSON has no position field, and
the album-level `metadata.json` contains only `{"title": ...}`. The
Photos Library API's read scope was locked down in March 2025 to
app-created content only, so it can no longer read an existing
album's order either. No community tool (e.g. GooglePhotosTakeoutHelper)
has solved this. Saving the album page as HTML only captures a subset
because the web UI virtualizes/lazy-loads the photo grid.

**However**, the order *is* recoverable from the live album via
browser automation: driving a real scroll through the shared album
page (`photos.google.com/share/...`) forces each photo tile to render,
and each tile's accessibility label (`aria-label="Photo - Landscape -
Aug 4, 2017, 9:26:32 PM"`) exposes an exact timestamp. Collecting
these in DOM order and correlating them against `photos.json`'s
`photoTakenTime` values (after calibrating a timezone offset, since
the displayed time isn't UTC) recovered 255/287 (89%) of one real
album's true positions directly. This is a one-off manual process
(done interactively via `claude-in-chrome` against Google's
undocumented internal DOM structure, not a repeatable CLI feature) —
it would need redoing, and re-verifying against the live DOM, for
each album.

The remaining 32/287 (11%) had no timestamp match at all — most
likely their own `photoTakenTime` is simply inaccurate (a known issue
with old/edited photos), so no calibrated offset lines them up with
any candidate position. **First attempt interpolated these by
inserting each one next to whichever recovered photo had the closest
timestamp — this was wrong** and shipped a real ordering bug (verified
against the user's own review of the proof PDF: a photo the user
confirmed was #3 in the live album showed as #4, displaced by an
unrelated photo wrongly inserted at #3). The bug: the recovered
sequence is in *manual* album order, not sorted by time, so `bisect`
over it is invalid — silently produces an arbitrary position rather
than an error. Root cause is deeper than the implementation bug,
though: even a *correct* nearest-timestamp-neighbor insertion assumes
local chronological continuity, which a manually-curated,
non-chronological album explicitly violates (confirmed empirically:
fixing the bisect bug with correct nearest-neighbor logic still placed
the same photo wrong, because its own timestamp really is closest to
the wrong neighborhood). Timestamp proximity cannot honestly stand in
for a missing position here.

Implemented as `ordering.order_photos(photos, manual_order=...)` and
`photobook proof --manual-order <file.json>`: `manual_order` is a list
of `image_path` strings in the recovered/desired sequence; photos not
listed are appended at the end, sorted by timestamp among themselves —
an honest "position unknown," not a guessed one.

------------------------------------------------------------------------

## 5. Proof Book

Generate a compact PDF for verification.

Each entry includes:

-   Photo
-   Filename
-   Date
-   Caption
-   Warnings

Purpose:

-   Verify ordering.
-   Verify captions.
-   Verify orientation.
-   Detect missing metadata.

------------------------------------------------------------------------

## 6. Layout Engine

Target: Blurb **8×10 in, landscape orientation, image-wrap hardcover**
(Blurb lists this size as "Standard Landscape 10×8" — width×height
before orientation naming; confirm the exact catalog name and page
dimensions against Blurb's current
[Specification Calculator](https://www.blurb.com/make/pdf_to_book/booksize_calculator)
before final build, since Blurb determines exact page size, bleed, and
safety margin per size/paper/cover combination rather than a fixed
constant — see [Milestone 4](#milestone-4)).

Layout rules:

-   Large landscape images: one per page.
-   Portraits: two per page when appropriate.
-   Panoramas: full-width.
-   Hero images: full-page.
-   Captions below photos.
-   No reserved caption space when caption absent.

Automatic image classification:

-   Portrait
-   Landscape
-   Square
-   Panorama

------------------------------------------------------------------------

## 7. Typography

Use HTML/CSS templates rendered to PDF via WeasyPrint, with trim size,
bleed, and margins driven by CSS `@page` rules generated from the
resolved Blurb spec (see Milestone 4) rather than hardcoded.

Fonts (pick one as default, configurable):

-   Crimson Pro
-   Garamond
-   Palatino

Captions:

-   10–11 pt
-   Preserve paragraph breaks.

------------------------------------------------------------------------

## 8. Front Matter

Generate automatically:

-   Title page
-   Optional copyright page
-   Optional table of contents
-   Chapter divider pages

------------------------------------------------------------------------

## 9. Configuration

Example:

``` yaml
book:
  title: GERT Highlights
  size: 8x10_landscape
  cover: image_wrap

layout:
  hero_every: 12

captions:
  enabled: true

ordering:
  by: photoTakenTime

prefer:
  edited_images: true
```

Validated at load time via a `pydantic` model in `config.py`; invalid
or unknown keys fail fast with a clear message rather than silently
being ignored.

------------------------------------------------------------------------

## 10. Future Enhancements

### Ratings

Allow a ratings file:

    IMG_1432.JPG *****
    IMG_1717.JPG ****

Higher-rated images receive larger layouts.

### Chapters

Allow manual chapter breaks.

### Maps

Optional travel maps between chapters.

### Index

Generate a filename/date index.

### Image quality

Detect low-resolution images before printing (compare effective PPI
at print size against Blurb's 300 PPI guidance).

------------------------------------------------------------------------

# Testing Strategy

-   **Fixtures over mocks**: check a small synthetic Takeout export
    into `tests/fixtures/sample_takeout/` — a handful of tiny real
    images (a few KB each) plus their `.supplemental-metadata.json`
    sidecars, covering: a normal photo, an `-edited` pair, a
    duplicate-suffix pair (`(1)`), a photo with a missing JSON
    sidecar, and a video (to confirm it's skipped). Tests run against
    this real directory rather than mocked filesystem calls, so
    regressions in the actual matching logic surface directly.
-   **Unit tests per stage**, matching the module boundaries above:
    -   `test_importer.py` — filename matching priority, edited-image
        detection, duplicate suffix handling, unmatched-file
        reporting, timestamp fallback priority.
    -   `test_ordering.py` — sort stability and fallback chain.
    -   `test_classify.py` — orientation thresholds (portrait /
        landscape / square / panorama) using known width/height pairs.
    -   `test_config.py` — valid config loads correctly; invalid/
        unknown keys raise a clear validation error.
    -   `test_layout.py` — given a fixed list of classified `Photo`
        objects, assert the resulting page plan (which photos land on
        which page, hero placement) rather than pixels.
    -   `test_render.py` — rendering a small photo set produces a PDF
        with the expected page count; use `pypdf` to assert structural
        properties (page count, page size in points, non-empty text
        layer for captions) rather than visual diffing.
-   **Golden files**: `photos.json` and `report.csv` output for the
    fixture album are checked into `tests/fixtures/` as expected
    output; tests do a structural comparison (not raw byte diff, so
    incidental key-ordering changes don't break tests).
-   **Out of scope for automated tests**: pixel-level visual
    regression of the final layout. That stays a manual step — open
    the proof PDF (Milestone 2) and the final PDF (Milestone 4) and
    eyeball them. Revisit only if visual bugs recur often enough to
    justify a `pdf2image` + image-diff harness.

------------------------------------------------------------------------

# Development Milestones

## Milestone 0

Project scaffolding

-   `uv init`, `pyproject.toml` with the dependencies above.
-   `src/photobook` package skeleton + `tests/` with one trivial
    passing test.
-   `uv run pytest` and `uv run ruff check` both green in CI-less
    local dev.

## Milestone 1

Importer

Deliverables:

-   photos.json
-   report.csv
-   report.txt

## Milestone 2

Proof PDF

Verify:

-   ordering
-   captions
-   metadata

## Milestone 3

Professional layout engine

Generate attractive pages using HTML templates.

## Milestone 4

Blurb-ready PDF

-   Pull exact page size, bleed, and safety margin from Blurb's
    [Specification Calculator](https://www.blurb.com/make/pdf_to_book/booksize_calculator)
    for the chosen size/paper/cover combination — do not hardcode
    assumed values, since Blurb computes these per configuration.
-   Export as individual pages (not spreads), per Blurb's PDF-to-Book
    requirements.

Verify:

-   page size matches the spec tool output
-   bleed matches the spec tool output
-   margins / safety area
-   embedded fonts
-   images meet the ≤300 PPI guidance at print size

## Milestone 5

Polish

-   Hero images
-   Chapter pages
-   Improved typography
-   Ratings support

------------------------------------------------------------------------

# Decisions & Defaults

Resolved for the MVP (change via config, not code):

-   Prefer edited images over originals when both exist: `true`.
-   Order by `photoTakenTime` with `creationTime` → EXIF fallback.
-   Captions enabled, shown below photos, 10–11 pt.

-   Target: **8×10 in landscape, image-wrap hardcover**. Exact Blurb
    catalog size name, paper stock, and precise trim/bleed/safety
    numbers still need to be pulled from the
    [Specification Calculator](https://www.blurb.com/make/pdf_to_book/booksize_calculator)
    in Milestone 4.
-   No chapter support in the MVP — single flowing sequence, ordered
    by timestamp. Chapters remain a Future Enhancement.

Still needs your input before implementation starts:

-   Font: undecided (Crimson Pro / Garamond / Palatino / other). Will
    be wired up as a config value so it's a one-line YAML change
    whenever you decide — not blocking Milestone 0–3 work.
-   Whether to show photo dates in the final book (vs. proof PDF
    only).

------------------------------------------------------------------------

# Success Criteria

The final system should:

-   Preserve captions.
-   Produce a visually appealing hardcover book.
-   Require minimal manual intervention.
-   Be reusable for future Google Photos albums.
-   Have automated test coverage for every stage except final visual
    layout, so future album runs catch regressions before spending a
    print credit.
