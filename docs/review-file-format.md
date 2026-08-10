# Review file format

The review file is a tab-separated (`.tsv`) file with one row per photo
plus optional chapter-divider rows. It's the input to `build
--review-file` and the output of `review-export` (see
[Workflow](workflow.md)).

## Columns

| Column | Meaning |
| --- | --- |
| `row_type` | `chapter` or `photo`. Anything else is a validation error. |
| `image_path` | The photo's path, exactly as it appears in `photos.json`. This is the only column the build actually uses to identify *which* photo a row refers to — required, and must match a real photo. |
| `filename` | The photo's filename, for your reference only. Never read back. |
| `date` | The photo's date (`YYYY-MM-DD`), for your reference only. Never read back. |
| `tag` | See [Tags and captions](#tags-and-captions) below. |
| `chapter_title` | Only meaningful on `chapter` rows — the chapter's title, shown on its divider page. |
| `solo` | `true`, `false`, or blank. See [Solo-page control](#solo-page-control) below. |

Only `row_type`, `image_path`, `tag`, and `chapter_title` are required
columns — a file missing any of them is rejected. `solo` is optional
(older files without it still load fine, and every photo just falls back
to the automatic decision).

## Row order is book order

`photo` rows are rendered in the order they appear in the file — cut and
paste rows to reorder the book.

## Omitting a photo excludes it

A photo in `photos.json` that doesn't have a corresponding row in the
review file is **excluded from the book entirely**. This is different
from `--manual-order`, where an unlisted photo gets appended at the end
instead — the review file is meant to be a complete, edited roster, so a
missing row is treated as a deliberate deletion, not an oversight.

Conversely, every `image_path` that *is* listed must match a real photo
in `photos.json`, or the build fails with a clear error naming the file
and line number.

## Chapter boundaries come from row position

A `chapter` row starts a new chapter — every `photo` row after it
belongs to that chapter, until the next `chapter` row (or the end of the
file). There's no per-photo chapter field; the row's *position* is the
only thing that matters. To fix a chapter boundary:

- **Move** a `chapter` row to change where that chapter starts.
- **Delete** a `chapter` row to merge it into the previous chapter.
- **Add** a new `chapter` row to split a chapter in two.
- **Edit** `chapter_title` to rename it.

Up to three photos at the start of each chapter share the chapter's
divider page (title in one quadrant, up to three photos in the others)
rather than the title taking a full page by itself; the rest of the
chapter's photos fill ordinary pages after it.

## Tags and captions

The `tag` column serves double duty:

- **Unparenthesized** (`Skiing at Dieni`) — becomes that photo's real
  caption in the book.
- **Parenthesized** (`(garden gnomes in the grass)`) — a reference note
  only, meant to help you identify the photo while editing. It's
  ignored, not shown in the book. `review-export` writes existing real
  captions unparenthesized and leaves uncaptioned photos blank (see
  [Workflow](workflow.md#4-generate-a-review-file) for why it can't fill
  those in itself).

To give a previously-uncaptioned photo a real caption, just remove the
parentheses (or write a caption in from scratch) and un-wrap it.

## Solo-page control

Some photos naturally land alone on a page — panoramas always do (they'd
lose too much detail cropped into a small grid cell), and occasionally an
ordinary photo does too, as a batch's leftover remainder. If a photo
shouldn't be alone, or should be alone but isn't:

- `solo=true` forces that photo onto its own page.
- `solo=false` forces it to always share a page with others — even if
  it's a panorama, or would otherwise be a lone leftover (in that case
  it's merged into a neighboring grid page instead of getting a page to
  itself).
- Blank leaves it to the automatic panorama-based decision.

`review-export` prefills `true` for every photo currently landing alone,
so you can scan for ones that don't belong there and flip them to
`false` rather than starting from a blank column.

## Example

```tsv
row_type	image_path	filename	date	tag	chapter_title	solo
chapter					Switzerland	
photo	/album/IMG_0345.JPG	IMG_0345.JPG	2017-02-25	Skiing at Dieni		
photo	/album/IMG_2783.JPG	IMG_2783.JPG	2017-03-29	(Family gathered in an office)		
chapter					Spain	
photo	/album/IMG_0595.JPG	IMG_0595.JPG	2017-04-08	The Sevilla Cathedral		true
```
