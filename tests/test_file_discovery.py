import re
from pathlib import Path

import pytest

from dgrep import file_discovery
from dgrep.regex_utils import (
    DEFAULT_EXCLUDE_DIRS_SPEC,
    compile_regex_list,
    is_excluded_directory_path,
)


def test_compile_regex_list_splits_and_strips_entries() -> None:
    patterns = compile_regex_list(" renv , venv ")

    assert [pattern.pattern for pattern in patterns] == ["renv", "venv"]


def test_default_exclusions_match_directory_segments() -> None:
    patterns = compile_regex_list(DEFAULT_EXCLUDE_DIRS_SPEC)

    assert is_excluded_directory_path("src/.git/hooks", patterns)
    assert is_excluded_directory_path("renv/library/R", patterns)
    assert not is_excluded_directory_path("src/targeted", patterns)
    assert is_excluded_directory_path(
        "renv", [re.compile(r"^renv$")]
    )


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


def test_collect_files_excludes_matching_directories_and_prunes_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    included = tmp_path / "source" / "notes.md"
    excluded = tmp_path / "renv" / "library" / "notes.md"
    included.parent.mkdir()
    excluded.parent.mkdir(parents=True)
    included.touch()
    excluded.touch()
    visited: list[Path] = []
    walk = file_discovery.os.walk

    def tracking_walk(root: str | Path):
        for current_root, dirnames, filenames in walk(root):
            visited.append(Path(current_root))
            yield current_root, dirnames, filenames

    monkeypatch.setattr(file_discovery.os, "walk", tracking_walk)
    monkeypatch.setattr(file_discovery, "progress_enabled", lambda: False)

    found = file_discovery.collect_files(
        [str(tmp_path)],
        exclude_patterns=[re.compile(r"/renv/library/")],
    )

    assert found == [included.resolve()]
    assert excluded.parent not in visited


def test_collect_files_excludes_a_matching_search_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    excluded_root = tmp_path / "venv"
    excluded_root.mkdir()
    (excluded_root / "notes.md").touch()
    monkeypatch.setattr(file_discovery, "progress_enabled", lambda: False)

    assert file_discovery.collect_files(
        [str(excluded_root)],
        exclude_patterns=[re.compile("venv")],
    ) == []


def test_collect_files_excludes_explicit_files_in_matching_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    excluded = tmp_path / "renv" / "library" / "notes.md"
    excluded.parent.mkdir(parents=True)
    excluded.touch()
    monkeypatch.setattr(file_discovery, "progress_enabled", lambda: False)

    assert file_discovery.collect_files(
        [str(excluded)],
        exclude_patterns=[re.compile("renv")],
    ) == []


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
