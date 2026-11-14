from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest

from ldgrep import text_extraction

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def sample(name: str) -> Path:
    return DATA_DIR / name


def assert_text_contains(lines: list[str], text: str) -> None:
    assert text.casefold() in "\n".join(lines).casefold()


@pytest.mark.parametrize(
    "extractor",
    [
        text_extraction.extract_pdf_text_pypdf,
        text_extraction.extract_pdf_text_pymupdf,
        text_extraction.extract_pdf_text,
    ],
)
def test_pdf_extractors_include_page_markers_and_text(extractor) -> None:
    """Verify PDF extractors preserve page markers and extract sample text.

    Args:
        extractor: PDF extraction function under test.
    """
    lines = extractor(sample("moby-dick.pdf"))

    # Check that page boundaries and extracted content are both retained.
    assert lines[0] == "[PDF page 1]"
    assert any(line.startswith("[PDF page ") for line in lines)
    assert_text_contains(lines, "Call me Ishmael")


def test_pdf_extractor_falls_back_to_pypdf(monkeypatch) -> None:
    """Verify PDF extraction falls back to pypdf when PyMuPDF fails.

    Args:
        monkeypatch: Pytest fixture for replacing extractor functions.
    """
    expected = ["[PDF page 1]", "fallback text"]

    # Force the preferred engine to fail so the fallback path is exercised.
    def fail_pymupdf(path: Path) -> list[str]:
        raise RuntimeError("PyMuPDF could not read the document")

    monkeypatch.setattr(text_extraction, "extract_pdf_text_pymupdf", fail_pymupdf)
    monkeypatch.setattr(
        text_extraction, "extract_pdf_text_pypdf", lambda path: expected
    )

    assert text_extraction.extract_pdf_text(sample("moby-dick.pdf")) == expected


@pytest.mark.parametrize(
    ("filename", "expected_text"),
    [
        ("moby-dick.docx", "Call me Ishmael"),
        ("rime-of-the-ancient-mariner.docx", "Ancient Mariner"),
    ],
)
def test_docx_extracts_paragraph_text(filename: str, expected_text: str) -> None:
    """Verify DOCX extraction returns paragraphs from the sample documents.

    Args:
        filename: Name of the DOCX sample file.
        expected_text: Text expected in the extracted paragraphs.
    """
    lines = text_extraction.extract_docx_text(sample(filename))

    # The samples contain narrative text in paragraph form.
    assert lines
    assert_text_contains(lines, expected_text)


def test_doc_extracts_text_when_antiword_is_installed() -> None:
    """Verify legacy DOC extraction when antiword is available."""
    if shutil.which("antiword") is None:
        # The extractor depends on this external system utility.
        pytest.skip("antiword is required to extract legacy .doc files")

    lines = text_extraction.extract_doc_text(sample("moby-dick.doc"))

    assert lines
    assert_text_contains(lines, "Call me Ishmael")


def test_pptx_extracts_slide_text() -> None:
    """Verify PPTX extraction includes slide markers and visible text."""
    lines = text_extraction.extract_pptx_text(sample("moby-dick.pptx"))

    # Slide markers make the extracted content traceable to its source slide.
    assert lines[0] == "[Slide 1]"
    assert_text_contains(lines, "Ishmael")


@pytest.mark.parametrize("filename", ["moby-dick.odt", "moby-dick.odp"])
def test_odf_extracts_text(filename: str) -> None:
    """Verify ODF extraction returns non-empty text from sample files.

    Args:
        filename: Name of the ODF sample file.
    """
    lines = text_extraction.extract_odf_text(sample(filename))

    # The two ODF samples differ in document type but should contain readable text.
    assert lines
    assert any(line.strip() for line in lines)


@pytest.mark.parametrize(
    ("extractor", "filename"),
    [
        (text_extraction.extract_xlsx_text, "rime-of-the-ancient-mariner.xlsx"),
        (text_extraction.extract_xls_text, "rime-of-the-ancient-mariner.xls"),
        (text_extraction.extract_ods_text, "rime-of-the-ancient-mariner.ods"),
    ],
)
def test_spreadsheet_extractors_include_sheet_names_and_text(
    extractor, filename: str
) -> None:
    """Verify spreadsheet extraction includes sheet names and cell content.

    Args:
        extractor: Spreadsheet extraction function under test.
        filename: Name of the spreadsheet sample file.
    """
    lines = extractor(sample(filename))

    # Each spreadsheet output row starts with a sheet name and uses the default delimiter.
    assert lines
    assert all("|" in line for line in lines)
    assert_text_contains(lines, "Mariner")


def test_spreadsheet_extractors_respect_custom_separator() -> None:
    """Verify spreadsheet extractors use a caller-provided separator."""
    for extractor, filename in [
        (text_extraction.extract_xlsx_text, "rime-of-the-ancient-mariner.xlsx"),
        (text_extraction.extract_xls_text, "rime-of-the-ancient-mariner.xls"),
        (text_extraction.extract_ods_text, "rime-of-the-ancient-mariner.ods"),
    ]:
        # Confirm the requested delimiter is applied to every emitted row.
        lines = extractor(sample(filename), separator="::")

        assert lines
        assert all("::" in line for line in lines)


def test_legacy_ppt_converts_to_pptx_and_extracts(monkeypatch, tmp_path: Path) -> None:
    """Verify legacy PPT conversion passes the converted file to extraction.

    Args:
        monkeypatch: Pytest fixture for replacing subprocess and extraction.
        tmp_path: Temporary directory fixture for the source presentation.
    """
    source = tmp_path / "presentation.ppt"
    source.touch()
    extracted_file: Path | None = None

    # Simulate LibreOffice creating the converted file without invoking it.
    def fake_run(command, **kwargs):
        nonlocal extracted_file
        output_dir = Path(command[command.index("--outdir") + 1])
        extracted_file = output_dir / "presentation.pptx"
        extracted_file.touch()
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    def fake_extract_pptx(path: Path) -> list[str]:
        assert path == extracted_file
        return ["[Slide 1]", "converted slide"]

    monkeypatch.setattr(text_extraction.subprocess, "run", fake_run)
    monkeypatch.setattr(text_extraction, "extract_pptx_text", fake_extract_pptx)

    # Extraction should receive the temporary PPTX and return its text.
    assert text_extraction.extract_ppt_text(source) == [
        "[Slide 1]",
        "converted slide",
    ]


@pytest.mark.parametrize(
    ("filename", "expected_text"),
    [
        ("moby-dick.txt", "Call me Ishmael"),
        ("moby-dick.md", "Call me Ishmael"),
        ("moby-dick.docx", "Call me Ishmael"),
        ("moby-dick.pdf", "Call me Ishmael"),
        ("moby-dick.odt", "Ishmael"),
        ("moby-dick.odp", None),
        ("moby-dick.pptx", "Ishmael"),
        ("rime-of-the-ancient-mariner.xlsx", "Mariner"),
        ("rime-of-the-ancient-mariner.xls", "Mariner"),
        ("rime-of-the-ancient-mariner.ods", "Mariner"),
    ],
)
def test_extract_text_dispatches_supported_data_files(
    filename: str, expected_text: str | None
) -> None:
    """Verify extension-based dispatch for the supplied supported files.

    Args:
        filename: Name of a sample file to dispatch.
        expected_text: Optional text expected in the extracted result.
    """
    lines = text_extraction.extract_text(sample(filename))

    # A missing expected phrase is intentional for the presentation sample.
    assert lines
    if expected_text is not None:
        assert_text_contains(lines, expected_text)


def test_extract_text_replaces_invalid_utf8(tmp_path: Path) -> None:
    """Verify plain-text extraction replaces invalid UTF-8 bytes.

    Args:
        tmp_path: Temporary directory fixture for the test file.
    """
    path = tmp_path / "invalid.bin"
    path.write_bytes(b"first line\ninvalid: \xff")

    # Invalid bytes should be replaced instead of preventing text extraction.
    assert text_extraction.extract_text(path) == [
        "first line",
        "invalid: \N{REPLACEMENT CHARACTER}",
    ]


def test_extract_text_matches_extension_case_insensitively(tmp_path: Path) -> None:
    """Verify plain-text dispatch accepts uppercase file extensions.

    Args:
        tmp_path: Temporary directory fixture for the test file.
    """
    path = tmp_path / "sample.TXT"
    path.write_text("plain text", encoding="utf-8")

    # Uppercase suffixes should use the same plain-text path as lowercase ones.
    assert text_extraction.extract_text(path) == ["plain text"]


@pytest.mark.parametrize(
    ("extractor", "module_name", "message"),
    [
        (text_extraction.extract_pdf_text_pypdf, "pypdf", "pypdf"),
        (text_extraction.extract_pdf_text_pymupdf, "pymupdf", "pymupdf"),
        (text_extraction.extract_docx_text, "docx", "python-docx"),
        (text_extraction.extract_pptx_text, "pptx", "python-pptx"),
        (text_extraction.extract_xlsx_text, "openpyxl", "openpyxl"),
        (text_extraction.extract_xls_text, "xlrd", "xlrd"),
        (text_extraction.extract_ods_text, "odf.opendocument", "odfpy"),
    ],
)
def test_extractors_report_missing_optional_dependencies(
    extractor, module_name: str, message: str, monkeypatch
) -> None:
    """Verify optional-format dependencies produce actionable errors."""
    monkeypatch.setitem(sys.modules, module_name, None)

    with pytest.raises(RuntimeError, match=message):
        extractor(Path("sample"))


def test_pdf_extractors_handle_empty_pages(monkeypatch) -> None:
    """Verify pages with no extractable text still get page markers."""
    import types

    monkeypatch.setitem(
        sys.modules,
        "pypdf",
        types.SimpleNamespace(
            PdfReader=lambda path: SimpleNamespace(
                pages=[SimpleNamespace(extract_text=lambda: None)]
            )
        ),
    )

    assert text_extraction.extract_pdf_text_pypdf(Path("sample")) == ["[PDF page 1]"]


def test_pymupdf_extracts_page_text(monkeypatch) -> None:
    """Verify PyMuPDF page text is split into lines and the document is closed."""
    import types

    class Document:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed = True

        def __iter__(self):
            return iter([SimpleNamespace(get_text=lambda mode: "one\ntwo\n")])

    doc = Document()
    monkeypatch.setitem(
        sys.modules, "pymupdf", types.SimpleNamespace(open=lambda path: doc)
    )

    assert text_extraction.extract_pdf_text_pymupdf(Path("sample")) == [
        "[PDF page 1]",
        "one",
        "two",
    ]
    assert doc.closed


def test_extract_doc_text_returns_lines_and_reports_failures(
    monkeypatch, tmp_path: Path
) -> None:
    """Verify antiword success, missing executable, and conversion errors."""
    source = tmp_path / "sample.doc"
    source.touch()
    monkeypatch.setattr(
        text_extraction.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="first\nsecond\n"),
    )
    assert text_extraction.extract_doc_text(source) == ["first", "second"]

    monkeypatch.setattr(
        text_extraction.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )
    with pytest.raises(RuntimeError, match="antiword"):
        text_extraction.extract_doc_text(source)

    monkeypatch.setattr(
        text_extraction.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, "antiword", stderr="bad document\n")
        ),
    )
    with pytest.raises(RuntimeError, match="bad document"):
        text_extraction.extract_doc_text(source)


def test_docx_preserves_empty_paragraphs_and_line_breaks(monkeypatch) -> None:
    """Verify DOCX extraction preserves empty paragraphs and split lines."""
    import types

    monkeypatch.setitem(
        sys.modules,
        "docx",
        types.SimpleNamespace(
            Document=lambda path: SimpleNamespace(
                paragraphs=[
                    SimpleNamespace(text="first\nsecond"),
                    SimpleNamespace(text=""),
                ]
            )
        ),
    )

    assert text_extraction.extract_docx_text(Path("sample")) == [
        "first",
        "second",
        "",
    ]


def test_pptx_extracts_shapes_tables_groups_and_notes(monkeypatch) -> None:
    """Verify recursive slide content and optional speaker notes are included."""
    import types

    def shape(
        *,
        text=(),
        rows=(),
        children=(),
        shape_type=1,
    ):
        return SimpleNamespace(
            has_text_frame=True,
            text_frame=SimpleNamespace(
                paragraphs=[SimpleNamespace(text=value) for value in text]
            ),
            has_table=bool(rows),
            table=SimpleNamespace(
                rows=[
                    SimpleNamespace(
                        cells=[SimpleNamespace(text=value) for value in row]
                    )
                    for row in rows
                ]
            ),
            shape_type=shape_type,
            shapes=children,
        )

    slide = SimpleNamespace(
        shapes=[
            shape(text=[" Title ", " "]),
            shape(rows=[[" A ", "B"], ["", ""]]),
            shape(shape_type=6, children=[shape(text=["nested"])]),
        ],
        has_notes_slide=True,
        notes_slide=SimpleNamespace(
            notes_text_frame=SimpleNamespace(text=" note one\nnote two ")
        ),
    )
    empty_notes = SimpleNamespace(
        shapes=[],
        has_notes_slide=True,
        notes_slide=SimpleNamespace(notes_text_frame=None),
    )
    monkeypatch.setitem(
        sys.modules,
        "pptx",
        types.SimpleNamespace(
            Presentation=lambda path: SimpleNamespace(slides=[slide, empty_notes])
        ),
    )

    assert text_extraction.extract_pptx_text(Path("sample")) == [
        "[Slide 1]",
        "Title",
        "A | B",
        "nested",
        "[Speaker Notes - Slide 1]",
        "note one",
        "note two",
        "[Slide 2]",
    ]


@pytest.mark.parametrize(
    ("run_error", "result", "message"),
    [
        (FileNotFoundError(), None, "LibreOffice"),
        (subprocess.TimeoutExpired("libreoffice", 120), None, "timed out"),
        (
            None,
            SimpleNamespace(returncode=1, stderr="conversion failed", stdout=""),
            "conversion failed",
        ),
        (
            None,
            SimpleNamespace(returncode=0, stderr="", stdout="no file"),
            "no file",
        ),
    ],
)
def test_legacy_ppt_reports_conversion_failures(
    monkeypatch, tmp_path: Path, run_error, result, message: str
) -> None:
    """Verify missing tools, timeouts, and unsuccessful conversions are reported."""
    source = tmp_path / "presentation.ppt"
    source.touch()

    def fake_run(command, **kwargs):
        if run_error is not None:
            raise run_error
        return result

    monkeypatch.setattr(text_extraction.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match=message):
        text_extraction.extract_ppt_text(source)


def test_odf_reports_missing_content_and_preserves_inline_spacing(tmp_path: Path) -> None:
    """Verify ODF archive errors and paragraph spacing/break serialization."""
    missing_content = tmp_path / "missing.odt"
    with zipfile.ZipFile(missing_content, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
    with pytest.raises(RuntimeError, match="content.xml"):
        text_extraction.extract_odf_text(missing_content)

    document = tmp_path / "content.odt"
    content = b"""<office:document-content
        xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
        xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
      <office:body><office:text>
        <text:h> Heading </text:h>
        <text:p>left<text:s text:c="2"/>middle<text:tab/>right<text:line-break/>next<text:span>nested</text:span> tail</text:p>
        <text:p><text:line-break/></text:p>
        <text:p/>
      </office:text></office:body>
    </office:document-content>"""
    with zipfile.ZipFile(document, "w") as archive:
        archive.writestr("content.xml", content)

    assert text_extraction.extract_odf_text(document) == [
        " Heading ",
        "left  middle\tright",
        "nextnested tail",
        "",
        "",
    ]


def test_odf_extracts_nested_content_links_and_metadata(tmp_path: Path) -> None:
    """Verify ODF tables, frames, notes, comments, links, and metadata."""
    document = tmp_path / "rich-content.odt"
    content = b"""<office:document-content
        xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
        xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
        xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
        xmlns:presentation="urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"
        xmlns:xlink="http://www.w3.org/1999/xlink">
      <office:body><office:text>
        <table:table><table:table-row><table:table-cell>
          <text:p>Table cell text</text:p>
        </table:table-cell></table:table-row></table:table>
        <draw:frame><draw:text-box><text:p>Frame text</text:p></draw:text-box></draw:frame>
        <text:p>Link <text:a xlink:href="https://example.test/doc">target</text:a></text:p>
        <text:p>Footnote <text:note><text:note-citation>1</text:note-citation>
          <text:note-body><text:p>Footnote body</text:p></text:note-body>
        </text:note></text:p>
        <text:p>Endnote <text:note text:note-class="endnote">
          <text:note-citation>2</text:note-citation>
          <text:note-body><text:p>Endnote body</text:p></text:note-body>
        </text:note></text:p>
        <office:annotation><text:p>Comment text</text:p></office:annotation>
        <presentation:notes><draw:frame><draw:text-box>
          <text:p>Speaker note text</text:p>
        </draw:text-box></draw:frame></presentation:notes>
      </office:text></office:body>
    </office:document-content>"""
    metadata = b"""<office:document-meta
        xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
        xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
        xmlns:dc="http://purl.org/dc/elements/1.1/">
      <office:meta>
        <dc:title>Document title</dc:title>
        <dc:subject>Document subject</dc:subject>
        <meta:keyword>alpha</meta:keyword><meta:keyword>beta</meta:keyword>
        <dc:description>Document description</dc:description>
      </office:meta>
    </office:document-meta>"""
    with zipfile.ZipFile(document, "w") as archive:
        archive.writestr("content.xml", content)
        archive.writestr("meta.xml", metadata)

    lines = text_extraction.extract_odf_text(document)
    extracted = "\n".join(lines)

    for expected in [
        "Table cell text",
        "Frame text",
        "Link target (https://example.test/doc)",
        "Footnote body",
        "Endnote body",
        "Comment text",
        "Speaker note text",
        "Title: Document title",
        "Subject: Document subject",
        "Keywords: alpha, beta",
        "Description: Document description",
    ]:
        assert expected in extracted
    assert lines.count("Footnote body") == 1
    assert lines.count("Endnote body") == 1


def test_xlsx_normalizes_empty_cells_and_closes_workbook(monkeypatch) -> None:
    """Verify empty values, custom separators, and workbook cleanup."""
    import types

    class Sheet:
        title = "Data"

        def iter_rows(self, *, values_only):
            assert values_only
            yield (None, 3, False)

    workbook = SimpleNamespace(
        worksheets=[Sheet()],
        close=lambda: setattr(workbook, "closed", True),
        closed=False,
    )
    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        types.SimpleNamespace(
            load_workbook=lambda **kwargs: (
                setattr(workbook, "options", kwargs) or workbook
            )
        ),
    )

    assert text_extraction.extract_xlsx_text(Path("sample"), separator="::") == [
        "Data::::3::False"
    ]
    assert workbook.closed
    assert workbook.options == {
        "filename": "sample",
        "read_only": True,
        "data_only": True,
    }


def test_xlsx_closes_workbook_when_reading_fails(monkeypatch) -> None:
    """Verify a workbook is closed even when worksheet iteration raises."""
    import types

    class Sheet:
        title = "Data"

        def iter_rows(self, *, values_only):
            raise ValueError("invalid sheet")

    workbook = SimpleNamespace(
        worksheets=[Sheet()],
        closed=False,
    )
    workbook.close = lambda: setattr(workbook, "closed", True)
    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        types.SimpleNamespace(load_workbook=lambda **kwargs: workbook),
    )

    with pytest.raises(ValueError, match="invalid sheet"):
        text_extraction.extract_xlsx_text(Path("sample"))
    assert workbook.closed


def test_xls_normalizes_cell_types_and_unknown_errors(monkeypatch) -> None:
    """Verify XLS blanks, dates, booleans, errors, and ordinary values."""
    import types
    from datetime import datetime

    cells = [
        SimpleNamespace(ctype=0, value=""),
        SimpleNamespace(ctype=6, value=""),
        SimpleNamespace(ctype=3, value=2.5),
        SimpleNamespace(ctype=4, value=1),
        SimpleNamespace(ctype=5, value=7),
        SimpleNamespace(ctype=5, value=99),
        SimpleNamespace(ctype=1, value="text"),
    ]
    sheet = SimpleNamespace(
        name="Data",
        nrows=1,
        ncols=len(cells),
        cell=lambda row, col: cells[col],
    )
    workbook = SimpleNamespace(sheets=lambda: [sheet], datemode=0)
    fake_xlrd = types.SimpleNamespace(
        XL_CELL_EMPTY=0,
        XL_CELL_BLANK=6,
        XL_CELL_DATE=3,
        XL_CELL_BOOLEAN=4,
        XL_CELL_ERROR=5,
        error_text_from_code={7: "#DIV/0!"},
        open_workbook=lambda **kwargs: workbook,
        xldate_as_datetime=lambda value, datemode: datetime(2024, 1, 2),
    )
    monkeypatch.setitem(sys.modules, "xlrd", fake_xlrd)

    assert text_extraction.extract_xls_text(Path("sample"), separator=";") == [
        "Data;;;2024-01-02T00:00:00;true;#DIV/0!;99;text"
    ]


def test_ods_extracts_typed_values_inline_text_and_repeated_cells(
    monkeypatch, tmp_path: Path
) -> None:
    """Verify ODS text serialization and typed-cell fallbacks."""
    import types
    from odf.table import CoveredTableCell, Table, TableCell, TableRow
    from odf.text import A, LineBreak, P, S, Span, Tab

    row = TableRow()

    visible = TableCell()
    paragraph = P(text="visible")
    paragraph.addElement(S(c=2))
    paragraph.addElement(Span(text="nested"))
    paragraph.addElement(Tab())
    paragraph.addElement(A(href="https://example.test/sheet", text="linked"))
    paragraph.addElement(LineBreak())
    paragraph.addText("last")
    visible.addElement(paragraph)
    row.addElement(visible)

    for attributes in [
        {"valuetype": "string", "stringvalue": "str"},
        {"valuetype": "float", "value": "1.5"},
        {"valuetype": "currency", "value": "2"},
        {"valuetype": "percentage", "value": "0.5"},
        {"valuetype": "boolean", "booleanvalue": "true"},
        {"valuetype": "date", "datevalue": "2024-01-02"},
        {"valuetype": "time", "timevalue": "PT1H"},
        {"valuetype": "unknown", "value": "fallback"},
        {"valuetype": "unknown", "datevalue": "fallback date"},
        {"valuetype": "unknown"},
    ]:
        row.addElement(TableCell(**attributes))

    row.addElement(CoveredTableCell())
    row.addElement(TableCell(numbercolumnsrepeated="2"))
    row.childNodes.extend(
        [
            SimpleNamespace(nodeType=3, ELEMENT_NODE=1),
            SimpleNamespace(nodeType=1, ELEMENT_NODE=1, qname=("unknown", "node")),
        ]
    )
    table = SimpleNamespace(
        getAttribute=lambda name: "Data",
        getElementsByType=lambda element_type: [row]
        if element_type is TableRow
        else [],
    )
    document = SimpleNamespace(
        spreadsheet=SimpleNamespace(getElementsByType=lambda element_type: [table])
    )
    monkeypatch.setitem(
        sys.modules["odf.opendocument"].__dict__,
        "load",
        lambda path: document,
    )

    source = tmp_path / "sample.ods"
    content = b"""<office:document-content
        xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
        xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0">
      <office:body><office:spreadsheet>
        <draw:frame><draw:text-box><text:p>Floating text box</text:p></draw:text-box></draw:frame>
      </office:spreadsheet></office:body>
    </office:document-content>"""
    metadata = b"""<office:document-meta
        xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
        xmlns:dc="http://purl.org/dc/elements/1.1/">
      <office:meta><dc:title>Sheet title</dc:title></office:meta>
    </office:document-meta>"""
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("content.xml", content)
        archive.writestr("meta.xml", metadata)

    assert text_extraction.extract_ods_text(source, separator=";") == [
        "Data;visible  nested\tlinked (https://example.test/sheet)\nlast;str;1.5;2;0.5;true;2024-01-02;PT1H;fallback;fallback date;;;;",
        "Floating text box",
        "Title: Sheet title",
    ]


@pytest.mark.parametrize(
    ("suffix", "extractor_name"),
    [(".doc", "extract_doc_text"), (".ppt", "extract_ppt_text")],
)
def test_extract_text_dispatches_legacy_office_formats(
    monkeypatch, suffix: str, extractor_name: str
) -> None:
    """Verify legacy office extensions use their dedicated extractors."""
    expected = [f"handled {suffix}"]
    monkeypatch.setattr(text_extraction, extractor_name, lambda path: expected)

    assert text_extraction.extract_text(Path(f"legacy{suffix}")) == expected
