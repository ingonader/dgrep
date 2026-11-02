import re
from pathlib import Path

import pytest

from dgrep import file_discovery


def test_get_allowed_extensions_defaults_to_default_formats() -> None:
    allowed_extensions = file_discovery.get_allowed_extensions(None)

    assert file_discovery.is_allowed_extension(".md", allowed_extensions)
    assert file_discovery.is_allowed_extension(".DOCX", allowed_extensions)
    assert not file_discovery.is_allowed_extension(".doc", allowed_extensions)
    assert not file_discovery.is_allowed_extension(".py", allowed_extensions)


def test_get_allowed_extensions_accepts_patterns_without_defaults() -> None:
    allowed_extensions = file_discovery.get_allowed_extensions("py, docx?")

    assert file_discovery.is_allowed_extension(".py", allowed_extensions)
    assert file_discovery.is_allowed_extension(".doc", allowed_extensions)
    assert file_discovery.is_allowed_extension(".docx", allowed_extensions)
    assert not file_discovery.is_allowed_extension(".md", allowed_extensions)


def test_get_allowed_extensions_adds_to_defaults() -> None:
    allowed_extensions = file_discovery.get_allowed_extensions("+py")

    assert file_discovery.is_allowed_extension(".md", allowed_extensions)
    assert file_discovery.is_allowed_extension(".py", allowed_extensions)


def test_get_allowed_extensions_can_select_extensionless_files() -> None:
    allowed_extensions = file_discovery.get_allowed_extensions("txt,")

    assert file_discovery.is_allowed_extension("", allowed_extensions)
    assert file_discovery.is_allowed_extension(".txt", allowed_extensions)
    assert not file_discovery.is_allowed_extension(".md", allowed_extensions)


def test_get_allowed_extensions_rejects_invalid_regular_expressions() -> None:
    with pytest.raises(re.error):
        file_discovery.get_allowed_extensions("[")


def test_collect_files_recursively_filters_and_sorts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    paths = [
        tmp_path / "zeta.md",
        nested / "alpha.TXT",
        nested / "skip.py",
        nested / "draft-notes.md",
    ]
    for path in paths:
        path.touch()
    monkeypatch.setattr(file_discovery, "progress_enabled", lambda: False)

    found = file_discovery.collect_files(
        [str(tmp_path)],
        filename_pattern=re.compile(r"^(?!draft)"),
    )

    assert found == [paths[1].resolve(), paths[0].resolve()]


def test_collect_files_accepts_custom_extensions_and_extensionless_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain_text = tmp_path / "notes"
    script = tmp_path / "tool.py"
    excluded = tmp_path / "readme.md"
    for path in (plain_text, script, excluded):
        path.touch()
    monkeypatch.setattr(file_discovery, "progress_enabled", lambda: False)

    found = file_discovery.collect_files(
        [str(tmp_path)], formats="py,"
    )

    assert found == [plain_text.resolve(), script.resolve()]


def test_collect_files_deduplicates_overlapping_inputs_and_sorts_reverse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    first.touch()
    second.touch()
    monkeypatch.setattr(file_discovery, "progress_enabled", lambda: False)

    found = file_discovery.collect_files(
        [str(tmp_path), str(first)], sort_spec="ar"
    )

    assert found == [second.resolve(), first.resolve()]


def test_collect_files_warns_for_missing_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(file_discovery, "progress_enabled", lambda: False)
    missing = tmp_path / "missing"

    assert file_discovery.collect_files([str(missing)]) == []

    assert capsys.readouterr().err == f"Warning: not found: {missing}\n"
