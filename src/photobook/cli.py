import json
from pathlib import Path
from typing import Annotated

import typer

from photobook import __version__
from photobook.config import load_config
from photobook.importer import scan_album
from photobook.model import load_photos
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
) -> None:
    """Render the photo book: landscape/panorama/square one per page, portraits
    paired two-per-page, captions below when present. Page size/bleed are
    provisional pending the Blurb spec lookup (Milestone 4).
    """
    # Imported lazily: this pulls in WeasyPrint, which needs system libraries
    # (pango) not required by the other commands.
    from photobook.render import build_book_pdf

    config = load_config(config_path)
    photos = load_photos(photos_json)
    order = _load_manual_order(manual_order)
    build_book_pdf(
        photos,
        output,
        book_title=config.book.title,
        manual_order=order,
        guess_leftover_positions=guess_leftover_positions,
    )
    typer.echo(f"Wrote book PDF with {len(photos)} photos to {output}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
