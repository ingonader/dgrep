#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path
import tempfile

import logging
import warnings

from .archive_handling import (
    archive_member_names,
    collect_archives,
    copy_archive_member,
    is_searchable_archive_member,
)
from .file_discovery import (
    SUPPORTED_EXTENSIONS,
    DEFAULT_EXTENSIONS,
    get_allowed_extensions,
    collect_files,
)
from .regex_utils import DEFAULT_EXCLUDE_DIRS_SPEC, compile_exclude_patterns
from .output import (
    print_error,
    progress_enabled,
    show_search_progress,
    configure_colors,
)
from .text_matching import compile_search_pattern, search_file


def configure_logging():
    """Reduce warning noise from PDF extraction dependencies.

    The command-line output is intended for search results, so warnings emitted
    by pypdf are suppressed while errors remain visible.
    """
    # Keep third-party parser warnings from obscuring search output.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", module=r"pypdf(\.|$)")


def parse_sort_spec(value: str) -> str:
    """Validate and normalize a candidate-file sort specification.

    The specification must contain one sort key (`a`, `c`, `t`, or `u`) and may
    include `r` to reverse the order. A value of `r` alone is normalized to
    `ar`, meaning reverse alphabetical order.

    Args:
        value: Sort key and optional reverse flag supplied on the command line.

    Returns:
        The validated sort specification, with `r` normalized to `ar` when
        provided alone.

    Raises:
        argparse.ArgumentTypeError: If the value contains an unsupported,
            repeated, or conflicting option.
    """
    if (
        not value
        or any(option not in "actur" for option in value)
        or len(set(value)) != len(value)
        or sum(option in "actu" for option in value) > 1
    ):
        raise argparse.ArgumentTypeError(
            "sort must contain one of 'a', 'c', 't', or 'u', optionally with 'r'"
        )

    if not any(option in "actu" for option in value):
        if value == "r":
            return "ar"
        raise argparse.ArgumentTypeError(
            "sort must contain one of 'a', 'c', 't', or 'u', optionally with 'r'"
        )

    return value


class DgrepArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print_error(self.format_usage().rstrip("\n"))
        print_error(f"{self.prog}: error: {message}")
        self.exit(2)


def _run() -> int:
    """Run the command-line document search and return its process status.

    The command parses search options, discovers matching documents and
    optionally archive members, prints matching lines with context, and reports
    progress on standard error.

    Returns:
        `0` when at least one matching line is found, otherwise `1`.

    Raises:
        SystemExit: For invalid command-line arguments or invalid regular
            expressions, as handled by :mod:`argparse`.
    """
    configure_logging()

    parser = DgrepArgumentParser(
        description=(
            "Search "
            + ", ".join([i[1:] for i in SUPPORTED_EXTENSIONS])
            + " as well as any other plain-text files "
            + "using regular expressions."
        )
    )

    parser.add_argument(
        "pattern",
        help="Regular expression to search for",
    )

    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to search (default: current directory)",
    )

    parser.add_argument(
        "-i",
        "--ignore-case",
        action="store_true",
        help="Ignore case distinctions",
    )

    parser.add_argument(
        "-a",
        "--include-archives",
        action="store_true",
        help="Search supported archive files after searching ordinary files",
    )

    parser.add_argument(
        "-B",
        "--before-context",
        type=int,
        default=0,
        help="Number of context lines before each match",
    )

    parser.add_argument(
        "-A",
        "--after-context",
        type=int,
        default=0,
        help="Number of context lines after each match",
    )

    parser.add_argument(
        "-C",
        "--context",
        type=int,
        default=None,
        help="Number of context lines on both sides",
    )

    parser.add_argument(
        "-l",
        "--matchlen",
        type=int,
        default=None,
        metavar="CHARS",
        help="Limit each match excerpt to CHARS, centered on the match",
    )

    parser.add_argument(
        "-e",
        "--ext",
        type=str,
        default=None,
        metavar="EXTENSIONS",
        help=(
            "Comma-separated extension regexes (e.g., 'py,R,java' or 'docx?|xlsx?'); "
            + "a leading '+' adds to the defaults (e.g., '+py,sh'), a leading '^' "
            + "removes matching defaults (e.g., '^pdf,docx'), and empty entries "
            + "(e.g., 'py,') select extensionless files. Patterns match the suffix "
            + "with or without its leading dot. "
            + "Defaults: '"
            + ",".join([i[1:] for i in DEFAULT_EXTENSIONS])
            + "'; '"
            + ",".join([i[1:] for i in (SUPPORTED_EXTENSIONS - DEFAULT_EXTENSIONS)])
            + "' must be explicitly requested."
        ),
    )

    parser.add_argument(
        "-f",
        "--filename",
        metavar="REGEX",
        help="Only search files whose name without its extension matches this regex",
    )

    parser.add_argument(
        "-x",
        "--exclude",
        default=None,
        metavar="REGEXES",
        help=(
            "Comma-separated regular expressions (commas cannot appear inside "
            + "an expression) matched against relative "
            + "directory paths; matching directories and their contents are "
            + "excluded. A leading '+' adds patterns to the defaults, and a "
            + "leading '^' removes matching defaults; otherwise this replaces "
            + "the defaults. "
            + "Defaults: '"
            + DEFAULT_EXCLUDE_DIRS_SPEC
            + "'. Paths excluded during discovery are summarized on standard "
            + "output."
        ),
    )

    parser.add_argument(
        "--sort",
        type=parse_sort_spec,
        default="a",
        metavar="KEY",
        help=(
            "Sort candidates by resolved path (a, default), change time (c), "
            "modification time (t), or access time (u); add r to reverse "
            "the order (e.g. tr)"
        ),
    )

    parser.add_argument(
        "-c",
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help=("Colorize matching text: " "auto (default), always, or never."),
    )
    # Parse and normalize command-line options before discovering input files.
    args = parser.parse_args()

    # for interactive debugging:
    # args = parser.parse_args(["-a", "ishmael", str(Path(os.getcwd()).parent.parent)])

    red, reset = configure_colors(args.color)

    before = args.before_context
    after = args.after_context

    # The combined context option overrides the individual before/after values.
    if args.context is not None:
        before = after = args.context

    if before < 0 or after < 0:
        parser.error("Context values must be non-negative")

    if args.matchlen is not None and args.matchlen < 1:
        parser.error("Match length must be a positive integer")

    # Compile all expressions up front so invalid patterns fail before searching.
    try:
        pattern = compile_search_pattern(args.pattern, args.ignore_case)
    except re.error as exc:
        parser.error(f"Invalid regular expression: {exc}")

    filename_pattern = None
    if args.filename is not None:
        try:
            filename_pattern = re.compile(
                args.filename, re.IGNORECASE if args.ignore_case else 0
            )
        except re.error as exc:
            parser.error(f"Invalid filename regular expression: {exc}")

    try:
        allowed_extensions = get_allowed_extensions(args.ext)
    except re.error as exc:
        parser.error(f"Invalid extension regular expression: {exc}")

    try:
        exclude_patterns = compile_exclude_patterns(
            args.exclude,
            re.IGNORECASE if args.ignore_case else 0,
        )
    except re.error as exc:
        parser.error(f"Invalid directory exclusion regular expression: {exc}")

    excluded_paths: set[str] = set()

    # Discover ordinary files and archives separately because their contents
    # require different extraction paths.
    files = collect_files(
        args.paths,
        args.ext,
        filename_pattern,
        args.sort,
        exclude_patterns,
        excluded_paths,
    )
    files_unique_extensions = {path.suffix for path in files}
    archives = (
        collect_archives(
            args.paths,
            filename_pattern,
            args.sort,
            exclude_patterns,
            excluded_paths,
        )
        if args.include_archives
        else []
    )

    # Filter archive members with the same extension policy used for normal files.
    archive_members = []
    for archive_path in archives:
        try:
            archive_type, member_names = archive_member_names(archive_path)
        except Exception as exc:
            print_error(f"\nWarning: cannot read archive {archive_path}: {exc}")
            continue

        compressed_stream = archive_type == "compressed"
        archive_members.extend(
            (archive_path, archive_type, member_name, compressed_stream)
            for member_name in member_names
            if is_searchable_archive_member(
                member_name,
                allowed_extensions,
                filename_pattern,
                compressed_stream,
                exclude_patterns,
                excluded_paths,
                archive_path,
            )
        )

    if excluded_paths:
        paths = ", ".join(sorted(excluded_paths))
        print(f"Excluded {len(excluded_paths)} matching paths: {paths}")

    if not files and not archives:
        print_error("No supported files found.")
        return 1

    # get filenames from archives, and their extentions:
    archive_members_filenames = [Path(i[2]) for i in archive_members]
    archive_members_unique_extensions = {i.suffix for i in archive_members_filenames}
    unique_extensions = files_unique_extensions | archive_members_unique_extensions
    unique_extensions_str = ",".join([i[1:] for i in unique_extensions])

    # Print number of files, and number of archives and their content-files.
    files_searched = 0
    files_total = len(files)
    if args.include_archives:
        print(
            f"Found {files_total} files, and {len(archives)} archives containing another {len(archive_members)} files..."
        )
        archive_note = ""
    else:
        archive_note = " (not searching archives)"
    print(f"Matched extentions in candidate files: {unique_extensions_str}")
    print(f"Searching {files_total} files...{archive_note}")

    total_matches = 0

    # Search ordinary files first, updating progress after each completed file.
    for path in files:
        total_matches += search_file(
            path,
            pattern,
            before,
            after,
            red,
            reset,
            args.matchlen,
        )
        files_searched += 1
        show_search_progress(
            files_searched,
            files_total,
            path,
            bar_width=20,
            label="Files " if args.include_archives else "",
        )

    # Print newline on stderr for correct printing afterwards.
    if progress_enabled():
        print(file=sys.stderr)

    if args.include_archives:
        if files:
            if progress_enabled():
                print(file=sys.stderr)
        else:
            show_search_progress(0, 0, "No ordinary files", label="Files ")
            if progress_enabled():
                print(file=sys.stderr)
        print(f"Searching {len(archive_members)} files in archives...")

        # Extract each selected member to a temporary file before reusing search_file.
        if archive_members:
            with tempfile.TemporaryDirectory(prefix="dgrep_archive_") as temp_dir:
                temp_root = Path(temp_dir)
                for index, (archive_path, archive_type, member_name, _) in enumerate(
                    archive_members, start=1
                ):
                    member_path = temp_root / f"member{Path(member_name).suffix}"
                    display_name = f"{archive_path}!/{member_name}"
                    try:
                        with member_path.open("wb") as destination:
                            copy_archive_member(
                                archive_path,
                                archive_type,
                                member_name,
                                destination,
                            )
                        total_matches += search_file(
                            member_path,
                            pattern,
                            before,
                            after,
                            red,
                            reset,
                            args.matchlen,
                            display_name=member_name,
                            link_path=archive_path,
                        )
                    except Exception as exc:
                        print_error(f"\nWarning: cannot read {display_name}: {exc}")

                    show_search_progress(
                        index,
                        len(archive_members),
                        archive_path.name,
                        bar_width=20,
                        label="Archives ",
                    )
        else:
            show_search_progress(0, 0, "No matching archive members", label="Archives ")

        # Print newline on stderr for correct printing afterwards.
        if progress_enabled():
            print(file=sys.stderr)

    # Print summary of searched files.
    if args.include_archives:
        print(
            f"Searched {files_total} files, and {len(archives)} archives containing another {len(archive_members)} files."
        )
    else:
        print(f"Searched {files_total} files (archives excluded by user).")

    return 0 if total_matches else 1


def main() -> int:
    """Run the command-line application, reporting user interruptions cleanly."""
    try:
        return _run()
    except KeyboardInterrupt:
        print_error("Interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
