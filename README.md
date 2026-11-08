# dgrep

`dgrep` searches text and document files for a regular expression. The tool can extract text from common formats. By default, files with the following extensions are searched:

* `.txt`: Plain-text files.
* `.md`: Plain-text markdown files.
* `.pdf`: Portable document format files.
* `.docx`: Microsoft Office Word files.
* `.odt`: Open Document Format document files (e.g., LibreOffice).
* `.odp`: Open Document Format presentation files (e.g., LibreOffice).
* `.pptx`: Powerpoint presentation files.

The tool can search a single file or recursively search directories, and optionally searches within supported archive files like `.zip`, `.7z`, and various `.,tar` files.

Files with matches are displayed as `file:///path/to/file.ext` , which in some terminals (like KDE's `konsole`) is rendered as link to open this file with the system's configured editor.

Matches are highlighted, and the tool can display context lines before/after matches, or limit the maximal line length around each match (useful for files with very long lines, to not clutter the results).

Searches operate on extracted lines, and the search can span multiple lines when the search expression contains one or more `\n` sequences. In multiline mode, `^` and `$` match the beginning and end of any line; `.` does not match line breaks in either mode. 

File names can also be filtered with a regular expression, and paths can be excluded as well (with sensible defaults for searching developer file trees).

Sort order of displayed results can be configured, and are sorted by modification time by default (last modified displayed first).

## Disclaimer

This tool has been developed for my own personal use. It was only tested on Linux, not other operating systems. Most (but not all) code has been written by AI, with human code reviews by myself. There is no guarantee that this tool works on any other system than my own, and I take no responsibility for any harm that might arise from installing or running the tool on your system.

## Installation

`dgrep` requires Python 3.12 or newer. The simplest way to run it without installing it permanently is with [`uv`](https://docs.astral.sh/uv/):

```bash
uvx dgrep --help
```

`uvx` downloads and runs the published package in an isolated environment. Alternatively, install it as a persistent command-line tool:

```bash
uv tool install dgrep
dgrep --help
```

To run from a checkout of this repository, install the project dependencies and invoke its command with `uv`:

```bash
uv sync
uv run dgrep --help
```

## Usage

```text
dgrep [OPTIONS] PATTERN [PATH ...]
```

For example, search the default document types under a directory:

```bash
uvx dgrep 'whale|sea' ./books
```

Search a particular file, ignoring case and showing two lines of context on each side:

```bash
uvx dgrep -i -C 2 'chapter\s+[0-9]+' ./books/novel.txt
```

Search source files by extension (the extension selector also accepts regexes)
and filter file names by a regular expression:

```bash
uvx dgrep -e 'py|js' -f 'test|example' 'TODO|FIXME' ./project
```

Exclude dependency and generated-file directories while searching:

```bash
uvx dgrep -x 'renv,venv' 'TODO|FIXME' ./project
```

Enable archive searching with `-a`:

```bash
uvx dgrep -a 'search pattern' ./downloads
```

Use quotes around patterns containing shell metacharacters such as `|`, `*`, parentheses, or spaces so the shell passes the complete regular expression to `dgrep`. Expressions use Python's regular-expression syntax.

## Command-line options

Run `dgrep --help` (or `uvx dgrep --help`) to see the options in the terminal.

| Option | Description |
| --- | --- |
| `PATTERN` | **Required.** Python regular expression searched in the extracted text. Expressions containing `\n` can match across lines; otherwise each line is searched independently. |
| `PATH ...` | Optional. One or more files or directories. Directories are searched recursively. Defaults to the current directory (`.`). |
| `-i`, `--ignore-case` | Ignore case in the content pattern, file-name pattern, and directory-exclusion patterns. |
| `-a`, `--include-archives` | Also search supported archive files found at the given paths. Ordinary files are searched first. |
| `-B N`, `--before-context N` | Print up to `N` lines before each matching line. Default: `0`. |
| `-A N`, `--after-context N` | Print up to `N` lines after each matching line. Default: `0`. |
| `-C N`, `--context N` | Print up to `N` lines before and after each match. This overrides `-A` and `-B` if they are also supplied. |
| `-l CHARS`, `--matchlen CHARS` | Limit displayed line excerpts to approximately `CHARS` characters, centered on each match. A match longer than this value is kept whole. Context-only lines are shortened from the beginning. Must be a positive integer. |
| `-e EXTENSIONS`, `--ext EXTENSIONS` | Comma-separated regular expressions full-matched against file suffixes, with or without the leading dot. For example, `txt,md` selects `.txt` and `.md`, `py|js` selects `.py` and `.js`, and `docx?` selects `.doc` and `.docx`. By default the searched extensions are `txt`, `md`, `pdf`, `docx`, `odt`, `odp`, and `pptx`. Specifying this option replaces the defaults; prefix it with `+` (for example, `+py,R,sh`) to add patterns while keeping the defaults, or `^` (for example, `^pdf,docx`) to remove matching extensions from the defaults. An empty entry selects files without an extension: `,` searches only extensionless files, while `py,` searches `.py` and extensionless files. |
| `-f REGEX`, `--filename REGEX` | Search only files whose name without its extension matches this regular expression. For archives, the archive suffix is removed before testing; archive members are filtered by their member-name stem. |
| `-x REGEXES`, `--exclude REGEXES` | Comma-separated regular expressions matched against relative directory paths (commas cannot appear inside an expression). Matching directories and all their contents are excluded, including archive members. By default, `/.git/`, `/.svn/`, `/.hg/`, `/__pycache__/`, `/.pytest_cache/`, `/.mypy_cache/`, `/.ruff_cache/`, `/.tox/`, `/.nox/`, `/node_modules/`, `/.venv/`, `/venv/`, `/virtualenv/`, `/renv/library/`, `/renv/sandbox/`, `/.next/`, `/.nuxt/`, `/.terraform/`, `/target/`, and `/.gradle/` are excluded. Specifying patterns replaces the defaults; prefix with `+` to add patterns to them, or `^` to remove matching defaults (for example, `-x '^renv/library'`). Paths excluded during discovery are summarized in the output. |
| `--sort KEY[ r]` | Sort ordinary files and archives before searching. `a` sorts alphabetically by fully resolved path (default); `c` sorts by change time; `t` by modification time; `u` by last access time. Time sorts place newest files first. Add `r` to reverse the selected order, e.g. `--sort tr` searches oldest-modified files first. `--sort r` reverses alphabetical order. |
| `-c MODE`, `--color MODE` | Set match coloring to `auto`, `always`, or `never`. `auto` (the default) uses color when standard output is a terminal. |
| `-h`, `--help` | Show the help text and exit. |

Context counts must be non-negative. The `-C` option takes precedence over `-A` and `-B`.

## Supported files

The following document formats have dedicated text extraction:

| Extension | Extracted content |
| --- | --- |
| `.pdf` | Page text, with a page marker included before each page. |
| `.docx` | Word paragraphs, preserving blank paragraphs. |
| `.doc` | Legacy Word document text, using `antiword`. |
| `.pptx` | Slide text, table rows, and speaker notes, with slide markers. |
| `.ppt` | Legacy PowerPoint content, converted to PPTX with LibreOffice first. |
| `.xlsx` | Worksheet rows, including the sheet name and cell values. |
| `.xls` | Legacy Excel worksheet rows and values. |
| `.ods` | Spreadsheet rows, including sheet names, visible cell text, and stored values. |
| `.odt`, `.odp` | Text paragraphs and headings in OpenDocument content. |

Other files selected by extension are read as UTF-8 text; invalid byte sequences are replaced. The default extension set is intentionally narrower than the formats supported by the extractors: `.doc`, `.ppt`, and `.xls` must be explicitly selected with `-e doc`, `-e ppt`, or `-e xls`.

Most document formats are handled by Python packages installed with `dgrep`. Two legacy formats need additional system programs:

* `.doc` files require `antiword` (on Debian or Ubuntu: `sudo apt install antiword`).
* `.ppt` files require LibreOffice Impress (on Debian or Ubuntu:
  `sudo apt install libreoffice-impress`).





## Archive searching

Archive search is opt-in: without `-a`, archives are not searched. Supported formats are ZIP (`.zip`, `.jar`), 7-Zip (`.7z`), TAR (including `.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz2`, `.tar.xz`, and `.txz`), and single-file compression (`.gz`, `.bz2`, `.xz`).

Archive members use the same extension selection as ordinary files. A standalone compressed stream without an inner filename is treated as a `.txt` member. Members are read into temporary storage and searched using the same document extractors; they are not unpacked into the searched directory.



## Development and Testing

To install the development dependencies and run the test suite:

```bash
uv sync --group dev
uv run pytest
```

To measure test coverage and show uncovered source lines, run:

```bash
uv run pytest --cov=dgrep --cov-report=term-missing
```

To create a browsable HTML report instead, run:

```bash
uv run pytest --cov=dgrep --cov-report=html
```

Open `htmlcov/index.html` to browse the report.

Coverage data (`.coverage`) is generated locally and should not be committed.
To keep a human-readable snapshot in Git for comparison, generate and commit a
Markdown coverage report:

```bash
uv run pytest --cov=dgrep --cov-report=term-missing \
  --cov-report=markdown:coverage-report.md
```

Commit `coverage-report.md` when you want to update the checked-in snapshot.



## Results and exit status

Matching lines are displayed with their one-based line numbers. Context lines use a dash after the line number; matching lines use a colon. When color is enabled, each matching occurrence is highlighted. File headings include a clickable terminal file link when the terminal supports OSC 8 hyperlinks.

The command exits with status `0` if at least one matching line is found, or `1` if there are no matches or no supported files. Pressing Ctrl+C stops the search, prints `Interrupted by user`, and exits with status `130`. Invalid arguments and regular expressions are reported by the command-line parser. Files that cannot be read produce warnings on standard error; the search continues with other files. If standard output is redirected while standard error remains connected to a terminal, error messages are also copied to standard output.
