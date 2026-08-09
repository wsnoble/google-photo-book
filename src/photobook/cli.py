import json
from pathlib import Path
from typing import Annotated

import typer

from photobook import __version__
from photobook.config import load_config
from photobook.importer import scan_album
from photobook.model import Photo, load_photos
from photobook.validation import summarize, write_photos_json, write_report_csv, write_report_txt

app = typer.Typer(help="Build a Blurb-ready photo book from a Google Takeout album export.")


def _load_manual_order(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            f"{path} is not valid JSON: {exc}", param_hint="--manual-order"
        ) from exc
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise typer.BadParameter(
            f"{path} must contain a JSON array of strings (image_path values).",
            param_hint="--manual-order",
        )
    return data


@app.callback()
def callback() -> None:
    """photobook: command-line tools for the Google Takeout -> Blurb photo book pipeline."""


@app.command()
def version() -> None:
    """Print the installed photobook version."""
    typer.echo(__version__)


@app.command(name="import")
def import_album(
    takeout_dir: Annotated[
        Path,
        typer.Argument(
            exists=True, file_okay=False, help="Path to the Google Takeout album folder."
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Directory to write photos.json, report.csv, and report.txt into.",
        ),
    ] = Path("build"),
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config", "-c", exists=True, dir_okay=False, help="Optional YAML config file."
        ),
    ] = None,
) -> None:
    """Scan a Google Takeout album export and write photos.json/report.csv/report.txt."""
    config = load_config(config_path)
    result = scan_album(takeout_dir, prefer_edited=config.prefer.edited_images)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_photos_json(result, output_dir / "photos.json")
    write_report_csv(result, output_dir / "report.csv")
    write_report_txt(result, output_dir / "report.txt")

    for key, value in summarize(result).items():
        typer.echo(f"{key}: {value}")


@app.command()
def proof(
    photos_json: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, help="Path to the photos.json produced by `import`."
        ),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path to write the proof PDF to."),
    ] = Path("build/proof.pdf"),
    manual_order: Annotated[
        Path | None,
        typer.Option(
            "--manual-order",
            exists=True,
            dir_okay=False,
            help="Optional JSON file listing image_path strings in a manually-specified "
            "order; photos not listed are appended at the end (dated ones sorted by "
            "timestamp, undated ones last of all).",
        ),
    ] = None,
    guess_leftover_positions: Annotated[
        bool,
        typer.Option(
            "--guess-leftover-positions",
            help="With --manual-order, insert leftover (unlisted) photos next to their "
            "chronologically closest neighbor instead of appending them at the end. "
            "This is a best-effort guess, not a recovered fact, and can place a photo "
            "confidently in the wrong spot for a non-chronological manual order — "
            "check the result visually.",
        ),
    ] = False,
) -> None:
    """Render a compact proof PDF (photo, filename, date, caption, warnings) for review."""
    # Imported lazily: this pulls in WeasyPrint, which needs system libraries
    # (pango) not required by the other commands.
    from photobook.proof import build_proof_pdf

    photos = load_photos(photos_json)
    order = _load_manual_order(manual_order)
    build_proof_pdf(
        photos, output, manual_order=order, guess_leftover_positions=guess_leftover_positions
    )
    typer.echo(f"Wrote proof PDF with {len(photos)} photos to {output}")


@app.command()
def build(
    photos_json: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, help="Path to the photos.json produced by `import`."
        ),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path to write the book PDF to."),
    ] = Path("build/book.pdf"),
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config", "-c", exists=True, dir_okay=False, help="Optional YAML config file."
        ),
    ] = None,
    manual_order: Annotated[
        Path | None,
        typer.Option(
            "--manual-order",
            exists=True,
            dir_okay=False,
            help="Optional JSON file listing image_path strings in a manually-specified "
            "order; photos not listed are appended at the end (dated ones sorted by "
            "timestamp, undated ones last of all).",
        ),
    ] = None,
    guess_leftover_positions: Annotated[
        bool,
        typer.Option(
            "--guess-leftover-positions",
            help="With --manual-order, insert leftover (unlisted) photos next to their "
            "chronologically closest neighbor instead of appending them at the end. "
            "This is a best-effort guess, not a recovered fact — check the result visually.",
        ),
    ] = False,
    chapters: Annotated[
        bool,
        typer.Option(
            "--chapters",
            help="Groups photos into chapters by country (reverse-geocoded from GPS data), "
            "with a divider page between chapters. Photos without GPS inherit their "
            "chronologically-nearest geotagged photo's country, with no distance limit — "
            "verify visually for albums spanning long GPS gaps. First use is slow "
            "(~10s one-time cost to build the offline geocoding index). Ignored if "
            "--review-file is given.",
        ),
    ] = False,
    review_file: Annotated[
        Path | None,
        typer.Option(
            "--review-file",
            exists=True,
            dir_okay=False,
            help="Optional TSV file (row_type/image_path/filename/date/tag/chapter_title "
            "columns, plus an optional solo column) giving full manual control over "
            "order, chapter boundaries, captions, and solo-page placement: photo rows "
            "are the book order, a photo omitted entirely is excluded from the book, "
            "chapter boundaries come from 'chapter' divider rows (not a per-photo "
            "field), an unparenthesized tag becomes that photo's caption, and "
            "solo=true/false forces a photo onto/off of a page by itself (blank or the "
            "column being absent leaves it to the automatic panorama-based decision). "
            "Takes full precedence over --manual-order, --guess-leftover-positions, "
            "and --chapters, which are ignored if this is given. Cannot be combined "
            "with --manual-order.",
        ),
    ] = None,
) -> None:
    """Render the Blurb-ready book PDF: panoramas get their own page,
    everything else fills grid pages (mostly 4-5 photos, occasionally 2),
    every photo shown uncropped at its own aspect ratio, captions below
    when present.
    """
    # Imported lazily: this pulls in WeasyPrint, which needs system libraries
    # (pango) not required by the other commands.
    from photobook.render import build_book_pdf

    if review_file is not None and manual_order is not None:
        raise typer.BadParameter(
            "--review-file and --manual-order can't be combined -- --review-file already "
            "supplies its own order.",
            param_hint="--review-file",
        )

    config = load_config(config_path)
    photos = load_photos(photos_json)
    order = _load_manual_order(manual_order)
    if chapters and review_file is None:
        typer.echo("Reverse-geocoding photo locations for chapters (one-time ~10s cost)...")
    included_count = build_book_pdf(
        photos,
        output,
        book_title=config.book.title,
        book_subtitle=config.book.subtitle,
        manual_order=order,
        guess_leftover_positions=guess_leftover_positions,
        chapters=chapters,
        review_file=review_file,
    )
    typer.echo(f"Wrote book PDF with {included_count} photos to {output}")

    from pypdf import PdfReader

    page_count = len(PdfReader(output).pages)
    if page_count % 2 != 0:
        typer.echo(
            f"Warning: {page_count} pages is odd -- Blurb's preflight check requires an "
            "even page count and will reject this PDF as-is."
        )


@app.command()
def cover(
    photos_json: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, help="Path to the photos.json produced by `import`."
        ),
    ],
    front: Annotated[
        str,
        typer.Option("--front", help="Filename of the photo to use for the front cover."),
    ],
    back: Annotated[
        str,
        typer.Option("--back", help="Filename of the photo to use for the back cover."),
    ],
    interior: Annotated[
        Path,
        typer.Option(
            "--interior",
            exists=True,
            dir_okay=False,
            help="Path to the already-built interior book PDF (from `build`), read to confirm "
            "its page count matches what the cover's spine width was verified for.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path to write the cover PDF to."),
    ] = Path("build/cover.pdf"),
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config", "-c", exists=True, dir_okay=False, help="Optional YAML config file."
        ),
    ] = None,
) -> None:
    """Render the single-spread cover PDF (back cover, spine, front cover)
    for Blurb's Hardcover ImageWrap: --front and --back photos are
    center-cropped to fill their panel, the spine shows the title, and the
    front panel shows the title/subtitle. The cover's spine width is a
    fixed, hand-verified constant (see cover.COVER_VERIFIED_PAGE_COUNT) --
    this command refuses to run if --interior's page count doesn't match.
    """
    # Imported lazily: this pulls in WeasyPrint, which needs system libraries
    # (pango) not required by the other commands.
    from pypdf import PdfReader

    from photobook.cover import build_cover_pdf

    config = load_config(config_path)
    photos = load_photos(photos_json)

    def _find(filename: str, role: str) -> Photo:
        matches = [p for p in photos if p.image_path.name == filename]
        if not matches:
            raise typer.BadParameter(
                f"No photo named {filename!r} found in {photos_json}.", param_hint=f"--{role}"
            )
        return matches[0]

    front_photo = _find(front, "front")
    back_photo = _find(back, "back")
    interior_page_count = len(PdfReader(interior).pages)

    build_cover_pdf(
        front_photo,
        back_photo,
        output,
        interior_page_count=interior_page_count,
        book_title=config.book.title,
        book_subtitle=config.book.subtitle,
    )
    typer.echo(f"Wrote cover PDF to {output}")


@app.command(name="review-export")
def review_export(
    photos_json: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, help="Path to the photos.json produced by `import`."
        ),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path to write the review TSV to."),
    ] = Path("build/review.tsv"),
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Overwrite an existing review file instead of refusing to touch it."
        ),
    ] = False,
) -> None:
    """Generate a review.tsv for hand-editing and later feeding to `build
    --review-file`: photos ordered by timestamp (undated ones last),
    chapters auto-assigned by country, existing captions carried over,
    and a best-effort solo column -- see review_export.export_review_file
    for the exact rules. Uncaptioned photos are left blank in the tag
    column; writing a short descriptive tag for those requires actually
    looking at each photo, which this command has no way to do.
    """
    from photobook.review_export import export_review_file

    if output.exists() and not force:
        raise typer.BadParameter(
            f"{output} already exists -- pass --force to overwrite it, or a different "
            "--output path. Refusing by default since it may contain hand edits.",
            param_hint="--output",
        )

    photos = load_photos(photos_json)
    typer.echo("Reverse-geocoding photo locations for chapters (one-time ~10s cost)...")
    export_review_file(photos, output)
    typer.echo(f"Wrote review file with {len(photos)} photos to {output}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
