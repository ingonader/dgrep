import sys
import shutil
from pathlib import Path


def configure_colors(mode: str) -> tuple[str, str]:
    """Choose ANSI color codes based on the requested color mode.

    Args:
        mode: One of `"always"`, `"never"`, or `"auto"`. Auto mode
            enables colors only when standard output is connected to a TTY.

    Returns:
        A pair containing the color-start and reset escape sequences, or two
        empty strings when color output is disabled.
    """
    # Auto mode avoids emitting terminal escapes when output is redirected.
    use_color = mode == "always" or (mode == "auto" and sys.stdout.isatty())

    if use_color:
        return "\033[31m", "\033[0m"

    return "", ""


def progress_enabled() -> bool:
    return sys.stdout.isatty() and sys.stderr.isatty()


def hyperlink(path: Path) -> str:
    """Format a file path as a file-URI label for search output."""
    uri = path.resolve().as_uri()
    return f"{uri} "


def print_file(link_path: Path, output_name: str) -> None:
    """Print a terminal-width separator followed by a file's display label."""
    terminal_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    print("=" * terminal_width)
    print(f"\r{hyperlink(link_path)}{output_name}")


def print_error(message: str) -> None:
    print(message, file=sys.stderr)
    if not sys.stdout.isatty() and sys.stderr.isatty():
        print(message, file=sys.stdout)


def show_search_progress(
    current: int,
    total: int,
    filename: str,
    bar_width: int = 20,
    label: str = "",
) -> None:
    """Write a single-line progress indicator to standard error.

    Args:
        current: Number of completed items.
        total: Total number of items; zero displays a zero-percent bar.
        filename: Current filename or status text shown beside the bar.
        bar_width: Number of characters used for the progress bar.
        label: Optional prefix distinguishing progress categories.
    """
    filename = str(filename)
    terminal_width = shutil.get_terminal_size(fallback=(80, 24)).columns

    # Clamp available filename space to avoid negative padding on narrow terminals.
    fraction = current / total if total else 0
    filled = int(bar_width * fraction)
    bar = "#" * filled + "." * (bar_width - filled)

    prefix = f"\r{label}[{bar}] {fraction:6.1%} "
    available = max(0, terminal_width - len(prefix) - 1)

    # Truncate long filenames.
    if len(filename) > available:
        filename = (
            "..." + filename[-(available - 3) :]
            if available > 3
            else filename[:available]
        )

    message = prefix + filename

    if progress_enabled():
        print(message.ljust(terminal_width - 1), end="", file=sys.stderr, flush=True)
