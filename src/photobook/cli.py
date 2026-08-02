import typer

from photobook import __version__

app = typer.Typer(help="Build a Blurb-ready photo book from a Google Takeout album export.")


@app.callback()
def callback() -> None:
    """photobook: convert a Google Takeout album export into a Blurb-ready PDF."""


@app.command()
def version() -> None:
    """Print the installed photobook version."""
    typer.echo(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
