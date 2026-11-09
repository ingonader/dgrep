import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from dgrep import output, text_matching


def _set_output_terminal_width(
    monkeypatch: pytest.MonkeyPatch, terminal_width: int
) -> None:
    monkeypatch.setattr(
        output.shutil,
        "get_terminal_size",
        lambda fallback: SimpleNamespace(columns=terminal_width),
    )


@pytest.mark.parametrize(
    ("expression", "multiline"),
    [
        (r"first\nsecond", True),
        ("first\nsecond", True),
        (r"literal\\ntext", False),
        ("single line", False),
    ],
)
def test_compile_search_pattern_selects_multiline_mode(
    expression: str, multiline: bool
) -> None:
    pattern = text_matching.compile_search_pattern(expression)

    assert bool(pattern.flags & re.MULTILINE) is multiline


@pytest.mark.parametrize(
    ("ranges", "expected"),
    [
        ([(5, 7), (1, 2), (3, 4), (10, 12)], [(1, 7), (10, 12)]),
        ([], []),
        ([(4, 4)], [(4, 4)]),
    ],
)
def test_merge_ranges(
    ranges: list[tuple[int, int]], expected: list[tuple[int, int]]
) -> None:
    assert text_matching.merge_ranges(ranges) == expected


def test_truncate_match_line_shows_centered_excerpts() -> None:
    line = "0123456789abcdefghij"

    assert (
        text_matching.truncate_match_line(line, re.compile(r"34|ef"), 6, "", "")
        == "...123456...cdefgh..."
    )


def test_truncate_match_line_keeps_long_matches_and_highlights() -> None:
    assert (
        text_matching.truncate_match_line(
            "0123456789abcdefghij", re.compile("3456789"), 4, "<", ">"
        )
        == "...<3456789>..."
    )

    assert (
        text_matching.truncate_match_line(
            "one hit two hit", re.compile("hit"), 20, "<", ">"
        )
        == "one <hit> two <hit>"
    )


def test_truncate_match_line_returns_empty_when_no_match() -> None:
    assert (
        text_matching.truncate_match_line(
            "nothing here", re.compile("missing"), 5, "", ""
        )
        == "..."
    )


@pytest.mark.parametrize(
    ("line", "matchlen", "expected"),
    [
        ("short", 5, "short"),
        ("long context line", 4, "long..."),
    ],
)
def test_truncate_context_line(line: str, matchlen: int, expected: str) -> None:
    assert text_matching.truncate_context_line(line, matchlen) == expected


def test_search_file_prints_matches_and_merged_context(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "fake.txt"
    _set_output_terminal_width(monkeypatch, terminal_width=40)
    monkeypatch.setattr(
        text_matching,
        "extract_text",
        lambda source: [
            "before",
            "needle one",
            "between",
            "needle two",
            "after",
        ],
    )

    count = text_matching.search_file(path, re.compile("needle"), before=1, after=1)

    captured = capsys.readouterr()
    assert count == 2
    assert captured.out == (
        "=" * 40 + "\n"
        f"\r{path.resolve().as_uri()} \n"
        "1- before\n"
        "2: needle one\n"
        "3- between\n"
        "4: needle two\n"
        "5- after\n"
        "---\n"
    )
    assert captured.err == ""


def test_search_file_matches_multiple_lines_and_highlights_each_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "fake.txt"
    _set_output_terminal_width(monkeypatch, terminal_width=40)
    monkeypatch.setattr(
        text_matching,
        "extract_text",
        lambda source: ["before", "start", "middle", "end", "after"],
    )

    count = text_matching.search_file(
        path,
        text_matching.compile_search_pattern(r"start\nmiddle\nend"),
        before=0,
        after=0,
        red="<",
        reset=">",
    )

    captured = capsys.readouterr()
    assert count == 3
    assert captured.out == (
        "=" * 40 + "\n"
        f"\r{path.resolve().as_uri()} \n"
        "2: <start>\n"
        "3: <middle>\n"
        "4: <end>\n"
        "---\n"
    )


def test_search_file_multiline_anchors_match_each_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "fake.txt"
    monkeypatch.setattr(
        text_matching,
        "extract_text",
        lambda source: ["first", "second", "third"],
    )

    count = text_matching.search_file(
        path,
        text_matching.compile_search_pattern(r"^second$\n^third$"),
        before=0,
        after=0,
    )

    captured = capsys.readouterr()
    assert count == 2
    assert "2: second\n3: third\n" in captured.out


def test_search_file_dot_does_not_match_newline(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        text_matching,
        "extract_text",
        lambda source: ["first", "second"],
    )

    assert (
        text_matching.search_file(
            tmp_path / "fake.txt",
            text_matching.compile_search_pattern("first.*second\n"),
            before=0,
            after=0,
        )
        == 0
    )
    assert capsys.readouterr().out == ""


def test_search_file_formats_archive_member_link(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "archive.zip"
    _set_output_terminal_width(monkeypatch, terminal_width=40)
    monkeypatch.setattr(text_matching, "extract_text", lambda source: ["fake match"])

    count = text_matching.search_file(
        path,
        re.compile("match"),
        before=0,
        after=0,
        red="<",
        reset=">",
        display_name="folder/member.txt",
        link_path=path,
    )

    captured = capsys.readouterr()
    assert count == 1
    assert captured.out == (
        "=" * 40 + "\n"
        f"\r{path.resolve().as_uri()} !/folder/member.txt\n"
        "1: fake <match>\n"
    )


def test_search_file_without_matches_prints_nothing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(text_matching, "extract_text", lambda source: ["fake text"])

    assert (
        text_matching.search_file(
            tmp_path / "fake.txt", re.compile("missing"), before=0, after=0
        )
        == 0
    )
    assert capsys.readouterr().out == ""


def test_search_file_reports_extraction_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def fail_extraction(source: Path) -> list[str]:
        raise OSError("fake read failure")

    monkeypatch.setattr(text_matching, "extract_text", fail_extraction)
    path = tmp_path / "fake.txt"

    assert text_matching.search_file(path, re.compile("needle"), before=0, after=0) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"Warning: cannot read {path}: fake read failure" in captured.err
