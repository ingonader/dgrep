import argparse
import re
from pathlib import Path

import pytest

from dgrep import dgrep


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("a", "a"),
        ("c", "c"),
        ("t", "t"),
        ("u", "u"),
        ("ar", "ar"),
        ("ra", "ra"),
        ("tr", "tr"),
        ("r", "ar"),
    ],
)
def test_parse_sort_spec_accepts_valid_values(value: str, expected: str) -> None:
    assert dgrep.parse_sort_spec(value) == expected


@pytest.mark.parametrize("value", ["", "x", "aa", "rr", "ac", "arx", "ca"])
def test_parse_sort_spec_rejects_invalid_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        dgrep.parse_sort_spec(value)


def _prepare_cli(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr(dgrep.sys, "argv", ["dgrep", *args])
    monkeypatch.setattr(dgrep, "configure_logging", lambda: None)
    monkeypatch.setattr(dgrep, "configure_colors", lambda color: ("<", ">"))
    monkeypatch.setattr(dgrep, "progress_enabled", lambda: False)
    monkeypatch.setattr(dgrep, "show_search_progress", lambda *args, **kwargs: None)


@pytest.mark.parametrize(
    ("arguments", "expected_message"),
    [
        (["[", "input"], "Invalid regular expression:"),
        (["needle", "input", "--filename", "["], "Invalid filename regular expression:"),
        (["needle", "input", "--ext", "["], "Invalid extension regular expression:"),
        (["needle", "input", "-B", "-1"], "Context values must be non-negative"),
        (["needle", "input", "-l", "0"], "Match length must be a positive integer"),
    ],
)
def test_run_rejects_invalid_arguments(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    expected_message: str,
) -> None:
    _prepare_cli(monkeypatch, *arguments)

    with pytest.raises(SystemExit) as exc_info:
        dgrep._run()

    assert exc_info.value.code == 2
    assert expected_message in capsys.readouterr().err


def test_run_searches_ordinary_files_with_parsed_options(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    calls: list[tuple[Path, re.Pattern[str], int, int, str, str, int | None]] = []
    collection: dict[str, object] = {}

    def collect_files(
        paths: list[str],
        formats: str | None,
        filename_pattern: re.Pattern[str] | None,
        sort_spec: str,
    ) -> list[Path]:
        collection.update(
            paths=paths, formats=formats, filename_pattern=filename_pattern,
            sort_spec=sort_spec,
        )
        return [first, second]

    def search_file(
        path: Path,
        pattern: re.Pattern[str],
        before: int,
        after: int,
        red: str,
        reset: str,
        matchlen: int | None,
    ) -> int:
        calls.append((path, pattern, before, after, red, reset, matchlen))
        return 1 if path == first else 0

    _prepare_cli(
        monkeypatch,
        "Needle",
        str(tmp_path),
        "--ignore-case",
        "-B",
        "1",
        "-A",
        "2",
        "-C",
        "3",
        "-l",
        "8",
        "-e",
        "+py",
        "-f",
        "report",
        "--sort",
        "tr",
        "--color",
        "always",
    )
    monkeypatch.setattr(dgrep, "collect_files", collect_files)
    monkeypatch.setattr(dgrep, "search_file", search_file)

    assert dgrep._run() == 0

    assert collection["paths"] == [str(tmp_path)]
    assert collection["formats"] == "+py"
    assert collection["sort_spec"] == "tr"
    filename_pattern = collection["filename_pattern"]
    assert isinstance(filename_pattern, re.Pattern)
    assert filename_pattern.pattern == "report"
    assert filename_pattern.flags & re.IGNORECASE
    assert [call[0] for call in calls] == [first, second]
    assert all(call[1].pattern == "Needle" for call in calls)
    assert all(call[1].flags & re.IGNORECASE for call in calls)
    assert all(call[2:] == (3, 3, "<", ">", 8) for call in calls)
    captured = capsys.readouterr()
    assert "Searching 2 files... (not searching archives)" in captured.out
    assert "Searched 2 files (archives excluded by user)." in captured.out


def test_run_returns_failure_when_no_supported_files_are_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare_cli(monkeypatch, "needle", "input")
    monkeypatch.setattr(dgrep, "collect_files", lambda *args: [])

    assert dgrep._run() == 1
    assert capsys.readouterr().err == "No supported files found.\n"


def test_run_searches_matching_archive_members(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    archive = tmp_path / "documents.zip"
    member = "folder/needle.md"
    search_calls: list[tuple[Path, str | None, Path | None]] = []

    def copy_member(
        archive_path: Path, archive_type: str, member_name: str, destination
    ) -> None:
        assert archive_path == archive
        assert archive_type == "zip"
        assert member_name == member
        destination.write(b"archive text")

    def search_file(
        path: Path,
        pattern: re.Pattern[str],
        before: int,
        after: int,
        red: str,
        reset: str,
        matchlen: int | None,
        *,
        display_name: str | None = None,
        link_path: Path | None = None,
    ) -> int:
        assert path.read_bytes() == b"archive text"
        search_calls.append((path, display_name, link_path))
        return 1

    _prepare_cli(monkeypatch, "needle", str(archive), "--include-archives")
    monkeypatch.setattr(dgrep, "collect_files", lambda *args: [])
    monkeypatch.setattr(dgrep, "collect_archives", lambda *args: [archive])
    monkeypatch.setattr(
        dgrep, "archive_member_names", lambda path: ("zip", [member, "ignored.bin"])
    )
    monkeypatch.setattr(dgrep, "copy_archive_member", copy_member)
    monkeypatch.setattr(dgrep, "search_file", search_file)

    assert dgrep._run() == 0

    assert len(search_calls) == 1
    searched_path, display_name, link_path = search_calls[0]
    assert searched_path.suffix == ".md"
    assert display_name == member
    assert link_path == archive
    captured = capsys.readouterr()
    assert "Found 0 files, and 1 archives containing another 1 files..." in captured.out
    assert "Searched 0 files, and 1 archives containing another 1 files." in captured.out


def test_run_warns_and_continues_when_archive_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    archive = tmp_path / "broken.zip"
    _prepare_cli(monkeypatch, "needle", str(archive), "--include-archives")
    monkeypatch.setattr(dgrep, "collect_files", lambda *args: [])
    monkeypatch.setattr(dgrep, "collect_archives", lambda *args: [archive])

    def fail_read(path: Path) -> tuple[str, list[str]]:
        raise OSError("broken archive")

    monkeypatch.setattr(dgrep, "archive_member_names", fail_read)

    assert dgrep._run() == 1

    captured = capsys.readouterr()
    assert f"Warning: cannot read archive {archive}: broken archive" in captured.err
    assert "Searched 0 files, and 1 archives containing another 0 files." in captured.out


def test_main_returns_run_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dgrep, "_run", lambda: 7)

    assert dgrep.main() == 7


def test_main_reports_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors: list[str] = []

    def interrupt() -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(dgrep, "_run", interrupt)
    monkeypatch.setattr(dgrep, "print_error", errors.append)

    assert dgrep.main() == 130
    assert errors == ["Interrupted by user"]
