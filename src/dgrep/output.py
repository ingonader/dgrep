import sys


def progress_enabled() -> bool:
    return sys.stderr.isatty()


def print_error(message: str) -> None:
    print(message, file=sys.stderr)
    if not sys.stdout.isatty() and sys.stderr.isatty():
        print(message, file=sys.stdout)
