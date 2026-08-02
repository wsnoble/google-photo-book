from pathlib import Path
from typing import Annotated

import typer

from photobook import __version__
from photobook.config import load_config
from photobook.importer import scan_album
from photobook.validation import summarize, write_photos_json, write_report_csv, write_report_txt

app = typer.Typer(help="Build a Blurb-ready photo book from a Google Takeout album export.")


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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
