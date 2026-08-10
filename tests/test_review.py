from __future__ import annotations

from pathlib import Path

import pytest

from photobook.model import Photo
from photobook.review import ReviewFileError, load_review_file

_HEADER = "row_type\timage_path\tfilename\tdate\ttag\tchapter_title\n"


def _make_photo(name: str, *, caption: str | None = None, force_solo: bool | None = None) -> Photo:
    return Photo(
        image_path=Path(f"/album/{name}"),
        metadata_path=None,
        timestamp=None,
        timestamp_source="unknown",
        caption=caption,
        google_photos_url=None,
        width=800,
        height=600,
        orientation=1,
        edited=False,
        force_solo=force_solo,
    )


def _write_tsv(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "review.tsv"
    path.write_text(_HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_photo_rows_become_a_chapter_group_in_file_order(tmp_path: Path) -> None:
    a, b = _make_photo("a.jpg"), _make_photo("b.jpg")
    tsv = _write_tsv(
        tmp_path,
        [
            "chapter\t\t\t\t\tItaly",
            "photo\t/album/a.jpg\ta.jpg\t2020-01-01\t\t",
            "photo\t/album/b.jpg\tb.jpg\t2020-01-02\t\t",
        ],
    )

    groups = load_review_file(tsv, [a, b])

    assert groups == [("Italy", [a, b])]


def test_omitted_photo_is_excluded_not_appended(tmp_path: Path) -> None:
    # `b` exists in the photo list but isn't listed in the file at all --
    # must be dropped, not silently appended as a leftover.
    a, b = _make_photo("a.jpg"), _make_photo("b.jpg")
    tsv = _write_tsv(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t2020-01-01\t\t"])

    groups = load_review_file(tsv, [a, b])

    assert groups == [(None, [a])]


def test_chapter_row_sets_chapter_for_following_photos_until_next_chapter_row(
    tmp_path: Path,
) -> None:
    a, b, c = _make_photo("a.jpg"), _make_photo("b.jpg"), _make_photo("c.jpg")
    tsv = _write_tsv(
        tmp_path,
        [
            "chapter\t\t\t\t\tItaly",
            "photo\t/album/a.jpg\ta.jpg\t\t\t",
            "chapter\t\t\t\t\tFrance",
            "photo\t/album/b.jpg\tb.jpg\t\t\t",
            "photo\t/album/c.jpg\tc.jpg\t\t\t",
        ],
    )

    groups = load_review_file(tsv, [a, b, c])

    assert groups == [("Italy", [a]), ("France", [b, c])]


def test_photos_before_the_first_chapter_row_get_none(tmp_path: Path) -> None:
    a = _make_photo("a.jpg")
    tsv = _write_tsv(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t\t"])

    groups = load_review_file(tsv, [a])

    assert groups == [(None, [a])]


def test_unparenthesized_tag_becomes_the_photo_caption(tmp_path: Path) -> None:
    a = _make_photo("a.jpg", caption=None)
    tsv = _write_tsv(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\tA real caption\t"])

    (_, [photo]) = load_review_file(tsv, [a])[0]

    assert photo.caption == "A real caption"


def test_parenthesized_tag_is_not_applied_as_a_caption(tmp_path: Path) -> None:
    a = _make_photo("a.jpg", caption=None)
    tsv = _write_tsv(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t(garden gnomes)\t"])

    (_, [photo]) = load_review_file(tsv, [a])[0]

    assert photo.caption is None


def test_blank_tag_clears_an_existing_caption(tmp_path: Path) -> None:
    # review-export carries a real caption over into `tag` unparenthesized
    # -- if the user deletes it (leaving the cell blank), that's a
    # deliberate removal, not "leave the caption alone."
    a = _make_photo("a.jpg", caption="An old caption")
    tsv = _write_tsv(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t\t"])

    (_, [photo]) = load_review_file(tsv, [a])[0]

    assert photo.caption is None


def test_parenthesizing_a_previously_real_caption_also_clears_it(tmp_path: Path) -> None:
    a = _make_photo("a.jpg", caption="An old caption")
    tsv = _write_tsv(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t(An old caption)\t"])

    (_, [photo]) = load_review_file(tsv, [a])[0]

    assert photo.caption is None


def test_unknown_image_path_raises_with_line_number(tmp_path: Path) -> None:
    a = _make_photo("a.jpg")
    tsv = _write_tsv(tmp_path, ["photo\t/album/does-not-exist.jpg\tx.jpg\t\t\t"])

    with pytest.raises(ReviewFileError, match=r"review\.tsv:2.*does-not-exist"):
        load_review_file(tsv, [a])


def test_missing_required_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "review.tsv"
    path.write_text("image_path\ttag\n/album/a.jpg\thello\n", encoding="utf-8")

    with pytest.raises(ReviewFileError, match="missing required column"):
        load_review_file(path, [_make_photo("a.jpg")])


def test_invalid_row_type_raises(tmp_path: Path) -> None:
    a = _make_photo("a.jpg")
    tsv = _write_tsv(tmp_path, ["bogus\t/album/a.jpg\ta.jpg\t\t\t"])

    with pytest.raises(ReviewFileError, match="row_type must be"):
        load_review_file(tsv, [a])


def _write_tsv_with_solo_column(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "review.tsv"
    header = "row_type\timage_path\tfilename\tdate\ttag\tchapter_title\tsolo\n"
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_solo_column_true_forces_force_solo_true(tmp_path: Path) -> None:
    a = _make_photo("a.jpg")
    tsv = _write_tsv_with_solo_column(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t\t\ttrue"])

    (_, [photo]) = load_review_file(tsv, [a])[0]

    assert photo.force_solo is True


def test_solo_column_false_forces_force_solo_false(tmp_path: Path) -> None:
    a = _make_photo("a.jpg")
    tsv = _write_tsv_with_solo_column(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t\t\tfalse"])

    (_, [photo]) = load_review_file(tsv, [a])[0]

    assert photo.force_solo is False


def test_solo_column_blank_leaves_force_solo_unset(tmp_path: Path) -> None:
    a = _make_photo("a.jpg")
    tsv = _write_tsv_with_solo_column(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t\t\t"])

    (_, [photo]) = load_review_file(tsv, [a])[0]

    assert photo.force_solo is None


def test_solo_column_blank_clears_an_existing_force_solo_override(tmp_path: Path) -> None:
    # A blank cell means "apply the automatic decision," full stop -- it
    # must actively reset force_solo, not just leave whatever value the
    # input Photo already happened to carry untouched.
    a = _make_photo("a.jpg", force_solo=True)
    tsv = _write_tsv_with_solo_column(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t\t\t"])

    (_, [photo]) = load_review_file(tsv, [a])[0]

    assert photo.force_solo is None


def test_solo_column_absent_leaves_force_solo_unset(tmp_path: Path) -> None:
    # Backward compat: a review file written before this column existed
    # (no "solo" header at all) must still load fine.
    a = _make_photo("a.jpg")
    tsv = _write_tsv(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t\t"])

    (_, [photo]) = load_review_file(tsv, [a])[0]

    assert photo.force_solo is None


def test_solo_column_invalid_value_raises(tmp_path: Path) -> None:
    a = _make_photo("a.jpg")
    tsv = _write_tsv_with_solo_column(tmp_path, ["photo\t/album/a.jpg\ta.jpg\t\t\t\tmaybe"])

    with pytest.raises(ReviewFileError, match="solo column must be"):
        load_review_file(tsv, [a])
