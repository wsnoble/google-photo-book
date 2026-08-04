import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from photobook import __version__
from photobook.cli import _load_manual_order, app

runner = CliRunner()


def test_version_command_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_load_manual_order_returns_none_when_no_path() -> None:
    assert _load_manual_order(None) is None


def test_load_manual_order_accepts_list_of_strings(tmp_path: Path) -> None:
    path = tmp_path / "order.json"
    path.write_text(json.dumps(["/a.jpg", "/b.jpg"]))

    assert _load_manual_order(path) == ["/a.jpg", "/b.jpg"]


def test_load_manual_order_rejects_non_list(tmp_path: Path) -> None:
    path = tmp_path / "order.json"
    path.write_text(json.dumps({"not": "a list"}))

    with pytest.raises(typer.BadParameter):
        _load_manual_order(path)


def test_load_manual_order_rejects_non_string_items(tmp_path: Path) -> None:
    path = tmp_path / "order.json"
    path.write_text(json.dumps(["/a.jpg", 42]))

    with pytest.raises(typer.BadParameter):
        _load_manual_order(path)


def test_load_manual_order_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "order.json"
    path.write_text("not json{")

    with pytest.raises(typer.BadParameter):
        _load_manual_order(path)
