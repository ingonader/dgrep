import os
import re
import sys
from pathlib import Path

from .output import print_error, progress_enabled
from .regex_utils import (
    find_excluded_directory_path,
    parse_regex_spec,
)
from .archive_handling import (
    is_allowed_extension,
    show_candidate_id_progress,
    sort_paths,
)

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".doc",
    ".docx",
    ".odt",
    ".odp",
    ".ppt",
    ".pptx",
    ".xlsx",
    ".xls",
    ".ods",
}

DEFAULT_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".odt",
    ".odp",
    ".pptx",
}

VALID_FORMATS = {extension.lstrip(".") for extension in SUPPORTED_EXTENSIONS}


def get_allowed_extensions(
    extension_spec: str | None,
) -> list[re.Pattern[str]]:
    """Compile extension patterns, including default modifiers.

    Args:
        extension_spec: Comma-separated regular expressions matched against
            file suffixes. A leading `+` adds patterns to the defaults, and a
            leading `^` removes matching extensions from the defaults. Empty
            entries select files without an extension for ordinary and `+`
            specifications. `None` selects only the defaults.

    Returns:
        Compiled regular expressions for matching file suffixes, including the
        empty suffix when extensionless files are selected.
    """
    modifier, extension_patterns = parse_regex_spec(
        extension_spec,
        re.IGNORECASE,
        empty_pattern=r"^$",
    )
    if extension_spec is not None and modifier is None:
        return extension_patterns

    allowed_extensions = []
    for extension in DEFAULT_EXTENSIONS:
        if modifier != "^" or not is_allowed_extension(
            extension, extension_patterns
        ):
            allowed_extensions.append(
                re.compile(re.escape(extension), re.IGNORECASE)
            )
    if modifier != "^":
        allowed_extensions.extend(extension_patterns)

    return allowed_extensions


def collect_files(
    inputs: list[str],
    formats: str | None = None,
    filename_pattern: re.Pattern[str] | None = None,
    sort_spec: str = "t",
    exclude_patterns: list[re.Pattern[str]] | None = None,
    excluded_paths: set[str] | None = None,
) -> list[Path]:
    """Find unique files matching extension, name, and directory filters.

    Directories are searched recursively. Nonexistent paths are reported to
    standard error and skipped.

    Args:
        inputs: File and directory paths to search.
        formats: Comma-separated extension regular expressions. A leading `+`
            adds to the default extensions, and a leading `^` removes matching
            extensions from the defaults. Empty entries select files without
            an extension. `None` selects the default extensions.
        filename_pattern: Optional regular expression matched against each
            filename stem.
        sort_spec: Sort key (`a`, `c`, `t`, or `u`) and optional reverse flag
            (`r`).
        exclude_patterns: Optional expressions matched against relative
            directory paths before they are traversed.
        excluded_paths: Optional set populated with paths excluded by these
            directory patterns.

    Returns:
        Resolved matching file paths in the requested order.
    """

    allowed_extensions = get_allowed_extensions(formats)
    exclude_patterns = exclude_patterns or []

    files = set()

    for item in inputs:
        path = Path(item).expanduser()

        if not path.exists():
            print_error(f"Warning: not found: {item}")
            continue

        if path.is_file():
            relative_path = Path(os.path.relpath(path.absolute(), Path.cwd()))
            excluded_directory = find_excluded_directory_path(
                relative_path.parent, exclude_patterns
            )
            if excluded_directory is not None and excluded_paths is not None:
                excluded_paths.add(str(excluded_directory))
            if (
                excluded_directory is None
                and is_allowed_extension(path.suffix, allowed_extensions)
                and (
                    filename_pattern is None
                    or filename_pattern.search(path.stem)
                )
            ):
                files.add(path.resolve())
                file_cnt = len(files)
                show_candidate_id_progress(file_cnt, "files")
            continue

        if path.is_dir():
            search_root = path.absolute()
            excluded_root = find_excluded_directory_path(path.name, exclude_patterns)
            if excluded_root is not None:
                if excluded_paths is not None:
                    excluded_paths.add(
                        str(Path(os.path.relpath(search_root, Path.cwd())))
                    )
            else:
                for current_root, dirnames, filenames in os.walk(search_root):
                    current_path = Path(current_root)
                    relative_root = current_path.relative_to(search_root)
                    kept_dirnames = []
                    for dirname in dirnames:
                        excluded_directory = find_excluded_directory_path(
                            relative_root / dirname, exclude_patterns
                        )
                        if excluded_directory is None:
                            kept_dirnames.append(dirname)
                        elif excluded_paths is not None:
                            excluded_paths.add(
                                str(
                                    Path(os.path.relpath(search_root, Path.cwd()))
                                    / Path(str(excluded_directory))
                                )
                            )
                    dirnames[:] = kept_dirnames
                    for filename in filenames:
                        candidate = current_path / filename
                        if (
                            candidate.is_file()
                            and is_allowed_extension(
                                candidate.suffix, allowed_extensions
                            )
                            and (
                                filename_pattern is None
                                or filename_pattern.search(candidate.stem)
                            )
                        ):
                            files.add(candidate.resolve())
                            file_cnt = len(files)
                            show_candidate_id_progress(file_cnt, "files")

    if progress_enabled():
        print("\r\033[K", end="", file=sys.stderr)
    return sort_paths(files, sort_spec)
