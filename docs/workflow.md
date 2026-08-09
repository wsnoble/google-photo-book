# Workflow

This walks through the full pipeline, from a raw Takeout export to a
print-ready PDF.

## 1. Get a Takeout export

Export the album from [Google Takeout](https://takeout.google.com/) —
select **Google Photos**, and if possible limit it to the specific album
you want (Takeout lets you pick individual albums). Unzip it; you should
end up with a folder containing the album's photos and a `.json`
metadata sidecar file next to each one.

## 2. Import

```sh
uv run photobook import "path/to/Takeout/Google Photos/My Album" -o build
```

This scans the folder and writes three files into `build/`:

- **`photos.json`** — every photo's resolved metadata (caption,
  timestamp, dimensions, GPS, EXIF orientation) in the internal format
  every other command reads. This is the input to everything below.
- **`report.csv`** / **`report.txt`** — a per-photo and summary report
  of what was found: how many photos, how many had captions, how many
  had no GPS data, any orphaned metadata files, etc. Worth a skim to
  catch anything unexpected before continuing.

Takeout's quirks (edited-photo pairs, duplicate-filename JSON renaming,
metadata sidecar matching) are handled automatically here — see the
[CLI reference](cli-reference.md#import) for the `--config` option that
controls whether edited or original photos are preferred.

## 3. (Optional) Proof

```sh
uv run photobook proof build/photos.json -o build/proof.pdf
```

A compact, text-heavy PDF listing every photo — thumbnail, filename,
date, caption, and any warnings — in book order. It's meant for a quick
sanity check (does the order look right? are captions where you expect?
are there a lot of "no GPS data" warnings?) before spending time on the
full review file or the real build.

## 4. Generate a review file

```sh
uv run photobook review-export build/photos.json -o build/review.tsv
```

This produces an editable TSV: every photo ordered by timestamp
(undated photos grouped at the end), chapters auto-assigned by country
from GPS data, existing captions carried over, and a best-effort `solo`
column marking which photos currently land alone on a page. Open it in
Excel, Numbers, Google Sheets, or a text editor.

!!! note "Uncaptioned photos are left blank"
    Writing a short descriptive tag for a photo with no real caption
    (e.g. `"garden gnomes in the grass"`) requires actually looking at
    the photo — this command has no way to do that on its own. If
    you're working with an AI assistant, that's a reasonable thing to
    ask it to do for you across the uncaptioned rows before you start
    editing; otherwise just leave those rows' `tag` column blank, or
    fill them in yourself as you go.

See the [review file format](review-file-format.md) page for exactly
what each column means and how to edit it.

## 5. Edit the review file

Common edits:

- **Reorder** — cut/paste rows to fix the photo order.
- **Delete** a row — that photo is dropped from the book entirely.
- **Move a `chapter` row** — moves where that chapter starts. Delete one
  to merge two chapters together; add one to split a chapter in two;
  edit `chapter_title` to rename it.
- **Edit `tag`** — an unparenthesized value becomes that photo's real
  caption; a parenthesized value (the auto-generated placeholders from
  step 4) is just a reference note and won't appear in the book.
- **Edit `solo`** — `true` forces that photo onto its own page, `false`
  forces it to always share a page with others (even a panorama), blank
  leaves it to the automatic decision.

## 6. Build

```sh
uv run photobook build build/photos.json --review-file build/review.tsv
```

Renders the actual book PDF to `build/book.pdf`, following the review
file's order, chapter boundaries, captions, and solo-page overrides
exactly. Re-run this as many times as you like while you keep refining
`review.tsv` — nothing about the build step mutates the review file.

## Simpler alternatives to a review file

The review file is the most control, but it's also the most manual
effort. `build` and `proof` both work directly on `photos.json` too:

- **Bare `build`**: no flags — orders photos by timestamp (undated
  last), no chapters, no per-photo overrides. Fastest path to a first
  draft.
- **`--chapters`**: adds automatic country-based chapter dividers on top
  of the timestamp order, without needing a review file at all.
- **`--manual-order`**: a JSON file listing `image_path` strings in a
  specific order (e.g. scraped from the live Google Photos album's
  actual display order) — see the [CLI reference](cli-reference.md#build)
  for details and the `--guess-leftover-positions` companion flag.

`--review-file` takes full precedence over all of these if given; see
the reference for exactly which flags it makes redundant.

## Config file

Both `import` and `build` accept `--config path/to/config.yaml`. Only
two settings currently do anything:

```yaml
book:
  title: "My Trip"       # used in build's PDF metadata title
prefer:
  edited_images: true    # import: prefer "-edited" photo variants over originals
```

(The config schema has a few more fields declared for future use --
`layout.hero_every`, `captions.enabled`, `ordering.by`, `book.size`,
`book.cover` — but none of them are wired up to any behavior yet.)
