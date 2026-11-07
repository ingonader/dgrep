import re
from pathlib import PurePosixPath

DEFAULT_EXCLUDE_DIRS = (
    r"/\.git/",
    r"/\.svn/",
    r"/\.hg/",
    r"/__pycache__/",
    r"/\.pytest_cache/",
    r"/\.mypy_cache/",
    r"/\.ruff_cache/",
    r"/\.tox/",
    r"/\.nox/",
    r"/node_modules/",
    r"/\.venv/",
    r"/venv/",
    r"/virtualenv/",
    r"/renv/library/",
    r"/renv/sandbox/",
    r"/\.next/",
    r"/\.nuxt/",
    r"/\.terraform/",
    r"/target/",
    r"/\.gradle/",
)
DEFAULT_EXCLUDE_DIRS_SPEC = ",".join(DEFAULT_EXCLUDE_DIRS)


def compile_regex_list(
    value: str,
    flags: int = 0,
    *,
    empty_pattern: str | None = None,
) -> list[re.Pattern[str]]:
    """Compile comma-separated regular expressions into a list of patterns.

    Empty entries are ignored unless ``empty_pattern`` is provided, in which
    case they compile as that expression.

    Args:
        value: Comma-separated regular expressions to compile.
        flags: Flags passed to :func:`re.compile` for each expression.
        empty_pattern: Expression to use for empty entries. If ``None``,
            empty entries are skipped.

    Returns:
        Compiled regular expression patterns, in input order.

    Raises:
        re.error: If any expression is invalid.
    """
    patterns = []
    for expression in value.split(","):
        expression = expression.strip()
        if not expression:
            if empty_pattern is None:
                continue
            expression = empty_pattern
        patterns.append(re.compile(expression, flags))
    return patterns


def is_excluded_directory_path(
    relative_path: str | PurePosixPath,
    exclude_patterns: list[re.Pattern[str]],
) -> bool:
    """Check whether any directory in a relative path matches an exclusion.

    Each directory prefix is tested in its plain, trailing-slash, and
    slash-delimited forms.

    Args:
        relative_path: Relative path whose directory components to check.
        exclude_patterns: Compiled expressions used to match directory paths.

    Returns:
        ``True`` if any directory component matches an expression; otherwise,
        ``False``.
    """
    path = PurePosixPath(str(relative_path).replace("\\", "/"))
    parts = [part for part in path.parts if part not in {".", "/", ""}]
    for end in range(1, len(parts) + 1):
        prefix = "/".join(parts[:end])
        candidates = (prefix, prefix + "/", "/" + prefix + "/")
        if any(
            pattern.search(candidate)
            for pattern in exclude_patterns
            for candidate in candidates
        ):
            return True
    return False
