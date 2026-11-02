import sys
import re
from pathlib import Path
from .output import print_error, progress_enabled

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


from .archive_handling import (
    is_allowed_extension,
    show_candidate_id_progress,
    sort_paths,
)


def get_allowed_extensions(
    extension_spec: str | None,
) -> list[re.Pattern[str]]:
    """Compile extension patterns, including additive and extensionless forms.

    Args:
        extension_spec: Comma-separated regular expressions matched against
            file suffixes. A leading `+` includes the default extensions, and
            empty entries select files without an extension. `None` selects
            only the defaults.

    Returns:
        Compiled regular expressions for matching file suffixes, including the
        empty suffix when extensionless files are selected.
    """
    include_defaults = extension_spec is None or extension_spec.startswith("+")
    allowed_extensions = (
        [
            re.compile(re.escape(extension), re.IGNORECASE)
            for extension in DEFAULT_EXTENSIONS
        ]
        if include_defaults
        else []
    )

    if extension_spec is not None:
        if include_defaults:
            extension_spec = extension_spec[1:]
        for extension in extension_spec.split(","):
            extension = extension.strip()
            allowed_extensions.append(
                re.compile(extension if extension else r"^$", re.IGNORECASE)
            )

    return allowed_extensions


def collect_files(
    inputs: list[str],
    formats: str | None = None,
    filename_pattern: re.Pattern[str] | None = None,
    sort_spec: str = "a",
) -> list[Path]:
    """Find unique files matching extension and optional filename filters.

    Directories are searched recursively. Nonexistent paths are reported to
    standard error and skipped.

    Args:
        inputs: File and directory paths to search.
        formats: Comma-separated extension regular expressions. A leading `+`
            adds to the default extensions, and empty entries select files
            without an extension. `None` selects the default extensions.
        filename_pattern: Optional regular expression matched against each
            filename stem.
        sort_spec: Sort key (`a`, `c`, `t`, or `u`) and optional reverse flag
            (`r`).

    Returns:
        Resolved matching file paths in the requested order.
    """

    allowed_extensions = get_allowed_extensions(formats)

    files = set()

    for item in inputs:
        path = Path(item).expanduser()

        if not path.exists():
            print_error(f"Warning: not found: {item}")
            continue

        if path.is_file():
            if is_allowed_extension(path.suffix, allowed_extensions) and (
                filename_pattern is None or filename_pattern.search(path.stem)
            ):
                files.add(path.resolve())
                file_cnt = len(files)
                show_candidate_id_progress(file_cnt, "files")
            continue

        if path.is_dir():
            for candidate in path.rglob("*"):
                if (
                    candidate.is_file()
                    and is_allowed_extension(candidate.suffix, allowed_extensions)
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
