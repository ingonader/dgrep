from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from ldgrep import output


class TerminalStream(StringIO):
    def isatty(self) -> bool:
        return True


def _enable_search_progress(
    monkeypatch: pytest.MonkeyPatch,
    stderr: StringIO,
    terminal_width: int,
) -> None:
    monkeypatch.setattr(output, "sys", SimpleNamespace(stderr=stderr))
    monkeypatch.setattr(output, "progress_enabled", lambda: True)
    monkeypatch.setattr(
        output.shutil,
        "get_terminal_size",
        lambda fallback: SimpleNamespace(columns=terminal_width),
    )


def test_progress_is_disabled_when_stderr_is_not_a_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        output,
        "sys",
        SimpleNamespace(stdout=StringIO(), stderr=StringIO()),
    )

    assert not output.progress_enabled()


def test_progress_is_enabled_when_stderr_is_a_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        output,
        "sys",
        SimpleNamespace(stdout=StringIO(), stderr=TerminalStream()),
    )

    assert output.progress_enabled()


def test_hyperlink_formats_path_as_terminal_uri(tmp_path: Path) -> None:
    path = tmp_path / "fake document.txt"

    assert output.hyperlink(path) == f"{path.resolve().as_uri()} "


def test_print_file_prints_separator_and_hyperlink(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "fake document.txt"
    monkeypatch.setattr(
        output.shutil,
        "get_terminal_size",
        lambda fallback: SimpleNamespace(columns=12),
    )

    output.print_file(path, "display name")

    assert capsys.readouterr().out == (
        "=" * 12 + "\n" + f"\r{output.hyperlink(path)}display name\n"
    )


def test_print_error_duplicates_to_redirected_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = StringIO()
    stderr = TerminalStream()
    monkeypatch.setattr(output, "sys", SimpleNamespace(stdout=stdout, stderr=stderr))

    output.print_error("Warning: failed")

    assert stdout.getvalue() == "Warning: failed\n"
    assert stderr.getvalue() == "Warning: failed\n"


def test_print_error_does_not_duplicate_when_stderr_is_not_a_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = StringIO()
    stderr = StringIO()
    monkeypatch.setattr(output, "sys", SimpleNamespace(stdout=stdout, stderr=stderr))

    output.print_error("Warning: failed")

    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Warning: failed\n"


def test_show_search_progress_writes_labeled_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = StringIO()
    _enable_search_progress(monkeypatch, stderr, terminal_width=40)

    output.show_search_progress(1, 4, "file.txt", bar_width=4, label="scan:")

    assert stderr.getvalue() == ("\rscan:[#...]  25.0% file.txt").ljust(39)


def test_show_search_progress_handles_zero_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = StringIO()
    _enable_search_progress(monkeypatch, stderr, terminal_width=30)

    output.show_search_progress(0, 0, 42, bar_width=4)

    assert stderr.getvalue() == ("\r[....]   0.0% 42").ljust(29)


def test_show_search_progress_truncates_long_filename_from_the_left(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = StringIO()
    _enable_search_progress(monkeypatch, stderr, terminal_width=25)

    output.show_search_progress(1, 1, "abcdefghijklmno", bar_width=2)

    assert stderr.getvalue() == ("\r[##] 100.0% ...hijklmno").ljust(24)


def test_show_search_progress_clips_filename_on_narrow_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = StringIO()
    _enable_search_progress(monkeypatch, stderr, terminal_width=16)

    output.show_search_progress(1, 1, "filename", bar_width=2)

    assert stderr.getvalue() == "\r[##] 100.0% fi"


def test_show_search_progress_writes_nothing_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = StringIO()
    monkeypatch.setattr(output, "sys", SimpleNamespace(stderr=stderr))
    monkeypatch.setattr(output, "progress_enabled", lambda: False)

    output.show_search_progress(1, 1, "file.txt")

    assert stderr.getvalue() == ""
