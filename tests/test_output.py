from io import StringIO
from types import SimpleNamespace

import pytest

from dgrep import output


class TerminalStream(StringIO):
    def isatty(self) -> bool:
        return True


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


def test_print_error_duplicates_to_redirected_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = StringIO()
    stderr = TerminalStream()
    monkeypatch.setattr(
        output, "sys", SimpleNamespace(stdout=stdout, stderr=stderr)
    )

    output.print_error("Warning: failed")

    assert stdout.getvalue() == "Warning: failed\n"
    assert stderr.getvalue() == "Warning: failed\n"


def test_print_error_does_not_duplicate_when_stderr_is_not_a_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = StringIO()
    stderr = StringIO()
    monkeypatch.setattr(
        output, "sys", SimpleNamespace(stdout=stdout, stderr=stderr)
    )

    output.print_error("Warning: failed")

    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Warning: failed\n"
