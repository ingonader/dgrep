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


def parse_regex_spec(
    value: str | None,
    flags: int = 0,
    *,
    empty_pattern: str | None = None,
) -> tuple[str | None, list[re.Pattern[str]]]:
    """Parse and compile a comma-separated regex specification.

    A leading ``+`` or ``^`` is removed and returned as the modifier. Callers
    use ``+`` to add patterns to defaults and ``^`` to remove matching defaults.

    Args:
        value: Comma-separated regular expressions, or ``None``.
        flags: Flags passed to :func:`re.compile`.
        empty_pattern: Pattern used for empty entries. Empty entries are
            ignored when this is ``None`` or when ``value`` uses ``^``.

    Returns:
        A tuple containing the optional modifier and the compiled patterns.
        If ``value`` is ``None``, returns ``(None, [])``.

    Raises:
        re.error: If any expression is invalid.
    """
    if value is None:
        return None, []

    modifier = value[0] if value.startswith(("+", "^")) else None
    if modifier is not None:
        value = value[1:]

    return modifier, compile_regex_list(
        value,
        flags,
        empty_pattern=empty_pattern if modifier != "^" else None,
    )


def compile_exclude_patterns(
    value: str | None,
    flags: int = 0,
) -> list[re.Pattern[str]]:
    """Compile directory exclusions with optional default-set modifiers.

    Args:
        value: Comma-separated directory regexes, or ``None`` to use only the
            defaults. Without a prefix, the supplied patterns replace the
            defaults; ``+`` adds patterns to them, and ``^`` removes matching
            defaults.
        flags: Flags passed to :func:`re.compile`.

    Returns:
        Compiled directory-exclusion patterns.

    Raises:
        re.error: If any supplied expression is invalid.
    """
    modifier, patterns = parse_regex_spec(value, flags)
    if value is None:
        return compile_regex_list(DEFAULT_EXCLUDE_DIRS_SPEC, flags)
    if modifier is None:
        return patterns

    default_patterns = compile_regex_list(DEFAULT_EXCLUDE_DIRS_SPEC, flags)
    if modifier == "+":
        return default_patterns + patterns

    return [
        default
        for default in default_patterns
        if not any(pattern.search(default.pattern) for pattern in patterns)
    ]


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
