#!/usr/bin/env python3
"""
Tests for journal data models, .bib parsing, and export helpers.
"""

import os
import tempfile
import zipfile
from pathlib import Path

# Add source paths for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

import journal
from journal import (
    Entry, BibEntry, VaultStorage, fuzzy_filter, fuzzy_filter_entries,
    parse_bib_lightweight, _find_bib_file, _load_bib_entries,
    parse_yaml_frontmatter, resolve_reference_doc,
    detect_pandoc, detect_libreoffice, detect_typst,
    _generate_lua_filter, _lua_basic_filter,
    _lua_coverpage_filter, _lua_header_filter,
    _postprocess_docx, _REFS_DIR,
    _author_lastname, _format_export_date, _typst_str, _typst_wrapper,
    _pdf_engine, _resolve_bib_path, _bundled_bin, _TEMPLATES_DIR, _initial_pdf_engine, _strip_frontmatter, _resolve_csl_path,
    _list_continuation, _ensure_writable, MarkdownLexer,
    _get_foot_font_size, _set_foot_font_size, COLOR_SCHEMES,
    _env_bin, _config_path, _default_vault, _normalise_pasted,
    _detect_clipboard, _no_console, safe_entry_name, _ILLEGAL_CHARS,
    _template_name, _DEFAULT_TEMPLATE, _default_csl_path, _CSL_DIR,
    _column_widths, _cell_text_rows, _autofit_tables, _TEXT_WIDTH_TWIPS,
    _bib_blocks, _filter_bib, _cited_keys, _narrow_bib,
    _PANDOC_RTS, _rts_rejected, _PANDOC_TIMEOUT, _PANDOC_CITE_TIMEOUT,
    _FONTS_DIR,
    _strip_bib_noise, _bib_value_end, _bib_openers,
)


def test_vault_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = VaultStorage(Path(tmpdir))

        # Directories created
        assert (Path(tmpdir) / "pdf").is_dir()
        assert (Path(tmpdir) / "docx").is_dir()

        # Create entry
        entry = storage.create_entry("Test Note")
        assert entry.name == "Test Note"
        assert entry.path.exists()
        assert entry.path.suffix == ".md"

        # Save and read
        storage.save_entry(entry, "# Hello\n\nWorld.")
        content = storage.read_entry(entry)
        assert content == "# Hello\n\nWorld."

        # List entries
        entries = storage.list_entries()
        assert len(entries) == 1
        assert entries[0].name == "Test Note"

        # Rename
        renamed = storage.rename_entry(entry, "Renamed Note")
        assert renamed.name == "Renamed Note"
        assert renamed.path.exists()
        assert not entry.path.exists()

        # Read renamed
        content = storage.read_entry(renamed)
        assert content == "# Hello\n\nWorld."

        # Delete
        storage.delete_entry(renamed)
        assert len(storage.list_entries()) == 0

    print("  VaultStorage OK")


def test_entry_dataclass():
    p = Path("/tmp/test.md")
    e = Entry(path=p, name="test", modified=1234567890.0)
    assert e.path == p
    assert e.name == "test"
    assert e.modified == 1234567890.0
    print("  Entry dataclass OK")


def test_bib_entry_dataclass():
    b = BibEntry(citekey="smith2020")
    assert b.citekey == "smith2020"
    print("  BibEntry dataclass OK")


def test_parse_bib_lightweight():
    bib_text = """
@book{fitzgerald1925,
  author = {Fitzgerald, F. Scott},
  title = {The Great Gatsby},
  year = {1925},
  publisher = {Scribner},
}

@article{smith2020,
  author = {Smith, John},
  title = {The Symbolism of the Green Light},
  journal = {American Literature Quarterly},
  year = {2020},
  volume = {45},
}

@misc{web2023,
  title = {Understanding Gatsby},
  year = {2023},
}
"""
    entries = parse_bib_lightweight(bib_text)
    assert len(entries) == 3

    assert entries[0].citekey == "fitzgerald1925"
    assert entries[1].citekey == "smith2020"
    assert entries[2].citekey == "web2023"

    print("  parse_bib_lightweight OK")


def test_find_bib_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)

        # No sources dir
        assert _find_bib_file(vault) is None

        # Empty sources dir
        (vault / "sources").mkdir()
        assert _find_bib_file(vault) is None

        # With a .bib file
        bib = vault / "sources" / "refs.bib"
        bib.write_text("@book{test, author={A}, title={B}}", encoding="utf-8")
        result = _find_bib_file(vault)
        assert result is not None
        assert result.name == "refs.bib"

    print("  _find_bib_file OK")


def test_load_bib_entries():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        (vault / "sources").mkdir()
        bib = vault / "sources" / "library.bib"
        bib.write_text('@book{doe2021, author={Doe, Jane}, title={A Book}}', encoding="utf-8")

        entries, path, mtime, error = _load_bib_entries(vault)
        assert len(entries) == 1
        assert entries[0].citekey == "doe2021"
        assert path is not None
        assert mtime > 0
        assert error == ""

    print("  _load_bib_entries OK")


def test_fuzzy_filter():
    entries = [
        BibEntry(citekey="fitzgerald1925"),
        BibEntry(citekey="smith2020"),
        BibEntry(citekey="hemingway1952"),
    ]

    results = fuzzy_filter(entries, "fitzgerald")
    assert len(results) >= 1
    assert results[0].citekey == "fitzgerald1925"

    results = fuzzy_filter(entries, "")
    assert len(results) == 3

    results = fuzzy_filter(entries, "smith2020")
    assert len(results) >= 1
    assert results[0].citekey == "smith2020"

    print("  Fuzzy filter OK")


def test_fuzzy_filter_entries():
    entries = [
        Entry(path=Path("/tmp/essay.md"), name="essay", modified=100.0),
        Entry(path=Path("/tmp/notes.md"), name="notes", modified=200.0),
        Entry(path=Path("/tmp/draft.md"), name="draft", modified=300.0),
    ]

    results = fuzzy_filter_entries(entries, "essay")
    assert len(results) >= 1
    assert results[0].name == "essay"

    results = fuzzy_filter_entries(entries, "")
    assert len(results) == 3

    print("  Fuzzy filter entries OK")


def test_parse_yaml_frontmatter():
    # Basic extraction
    content = "---\ntitle: My Essay\nauthor: John Smith\ndate: 2025-03-07\n---\n\nBody text."
    yaml = parse_yaml_frontmatter(content)
    assert yaml["title"] == "My Essay"
    assert yaml["author"] == "John Smith"
    assert yaml["date"] == "2025-03-07"
    print("  Basic frontmatter OK")

    # Quoted values
    content2 = '---\ntitle: "My Quoted Title"\nauthor: \'Jane Doe\'\n---\n\nBody.'
    yaml2 = parse_yaml_frontmatter(content2)
    assert yaml2["title"] == "My Quoted Title"
    assert yaml2["author"] == "Jane Doe"
    print("  Quoted values OK")

    # No frontmatter
    yaml3 = parse_yaml_frontmatter("Just some text without frontmatter.")
    assert yaml3 == {}
    print("  No frontmatter OK")

    # Empty frontmatter
    yaml4 = parse_yaml_frontmatter("---\n\n---\n\nBody.")
    assert yaml4 == {}
    print("  Empty frontmatter OK")


def test_resolve_reference_doc():
    with tempfile.TemporaryDirectory() as tmpdir:
        import journal
        orig_refs = journal._REFS_DIR

        # Create a fake refs dir
        fake_refs = Path(tmpdir) / "refs"
        fake_refs.mkdir()
        journal._REFS_DIR = fake_refs

        try:
            # No docs at all
            assert resolve_reference_doc({}) is None
            print("  Missing refs dir OK")

            # Create default
            (fake_refs / "double.docx").write_bytes(b"fake")
            result = resolve_reference_doc({})
            assert result is not None
            assert result.name == "double.docx"
            print("  Default fallback OK")

            # Explicit ref
            (fake_refs / "single.docx").write_bytes(b"fake")
            result = resolve_reference_doc({"spacing": "single"})
            assert result is not None
            assert result.name == "single.docx"
            print("  Explicit spacing OK")

            # Explicit spacing that doesn't exist falls back to default
            result = resolve_reference_doc({"spacing": "nonexistent"})
            assert result is not None
            assert result.name == "double.docx"
            print("  Missing explicit spacing fallback OK")
        finally:
            journal._REFS_DIR = orig_refs


def test_lua_filter_generation():
    # Basic filter
    basic = _lua_basic_filter()
    assert "function Pandoc" in basic
    assert "pageBreakBefore" in basic
    assert "Bibliography" in basic
    assert "w:hanging" in basic
    print("  Basic filter OK")

    # Coverpage filter
    yaml = {"title": "Test", "author": "Smith", "style": "chicago"}
    cover = _lua_coverpage_filter(yaml)
    assert "function Meta" in cover
    assert "function Pandoc" in cover
    assert "pageBreakBefore" in cover
    assert "w:hanging" in cover
    assert '"Test"' in cover or "Test" in cover
    print("  Coverpage filter OK")

    # Header filter
    yaml2 = {"title": "Essay", "author": "Doe", "style": "mla"}
    header = _lua_header_filter(yaml2)
    assert "function Meta" in header
    assert "function Pandoc" in header
    assert "w:hanging" in header
    assert "MLA" in header
    print("  Header filter OK")

    # Dispatcher
    assert _generate_lua_filter({"style": "chicago"}) == _lua_coverpage_filter({})
    assert _generate_lua_filter({"style": "mla"}) == _lua_header_filter({})
    assert _generate_lua_filter({}) == _lua_basic_filter()
    print("  Dispatcher OK")


def test_author_lastname():
    # Explicit lastname wins over a derived one.
    assert _author_lastname({"author": "Jane Doe", "lastname": "Smith"}) == "Smith"
    assert _author_lastname({"author": "Jane Doe"}) == "Doe"
    assert _author_lastname({"author": "Jane van der Berg"}) == "Berg"
    assert _author_lastname({"author": "Prince"}) == "Prince"
    assert _author_lastname({}) == ""
    assert _author_lastname({"author": "   "}) == ""
    print("  Lastname derivation OK")


def test_format_export_date():
    # Turabian and MLA render the same date differently; both drop the
    # zero padding, matching the two Lua format_date functions.
    turabian = {"date": "2026-01-05", "style": "chicago"}
    mla = {"date": "2026-01-05", "style": "mla"}
    assert _format_export_date(turabian) == "January 5, 2026"
    assert _format_export_date(mla) == "5 January 2026"
    # No style: behaves like Turabian, as the basic Lua filter does.
    assert _format_export_date({"date": "2026-12-31"}) == "December 31, 2026"
    # Anything unparseable passes through untouched.
    assert _format_export_date({"date": "Spring 2026"}) == "Spring 2026"
    assert _format_export_date({"date": "2026-13-01"}) == "2026-13-01"
    assert _format_export_date({}) == ""
    print("  Export date formatting OK")


def test_typst_str():
    assert _typst_str("plain") == '"plain"'
    # Quotes and backslashes must not break out of the literal -- these
    # come from user frontmatter, so they are the injection surface.
    assert _typst_str('say "hi"') == '"say \\"hi\\""'
    assert _typst_str("back\\slash") == '"back\\\\slash"'
    print("  Typst string quoting OK")


def test_typst_wrapper():
    y = {"title": "T", "author": "Jane Doe", "course": "C",
         "instructor": "I", "date": "2026-01-05", "style": "mla",
         "spacing": "single"}
    src = _typst_wrapper(y, "body.typ")
    assert '#import "journal.typ": conf' in src
    assert '#show: conf.with(' in src
    assert '#include "body.typ"' in src
    assert 'title: "T",' in src
    assert 'spacing: "single",' in src
    # Derived fields, not raw frontmatter.
    assert 'lastname: "Doe",' in src
    assert 'date: "5 January 2026",' in src
    # The bibliography is pandoc's job now, so the wrapper must not try to
    # hand Typst one -- that path renders note-style citations as nested
    # footnotes and loses them.
    assert "bib:" not in src and "csl:" not in src

    # Absent frontmatter still produces every parameter, so the template
    # never sees a missing argument.
    bare = _typst_wrapper({}, "body.typ")
    for key in ("title", "author", "course", "instructor", "date",
                "style", "spacing", "lastname"):
        assert f"{key}: " in bare, key
    # spacing falls back to the default rather than an empty string.
    assert 'spacing: "double",' in bare
    print("  Typst wrapper OK")


def test_typst_template_exists():
    # The wrapper imports this by name; a rename would only surface at
    # export time otherwise.
    assert (_TEMPLATES_DIR / "journal.typ").is_file()
    print("  Typst template present OK")


def test_template_selection():
    # style: is the single key. No style -- or no frontmatter at all --
    # is journal.typ, the docx-derived template, which is Turabian minus
    # the cover page.
    assert _template_name({}) == _DEFAULT_TEMPLATE == "journal.typ"
    assert _template_name({"style": ""}) == "journal.typ"
    assert _template_name({"style": None}) == "journal.typ"
    assert _template_name({"title": "no style key"}) == "journal.typ"

    # The two style-guide templates, tolerant of case and whitespace.
    assert _template_name({"style": "mla"}) == "mla.typ"
    assert _template_name({"style": "  MLA "}) == "mla.typ"
    assert _template_name({"style": "chicago"}) == "turabian.typ"
    assert _template_name({"style": "turabian"}) == "turabian.typ"

    # A typo must not cost a student their export.
    assert _template_name({"style": "mla-9"}) == "journal.typ"

    # template: was the old key and is gone; it must not still work.
    assert _template_name({"template": "mla"}) == "journal.typ"
    print("  Template selection OK")


def test_new_templates_exist():
    # Selected by name at export time, so a rename or a missing file only
    # surfaces when a student presses export.
    for name in ("journal.typ", "mla.typ", "turabian.typ"):
        assert (_TEMPLATES_DIR / name).is_file(), name
    print("  Style-guide templates present OK")


def test_new_templates_expose_conf():
    # _typst_wrapper emits `#import "journal.typ": conf` against whichever
    # file was copied in, so every template must expose conf() with the
    # same parameters or the wrapper fails to compile.
    required = ("title", "author", "course", "instructor", "date",
                "style", "spacing", "lastname")
    for name in ("mla.typ", "turabian.typ"):
        src = (_TEMPLATES_DIR / name).read_text(encoding="utf-8")
        assert "#let conf(" in src, name
        for param in required:
            assert f"{param}:" in src, (name, param)
    print("  Template conf() signatures OK")


def test_mla_date_keys_off_style():
    # MLA writes the day first. Everything else, including no style at
    # all, gets the month-first form.
    assert _format_export_date(
        {"date": "2026-08-14", "style": "mla"}) == "14 August 2026"
    assert _format_export_date({"date": "2026-08-14"}) == "August 14, 2026"
    assert _format_export_date(
        {"date": "2026-08-14", "style": "chicago"}) == "August 14, 2026"
    # The retired key must not smuggle MLA formatting back in.
    assert _format_export_date(
        {"date": "2026-08-14", "template": "mla"}) == "August 14, 2026"
    print("  MLA date keys off style OK")


def test_journal_template_untouched_by_new_ones():
    # The docx-derived template is the reference the LibreOffice chain is
    # compared against. If MLA fixes ever get applied to it by mistake,
    # that comparison silently stops meaning anything -- so pin the two
    # properties that make it docx-derived rather than style-guide-derived.
    src = (_TEMPLATES_DIR / "journal.typ").read_text(encoding="utf-8")
    # What actually separates the docx-derived template from the
    # style-guide ones: a paragraph gap and the docx top margin. MLA has
    # neither.
    #
    # Note this does NOT include the first-line indent. An earlier version
    # of this test asserted journal.typ had none, which pinned a bug in
    # place: refs/*.docx carries w:ind w:firstLine="720" and the template
    # had simply never transcribed it, so the two engines wrapped their
    # lines in different places. Both templates indent; they differ on
    # margin and paragraph gap.
    assert "para-extra" in src, "journal.typ lost its docx paragraph gap"
    assert "1.531in" in src, "journal.typ lost its docx top margin"
    mla = (_TEMPLATES_DIR / "mla.typ").read_text(encoding="utf-8")
    assert "para-extra" not in mla, "mla.typ gained a docx paragraph gap"
    assert "1.531in" not in mla, "mla.typ gained the docx top margin"
    print("  journal.typ still docx-derived OK")


def test_first_line_indent_matches_reference_docx():
    # refs/*.docx sets w:ind w:firstLine="720" on BodyText -- half an inch
    # on every paragraph. journal.typ exists to mirror those documents, so
    # if one grows an indent the other has to have it too.
    import zipfile, re as _re
    for ref in ("double.docx", "single.docx"):
        xml = zipfile.ZipFile(_REFS_DIR / ref).read(
            "word/styles.xml").decode("utf-8")
        m = _re.search(
            r'<w:style [^>]*w:styleId="BodyText".*?</w:style>', xml, _re.S)
        assert m and 'w:firstLine="720"' in m.group(0), ref
    src = (_TEMPLATES_DIR / "journal.typ").read_text(encoding="utf-8")
    assert "first-line-indent" in src and "0.5in" in src
    print("  First-line indent matches reference docx OK")


def test_line_box_pinned_explicitly():
    # text.top-edge: "ascender" resolves to the font's *typo* ascender --
    # 0.693em for real Times New Roman, not the 0.891em the leading
    # constants are derived against. Using the keyword silently shrinks
    # the line box to 0.907em and puts double spacing at 2.10em where
    # LibreOffice renders 2.30em. Every template must pin it by length.
    for name in ("journal.typ", "mla.typ", "turabian.typ"):
        src = (_TEMPLATES_DIR / name).read_text(encoding="utf-8")
        assert 'top-edge: "ascender"' not in src, name
        assert 'bottom-edge: "descender"' not in src, name
        assert "box-top = 0.891em" in src, name
        assert "box-bottom = -0.216em" in src, name
        assert "top-edge: box-top" in src, name
    print("  Line box pinned by length OK")


def test_journal_typ_has_no_style_branches():
    # journal.typ is now reached only by notes with no style: or an
    # unrecognised one -- mla and chicago have templates of their own. It
    # therefore renders its front matter unconditionally, and carries no
    # running head or footer, both of which belonged to those styles.
    #
    # The unconditional part matters: the front matter used to be guarded
    # on `style == "" or style == "basic"`, so a note whose style: was a
    # typo fell back to this template and then silently lost its title,
    # author and date.
    src = (_TEMPLATES_DIR / "journal.typ").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines()
                     if not l.lstrip().startswith("//"))
    assert "style ==" not in code, "journal.typ regained a style branch"
    assert "header:" not in code, "journal.typ regained a running head"
    assert "footer:" not in code, "journal.typ regained a footer"

    # The parameter itself has to stay: _typst_wrapper passes the same
    # arguments to every template, so dropping it breaks the import.
    assert "style:" in code
    for param in ("title", "author", "course", "instructor", "date",
                  "spacing", "lastname"):
        assert f"{param}:" in code, param
    print("  journal.typ is the unstyled template OK")


def test_default_csl_by_style():
    # Without this, pandoc falls back to its built-in chicago-author-date
    # and a Turabian note asking for footnotes silently renders
    # "(Smith 2020)" -- a plausible document in the wrong style.
    assert _default_csl_path({"style": "chicago"}).name == \
        "chicago-notes-bibliography.csl"
    assert _default_csl_path({"style": "turabian"}).name == \
        "chicago-notes-bibliography.csl"
    assert _default_csl_path({"style": "MLA "}).name == \
        "modern-language-association.csl"
    # No style, and unknown styles, stay on pandoc's default.
    assert _default_csl_path({}) is None
    assert _default_csl_path({"style": "apa"}) is None
    print("  Default CSL by style OK")


def test_explicit_csl_wins_over_default():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td)
        (vault / "sources").mkdir()
        own = vault / "sources" / "house.csl"
        own.write_text("<style/>", encoding="utf-8")

        # A vault that curated its own style keeps it.
        got = _resolve_csl_path({"style": "chicago", "csl": "sources/house.csl"}, vault)
        assert got == own, got

        # Named but missing -- an absolute path from another machine, say.
        # Better the style's default than pandoc's unrelated one.
        got = _resolve_csl_path(
            {"style": "chicago", "csl": "/gone/elsewhere.csl"}, vault)
        assert got is not None and got.name == "chicago-notes-bibliography.csl"

        # Still nothing to fall back to when the style implies no default.
        assert _resolve_csl_path({"csl": "/gone/elsewhere.csl"}, vault) is None
    print("  Explicit csl: wins over the default OK")


def test_bundled_csls_are_the_right_class():
    # class="note" is what makes Chicago render footnotes rather than
    # author-date; "in-text" is what MLA needs. Swapping the files for
    # the wrong variant would look fine until someone read the output.
    chicago = (_CSL_DIR / "chicago-notes-bibliography.csl").read_text(
        encoding="utf-8")
    assert 'class="note"' in chicago
    mla = (_CSL_DIR / "modern-language-association.csl").read_text(
        encoding="utf-8")
    assert 'class="in-text"' in mla
    # Redistributed under CC BY-SA; keep the rights element intact.
    for src in (chicago, mla):
        assert "creativecommons.org/licenses/by-sa" in src
    print("  Bundled CSLs are the right class OK")


def test_column_widths_fit_the_page():
    rows = [["Date", "Period", "Class", "Notes"],
            ["26 Aug", "1", "Rhetoric", "Lesson: Intro to thesis project"],
            ["14 Sep", "1", "Rhetoric",
             "Lesson: relationship and circumstance; speech 01 proposal work"]]
    w = _column_widths(rows)
    assert len(w) == 4
    assert sum(w) <= _TEXT_WIDTH_TWIPS, sum(w)
    # The prose column takes the slack; the narrow ones stay narrow.
    assert w[3] > sum(w[:3]), w
    # And none is squeezed below its longest word. pandoc's dash-derived
    # widths gave "Date" 5% of the page and wrapped it to three lines.
    for i, col in enumerate(("Date", "Period", "Class")):
        assert w[i] >= len(col) * 100, (col, w[i])
    print("  Column widths fit the page OK")


def test_column_widths_edge_cases():
    # A table of nothing must not divide by zero or emit a negative width.
    assert _column_widths([]) == []
    assert _column_widths([[]]) == []
    # Ragged rows: size to the widest row rather than crashing.
    w = _column_widths([["a"], ["a", "b", "c"]])
    assert len(w) == 3 and all(x > 0 for x in w)
    # Every column wanting more than its share still fits the page.
    long = "x" * 400
    w = _column_widths([[long, long, long]])
    assert sum(w) <= _TEXT_WIDTH_TWIPS and all(x > 0 for x in w), w
    print("  Column width edge cases OK")


def test_autofit_rewrites_table_widths():
    doc = (b'<w:document><w:body><w:tbl><w:tblGrid>'
           b'<w:gridCol w:w="392"/><w:gridCol w:w="6610"/></w:tblGrid>'
           b'<w:tr><w:tc><w:tcW w:type="dxa" w:w="392"/><w:p><w:r>'
           b'<w:t>Date</w:t></w:r></w:p></w:tc>'
           b'<w:tc><w:tcW w:type="dxa" w:w="6610"/><w:p><w:r>'
           b'<w:t>Notes about the lesson</w:t></w:r></w:p></w:tc></w:tr>'
           b'</w:tbl></w:body></w:document>')
    out = _autofit_tables(doc).decode("utf-8")
    assert 'w:w="392"' not in out, "pandoc's dash-derived width survived"
    assert out.count("<w:gridCol") == 2
    print("  Autofit rewrites table widths OK")


def test_cell_text_rows():
    tbl = ('<w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r>'
           '<w:r><w:t xml:space="preserve"> B</w:t></w:r></w:p></w:tc>'
           '<w:tc><w:p><w:r><w:t>C</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    # Runs within a cell must join: pandoc splits a cell across runs at
    # every formatting change, and measuring only the first would size
    # the column to a fragment.
    assert _cell_text_rows(tbl) == [["A B", "C"]]
    print("  Cell text extraction OK")


BIB_SAMPLE = """@string{jbl = {Journal of Biblical Literature}}

@article{alpha2020,
  title = {A Title (with an unclosed paren},
  abstract = {Prose (like this one has stray parens},
  journal = jbl,
}

@book{beta2021,
  title = {Another {{Braced}} Title},
  note = {He said "quoted" here},
}

@incollection{gamma2022,
  crossref = {beta2021},
  title = {Depends on beta},
}

@book{delta2023,
  title = {Unused},
}
"""


def test_bib_blocks_survive_unbalanced_parens():
    # The failure that made this necessary: a real 800-entry library has
    # abstracts with "(" and no ")", and counting parens as delimiters
    # made one entry swallow the remaining 710KB. BibTeX only treats
    # parens as delimiters when the entry opened with one.
    blocks = _bib_blocks(BIB_SAMPLE)
    keys = [k for _, k, _ in blocks if k]
    assert keys == ["alpha2020", "beta2021", "gamma2022", "delta2023"], keys
    kinds = [kind for kind, _, _ in blocks]
    assert kinds[0] == "string"
    print("  Bib parsing survives unbalanced parens OK")


def test_bib_blocks_paren_delimited_entry():
    # The other delimiter still has to work.
    blocks = _bib_blocks("@article(paren2020, title = {T})")
    assert [k for _, k, _ in blocks] == ["paren2020"], blocks
    print("  Paren-delimited entries OK")


def test_filter_bib_keeps_what_is_cited():
    out = _filter_bib(BIB_SAMPLE, {"alpha2020"})
    assert out and "alpha2020" in out
    assert "delta2023" not in out, "kept an uncited entry"
    # @string macros must survive: an entry referencing one renders
    # wrongly without it.
    assert "@string" in out
    print("  Filter keeps what is cited OK")


def test_filter_bib_follows_crossref():
    out = _filter_bib(BIB_SAMPLE, {"gamma2022"})
    assert out and "gamma2022" in out
    assert "beta2021" in out, "crossref target dropped"
    print("  Filter follows crossref OK")


def test_filter_bib_gives_up_rather_than_lose_a_source():
    # Nothing recognisable: better to hand pandoc the original than to
    # silently drop every citation.
    assert _filter_bib("not a bibliography at all", {"x"}) is None
    # A key that is not in the file at all cannot be satisfied by
    # filtering, so there is nothing to gain and a fallback is right.
    assert _filter_bib(BIB_SAMPLE, {"nosuchkey"}) is None
    print("  Filter gives up rather than lose a source OK")


def test_narrow_bib_falls_back_when_unhelpful():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        bib = d / "refs.bib"
        bib.write_text(BIB_SAMPLE, encoding="utf-8")
        # A note citing nothing keeps the original path.
        assert _narrow_bib(bib, "no citations here", d) == bib
        # A note citing something gets a smaller file.
        out = _narrow_bib(bib, "text [@alpha2020]", d)
        assert out != bib and out.exists()
        assert len(out.read_text(encoding="utf-8")) < len(BIB_SAMPLE)
        # A missing file is not fatal.
        assert _narrow_bib(d / "gone.bib", "[@alpha2020]", d) == d / "gone.bib"
    print("  Narrow-bib fallbacks OK")


def test_cited_keys_extraction():
    keys = _cited_keys("See [@a2020; @b2021] and @c2022 plus [-@d2023].")
    assert {"a2020", "b2021", "c2022", "d2023"} <= keys, keys
    # Trailing punctuation is not part of a key.
    assert "e2024" in _cited_keys("as noted by @e2024.")
    print("  Citekey extraction OK")


def test_rts_rejection_detected():
    # A pandoc built without -rtsopts fails when handed +RTS rather than
    # ignoring it, so the export retries without the flags. Recognising
    # that specific failure is what makes the retry safe: a real error
    # must not be mistaken for it and silently retried.
    class R:
        def __init__(self, rc, err): self.returncode, self.stderr = rc, err

    assert _rts_rejected(R(1, "pandoc: Most RTS options are disabled."))
    assert not _rts_rejected(R(0, ""))
    assert not _rts_rejected(R(1, "pandoc: source.md: does not exist"))
    assert not _rts_rejected(R(1, None))
    print("  RTS rejection detection OK")


def test_rts_flags_are_removable():
    # The retry strips the flags from the built argument list, so every
    # one of them must be an exact element rather than a fused token.
    args = ["pandoc", "body.md"]
    args[1:1] = list(_PANDOC_RTS)
    for f in _PANDOC_RTS:
        args.remove(f)
    assert args == ["pandoc", "body.md"], args
    assert _PANDOC_RTS[0] == "+RTS" and _PANDOC_RTS[-1] == "-RTS"
    print("  RTS flags removable OK")


def test_cite_timeout_is_larger():
    # The GC flags are several times slower, on hardware that is already
    # slow. A citing export must not be capped at the plain budget.
    assert _PANDOC_CITE_TIMEOUT > _PANDOC_TIMEOUT * 5
    print("  Citeproc timeout headroom OK")


def test_strip_bib_noise_removes_only_noise():
    src = """@article{a2020,
  title = {Kept},
  abstract = {Dropped, with {nested} braces and a stray ( paren},
  shorttitle = {Kept Too},
  file = {/path/with:colons/x.pdf},
  keywords = {one, two},
  year = {2020},
}
"""
    out, n = _strip_bib_noise(src)
    assert n == 3, n
    for gone in ("abstract", "file =", "keywords"):
        assert gone not in out, gone
    # shorttitle is what Chicago's shortened notes render; losing it
    # silently changes every repeat citation.
    for kept in ("title", "shorttitle", "Kept Too", "year", "a2020"):
        assert kept in out, kept
    # Still parses as one entry afterwards.
    assert [k for _, k, _ in _bib_blocks(out) if k] == ["a2020"]
    print("  Bib noise stripping OK")


def test_strip_bib_noise_leaves_unterminated_fields_alone():
    # A value that never closes cannot be removed safely; truncating the
    # file is worse than leaving one abstract in place.
    src = "@article{a, abstract = {never closes and never will\n"
    out, n = _strip_bib_noise(src)
    assert n == 0, n
    assert out == src, "input was modified despite the field being unusable"
    print("  Unterminated field left alone OK")


def test_bib_value_end_forms():
    assert _bib_value_end("{abc}", 0) == 5          # braced
    assert _bib_value_end('"abc"', 0) == 5          # quoted
    assert _bib_value_end("abc,", 0) == 3           # bare
    assert _bib_value_end("{a{b}c}", 0) == 7        # nested
    assert _bib_value_end("{unclosed", 0) is None
    print("  Bib value delimiters OK")


def test_bib_openers_is_independent_of_block_parsing():
    # This scan exists to check _bib_blocks' work, so it must not share
    # its brace matching -- including on the unbalanced-paren case that
    # broke that parser.
    src = "@book{x, title = {A ( paren}}\n@book{y, title = {B}}\n"
    assert _bib_openers(src) == ["x", "y"]
    print("  Independent opener scan OK")


def test_typst_writer_disables_native_citations():
    # The Typst writer emits #cite(<key>) when it can, which needs a
    # #bibliography() the templates deliberately do not declare -- so the
    # export must ask for citeproc's rendered text instead. Whether a
    # given pandoc does this by default varies by version; 3.1.11.1 on a
    # writerdeck does, 3.10 does not, and the export cannot depend on it.
    src = (Path(__file__).parent / "journal.py").read_text(encoding="utf-8")
    assert '"--to", "typst-citations"' in src, "typst writer may emit #cite()"
    assert '"--to", "typst",' not in src, "a bare typst writer target remains"
    print("  Typst native citations disabled OK")


def test_turabian_heading_levels():
    # Headings follow the CMOS presentation the Purdue OWL sample paper
    # shows -- flush left, bold then italic -- rather than Turabian's
    # prescribed centred scheme. Chicago does not prescribe one; it asks
    # for a consistent hierarchy. Nothing may be centred, and nothing may
    # grow: the hierarchy is placement and weight, never size.
    src = (_TEMPLATES_DIR / "turabian.typ").read_text(encoding="utf-8")
    body = "\n".join(l for l in src.splitlines()
                     if not l.lstrip().startswith("//"))
    heads = body[body.index("show heading"):body.index("show quote")]
    assert "align(center)" not in heads, "a heading is centred again"
    for bad in ("20pt", "16pt", "14pt"):
        assert bad not in heads, bad

    # Level 1 bold, level 2 italic, and both as set rules so they keep
    # their own line -- a content rule yields inline material and runs
    # the heading into the paragraph below.
    for lvl, prop in ((1, 'weight: "bold"'), (2, 'style: "italic"')):
        i = heads.index(f"heading.where(level: {lvl})")
        seg = heads[i:i + 90]
        assert "set text" in seg and prop in seg, (lvl, seg)

    # Level 5 is the exception: it must be inline, because the heading
    # and the sentence after it are one paragraph.
    j = heads.index("heading.where(level: 5)")
    assert "box(" in heads[j:j + 90]

    # An extra line space above, none below, per the same guidance.
    i = heads.index("set block(")
    assert "line-advance" in heads[i:i + 90], heads[i:i + 90]
    print("  CMOS heading levels OK")


def test_bundled_fonts_present_and_licensed():
    # The bundle is what makes output identical everywhere: without it a
    # minimal writerdeck matches none of the families the templates name
    # and typst silently substitutes its own default.
    for f in ("De-Gruyter-Serif-Regular.otf", "De-Gruyter-Serif-Bold.otf",
              "De-Gruyter-Serif-Italic.otf", "De-Gruyter-Serif-Bold-Italic.otf",
              "De-Gruyter-Sans-Math-Regular.otf"):
        assert (_FONTS_DIR / f).is_file(), f

    # OFL requires its text to travel with the font. Shipping the font
    # without it is a licence violation, not an oversight.
    lic = (_FONTS_DIR / "LICENSE").read_text(encoding="utf-8")
    assert "SIL Open Font License" in lic and "1.1" in lic
    print("  Bundled fonts and licence OK")


def test_templates_name_the_bundled_face_first():
    # First in the list is the one guaranteed to resolve. If a system
    # face were listed ahead of it, output would differ per machine --
    # which is the problem the bundle exists to remove.
    for name in ("journal.typ", "mla.typ", "turabian.typ"):
        src = (_TEMPLATES_DIR / name).read_text(encoding="utf-8")
        i = src.index("#let body-fonts = (")
        head = src[i:i + 120]
        assert head.split("(", 1)[1].lstrip().startswith('"De Gruyter Serif"'), name
        assert "math-fonts" in src, name
    print("  Templates prefer the bundled face OK")


def test_rts_is_bound_before_it_is_read():
    # An export *without* a bibliography died on "cannot access local
    # variable 'rts'": it was bound only inside the citing branch and
    # read unconditionally after it, so the common case -- a note with no
    # citations -- raised every time.
    #
    # This is a narrow guard for one variable, and deliberately so. Two
    # broader approaches were tried and dropped: pyflakes does not detect
    # conditional binding at all, and a hand-written AST pass produced
    # false positives on every if/else nested inside a loop, because
    # deciding what is "read afterwards" needs real control-flow
    # analysis rather than line numbers.
    #
    # The honest gap is that the export coroutine lives inside
    # create_app and no test can run it. Until that changes, bugs on
    # that path are found by exporting, not by this file.
    import ast
    src = (Path(__file__).parent / "journal.py").read_text(encoding="utf-8")
    for fn in ast.walk(ast.parse(src)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        binds, reads = [], []
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id == "rts":
                (binds if isinstance(node.ctx, ast.Store) else reads).append(
                    node.lineno)
        if not reads:
            continue
        assert binds and min(binds) < min(reads), (
            "rts is read at line %d before any binding" % min(reads))
    print("  rts bound before read OK")


def test_pdf_engine_routing():
    saved = os.environ.pop("JOURNAL_PDF_ENGINE", None)
    try:
        have_typst = detect_typst() is not None

        # The setting is honoured when nothing overrides it.
        assert _pdf_engine({}, "libreoffice") == "libreoffice"
        if have_typst:
            assert _pdf_engine({}, "typst") == "typst"
            assert _pdf_engine({"spacing": "single"}, "typst") == "typst"
            assert _pdf_engine({"spacing": "double"}, "typst") == "typst"
        else:
            # Never route to an engine whose binary is missing.
            assert _pdf_engine({}, "typst") == "libreoffice"

        # A spacing the template cannot express names a reference .docx,
        # so those notes must keep going through LibreOffice.
        for spacing in ("quiz", "dg.double", "dg.single", "whatever"):
            assert _pdf_engine({"spacing": spacing}, "typst") == "libreoffice"

        # The env var outranks both the setting and the spacing rule.
        os.environ["JOURNAL_PDF_ENGINE"] = "libreoffice"
        assert _pdf_engine({"spacing": "single"}, "typst") == "libreoffice"
        if have_typst:
            os.environ["JOURNAL_PDF_ENGINE"] = "typst"
            assert _pdf_engine({"spacing": "quiz"}, "libreoffice") == "typst"
        # An unrecognised value is ignored rather than obeyed.
        os.environ["JOURNAL_PDF_ENGINE"] = "nonsense"
        assert _pdf_engine({}, "libreoffice") == "libreoffice"
    finally:
        os.environ.pop("JOURNAL_PDF_ENGINE", None)
        if saved is not None:
            os.environ["JOURNAL_PDF_ENGINE"] = saved
    print("  PDF engine routing OK")


def test_resolve_bib_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        named = vault / "sources.bib"
        named.write_text("@book{a, title={A}}\n", encoding="utf-8")

        # bibliography: resolves relative to the vault.
        assert _resolve_bib_path({"bibliography": "sources.bib"}, vault) == named
        # An absolute path is honoured as given.
        assert _resolve_bib_path({"bibliography": str(named)}, vault) == named
        # A name that does not exist falls back to the vault-wide search,
        # which finds the one .bib present.
        assert _resolve_bib_path({"bibliography": "missing.bib"}, vault) == named

    with tempfile.TemporaryDirectory() as tmpdir:
        # Nothing to find at all.
        assert _resolve_bib_path({"bibliography": "x.bib"}, Path(tmpdir)) is None
    print("  Bib path resolution OK")


def test_initial_pdf_engine():
    # Devices already in the field must not have their export engine
    # swapped by an update. Some of them belong to people we cannot
    # reach, so a silent switch is a device that simply stops working.
    import journal as J
    with tempfile.TemporaryDirectory() as tmpdir:
        cfgp = Path(tmpdir) / "config.json"
        orig = J._config_path
        J._config_path = lambda: cfgp
        try:
            # No config file at all -> genuinely fresh install.
            assert not cfgp.exists()
            assert _initial_pdf_engine({}) == "typst"

            # Config exists but predates the setting -> leave it alone.
            cfgp.write_text('{"vault": "/home/x/Documents"}', encoding="utf-8")
            assert _initial_pdf_engine({"vault": "/home/x/Documents"}) == "libreoffice"

            # An explicit choice always wins, either way.
            assert _initial_pdf_engine({"pdf_engine": "typst"}) == "typst"
            assert _initial_pdf_engine({"pdf_engine": "libreoffice"}) == "libreoffice"

            # A junk value is not an explicit choice.
            assert _initial_pdf_engine({"pdf_engine": "nonsense"}) == "libreoffice"
        finally:
            J._config_path = orig
    print("  Initial PDF engine OK")


def test_strip_frontmatter():
    # An unquoted colon in a title is valid to Journal's parser and fatal
    # to pandoc's. The Typst path does not need pandoc to read metadata,
    # so the block is removed before it can be rejected.
    doc = ("---\n"
           "title: Freedom in Galatians: Conclusion\n"
           "author: Charles Cisco\n"
           "---\n"
           "# Heading\n\nBody text.\n")
    body = _strip_frontmatter(doc)
    assert body.startswith("# Heading")
    assert "title:" not in body and "Charles Cisco" not in body
    # Journal's own parser still gets the colon title right.
    assert parse_yaml_frontmatter(doc)["title"] == "Freedom in Galatians: Conclusion"

    # No frontmatter: unchanged.
    plain = "# Just a heading\n\nText.\n"
    assert _strip_frontmatter(plain) == plain

    # A --- rule in the body must not be mistaken for a fence.
    mid = "Text.\n\n---\n\nMore text.\n"
    assert _strip_frontmatter(mid) == mid

    # Empty frontmatter still strips.
    assert _strip_frontmatter("---\n\n---\nBody\n") == "Body\n"
    print("  Frontmatter stripping OK")


def test_resolve_csl_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        (vault / "sources").mkdir()
        csl = vault / "sources" / "chicago.csl"
        csl.write_text("<style/>", encoding="utf-8")

        # Absolute path as written.
        assert _resolve_csl_path({"csl": str(csl)}, vault) == csl
        # Vault-relative.
        assert _resolve_csl_path({"csl": "sources/chicago.csl"}, vault) == csl
        # An absolute path from the *other* machine still resolves by name:
        # frontmatter is written on whichever device the note was edited on.
        assert _resolve_csl_path(
            {"csl": "/home/charles/Documents/vault/sources/chicago.csl"},
            vault) == csl
        # Absent or unfindable.
        assert _resolve_csl_path({}, vault) is None
        assert _resolve_csl_path({"csl": "nope.csl"}, vault) is None
    print("  CSL path resolution OK")


def test_bundled_bin():
    # Nothing is bundled in a source checkout, so this must not invent a
    # path -- otherwise detect_* would return a binary that cannot run.
    assert _bundled_bin("definitely-not-a-real-tool") is None
    print("  Bundled binary lookup OK")


def test_env_bin():
    # An unset or empty variable must fall through to the other lookups
    # rather than returning "" and short-circuiting them.
    os.environ.pop("JOURNAL_TEST_BIN", None)
    assert _env_bin("JOURNAL_TEST_BIN") is None
    os.environ["JOURNAL_TEST_BIN"] = ""
    assert _env_bin("JOURNAL_TEST_BIN") is None

    # A path that does not exist is worse than useless: honouring it
    # would report a tool as present and then fail at export time.
    os.environ["JOURNAL_TEST_BIN"] = "/nonexistent/pandoc"
    assert _env_bin("JOURNAL_TEST_BIN") is None

    with tempfile.NamedTemporaryFile(suffix="-pandoc") as tf:
        os.environ["JOURNAL_TEST_BIN"] = tf.name
        assert _env_bin("JOURNAL_TEST_BIN") == tf.name
    os.environ.pop("JOURNAL_TEST_BIN", None)
    print("  Env-var binary override OK")


def test_env_bin_wins_in_detectors():
    # The whole point of the override: a Tauri sidecar stored under a
    # target-triple name must beat anything found on PATH.
    with tempfile.NamedTemporaryFile(suffix="-aarch64-apple-darwin") as tf:
        os.environ["JOURNAL_PANDOC"] = tf.name
        os.environ["JOURNAL_TYPST"] = tf.name
        try:
            assert detect_pandoc() == tf.name
            assert detect_typst() == tf.name
        finally:
            os.environ.pop("JOURNAL_PANDOC", None)
            os.environ.pop("JOURNAL_TYPST", None)
    print("  Sidecar override beats PATH OK")


def test_config_path():
    p = _config_path()
    assert p.name == "config.json"
    assert p.parent.name == "journal"
    # POSIX must keep the path every existing writerdeck already uses;
    # moving it would strand their configured vault.
    if sys.platform != "win32":
        assert p == Path.home() / ".config" / "journal" / "config.json"
    print("  Config path OK")


def test_default_vault():
    v = _default_vault()
    assert v.name == "Journal"
    assert v.parent == Path.home() / "Documents"
    # Must not create anything as a side effect of being asked.
    print("  Default vault location OK")


def test_normalise_pasted():
    # POSIX pastes must pass through untouched -- pbpaste and
    # wl-paste --no-newline already return exactly the right bytes.
    if sys.platform != "win32":
        assert _normalise_pasted("a\r\nb\n") == "a\r\nb\n"
        print("  Paste normalisation is POSIX no-op OK")
        return
    assert _normalise_pasted("a\r\nb\r\n") == "a\nb"
    assert _normalise_pasted("plain") == "plain"
    assert _normalise_pasted("") == ""
    print("  Paste normalisation OK")


def test_no_console():
    kwargs = _no_console()
    if sys.platform == "win32":
        assert "creationflags" in kwargs
    else:
        # Must be empty on POSIX: passing creationflags there is a
        # TypeError, so every shell-out would break at once.
        assert kwargs == {}
    print("  No-console subprocess kwargs OK")


def test_detect_clipboard_shape():
    copy_cmd, paste_cmd = _detect_clipboard()
    # Detection is allowed to find nothing (headless CI, no wl-copy), but
    # it must never return a half-pair -- _try_paste guards on the paste
    # command alone and would then run a copy command as a paste.
    assert (copy_cmd is None) == (paste_cmd is None)
    if copy_cmd is not None:
        assert isinstance(copy_cmd, list) and isinstance(paste_cmd, list)
    print("  Clipboard detection shape OK")


class _as_platform:
    """Run a block as though on another OS.

    The Windows branches are the reason this phase exists, and a Mac can
    never reach them otherwise -- so they would ship having never once
    been executed. Every shim reads sys.platform at call time, which is
    what makes this possible; keep it that way.
    """

    def __init__(self, name, **env):
        self.name = name
        self.env = env

    def __enter__(self):
        self._real = sys.platform
        self._saved = {k: os.environ.get(k) for k in self.env}
        sys.platform = self.name
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        sys.platform = self._real
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def test_config_path_windows():
    with _as_platform("win32", APPDATA=r"C:\Users\Kid\AppData\Roaming"):
        p = _config_path()
        assert p.parts[-2:] == ("journal", "config.json"), p
        assert "Roaming" in str(p), p

    # A missing APPDATA must not put config in ~/.config on Windows or
    # crash on Path(None) -- it falls back to the standard location.
    with _as_platform("win32", APPDATA=None):
        p = _config_path()
        assert "Roaming" in str(p), p
        assert ".config" not in str(p), p
    print("  Windows config path OK")


def test_normalise_pasted_windows():
    with _as_platform("win32"):
        # CRLF would otherwise leave stray \r rendering as control chars.
        assert _normalise_pasted("a\r\nb\r\n") == "a\nb"
        # Bare CR too, which some apps still put on the clipboard.
        assert _normalise_pasted("a\rb") == "a\nb"
        # Only ONE trailing newline is PowerShell's; a deliberate blank
        # line at the end of a copied passage must survive.
        assert _normalise_pasted("a\r\n\r\n") == "a\n"
        assert _normalise_pasted("plain") == "plain"
        assert _normalise_pasted("") == ""
    print("  Windows paste normalisation OK")


def test_no_console_windows():
    with _as_platform("win32"):
        kwargs = _no_console()
        assert "creationflags" in kwargs
        # Zero would silently mean "no flag", so a console could still
        # flash; the constant must actually have been found.
        assert kwargs["creationflags"] != 0
    print("  Windows no-console flag OK")


def test_powershell_paste_command():
    # Both halves matter and neither is obvious, so pin them: -Raw keeps
    # the clipboard as one string instead of an array of lines, and the
    # UTF-8 line stops the console codepage mangling curly quotes.
    joined = " ".join(journal._PS_PASTE)
    assert "-Raw" in joined
    assert "UTF8" in joined
    assert "-NoProfile" in joined
    print("  PowerShell paste command OK")


def test_safe_entry_name():
    # The motivating case: a colon in an essay title is completely
    # natural and is illegal in a Windows filename.
    assert ":" not in safe_entry_name("Chapter 1: The Beginning")
    assert safe_entry_name("Chapter 1: The Beginning") == "Chapter 1- The Beginning"

    # Every illegal character must go, backslash included -- on Windows
    # it is a separator, so leaving it would silently create a directory.
    cleaned = safe_entry_name("a" + _ILLEGAL_CHARS + "b")
    assert not any(c in cleaned for c in _ILLEGAL_CHARS), cleaned

    # Forward slash is meaningful (rename into a subfolder) and must
    # survive, while its components are still cleaned.
    assert safe_entry_name("notes/Chapter: One") == "notes/Chapter- One"

    # Reserved device names are refused by Windows whatever the
    # extension, so NUL.md is not a file that can exist.
    for reserved in ("CON", "nul", "COM1", "LPT9"):
        out = safe_entry_name(reserved)
        assert out.upper() not in ("CON", "NUL", "COM1", "LPT9"), out

    # Trailing dots and spaces are silently dropped by Windows, so the
    # file written is not the file looked for afterwards.
    assert safe_entry_name("draft.") == "draft"
    assert safe_entry_name("draft ") == "draft"

    # A typed name must never escape the vault.
    assert ".." not in safe_entry_name("../../etc/passwd")
    assert safe_entry_name("../../etc/passwd") == "etc/passwd"

    # Control characters are illegal on Windows and useless everywhere.
    assert "\x01" not in safe_entry_name("a\x01b")

    # Ordinary names must come through completely untouched.
    for ok in ("Monday", "notes/2026-08-14", "A Room of One's Own"):
        assert safe_entry_name(ok) == ok, ok
    print("  Filename sanitisation OK")


def test_create_entry_sanitises():
    with tempfile.TemporaryDirectory() as td:
        storage = VaultStorage(Path(td))
        entry = storage.create_entry("Chapter 1: The Beginning")
        # The file must actually exist under the cleaned name -- this is
        # the assertion that would fail on Windows before the fix.
        assert entry.path.exists()
        assert ":" not in entry.path.name

        # A name that sanitises away entirely still has to produce a file
        # rather than creating ".md" or throwing.
        blank = storage.create_entry("...")
        assert blank.path.exists()
        assert blank.path.stem
    print("  create_entry sanitisation OK")


def test_export_writes_utf8():
    # The export path wrote source.md with no encoding=, which on Windows
    # means cp1252 until Python 3.15. That fails two different ways, and
    # the quieter one is the more damaging.

    # 1. Silent corruption. cp1252 *can* hold curly quotes and em dashes
    #    (0x91-0x97), so nothing raises -- but pandoc reads UTF-8, so it
    #    sees different characters than the student typed.
    smart = "He said “hello” — then left."
    as_cp1252 = smart.encode("cp1252")
    try:
        round_tripped = as_cp1252.decode("utf-8")
        assert round_tripped != smart, "expected mojibake, got clean text"
    except UnicodeDecodeError:
        pass  # also fine: pandoc would reject the file outright

    # 2. Hard failure. Anything outside cp1252's 256 characters cannot be
    #    written at all -- Greek in a classics essay, any CJK, an arrow.
    for hostile in ("λόγος", "日本語", "a → b"):
        try:
            hostile.encode("cp1252")
            raise AssertionError(f"expected cp1252 to reject {hostile!r}")
        except UnicodeEncodeError:
            pass

    # With an explicit encoding both cases round-trip exactly.
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "source.md"
        text = smart + " λόγος 日本語 a → b"
        p.write_text(text, encoding="utf-8")
        assert p.read_text(encoding="utf-8") == text
    print("  UTF-8 export round-trip OK")


def test_no_default_encoding_io():
    # A regression guard for the whole class: any text I/O without an
    # explicit encoding is locale-dependent, and the locale is only
    # UTF-8 on the machines we happen to develop on.
    src = (Path(__file__).parent / "journal.py").read_text(encoding="utf-8")
    offenders = []
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for call in ("read_text()", ".write_text("):
            if call in stripped and "encoding=" not in stripped:
                # write_text spanning lines is checked by the suite run
                # under -X warn_default_encoding in CI.
                if call == ".write_text(" and stripped.endswith("("):
                    continue
                offenders.append(f"{i}: {stripped[:70]}")
    assert not offenders, "text I/O without encoding=:\n" + "\n".join(offenders)
    print("  No default-encoding text I/O OK")


def test_postprocess_docx():
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "test.docx")

        # Create a minimal DOCX zip with a header containing {{LASTNAME}}
        header_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p><w:r><w:t>{{LASTNAME}} </w:t></w:r></w:p>
</w:hdr>"""
        footer_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p><w:r><w:t>Page footer</w:t></w:r></w:p>
</w:ftr>"""
        with zipfile.ZipFile(docx_path, "w") as zf:
            zf.writestr("word/header1.xml", header_xml)
            zf.writestr("word/footer1.xml", footer_xml)
            zf.writestr("word/document.xml", b"<w:document/>")

        # Test coverpage format: strips headers, keeps footers, replaces lastname
        _postprocess_docx(docx_path, {"author": "John Smith", "style": "chicago"})
        with zipfile.ZipFile(docx_path, "r") as zf:
            header = zf.read("word/header1.xml").decode("utf-8")
            footer = zf.read("word/footer1.xml").decode("utf-8")
            # Header should be stripped (empty)
            assert "{{LASTNAME}}" not in header
            assert "Smith" not in header  # stripped, not replaced
            assert "Header" in header  # has the empty header style
            # Footer should be preserved
            assert "Page footer" in footer
        print("  Coverpage postprocess OK")

        # Rebuild for header format test
        with zipfile.ZipFile(docx_path, "w") as zf:
            zf.writestr("word/header1.xml", header_xml)
            zf.writestr("word/footer1.xml", footer_xml)
            zf.writestr("word/document.xml", b"<w:document/>")

        # Test header format: keeps headers (with replacement), strips footers
        _postprocess_docx(docx_path, {"author": "Jane Doe", "style": "mla"})
        with zipfile.ZipFile(docx_path, "r") as zf:
            header = zf.read("word/header1.xml").decode("utf-8")
            footer = zf.read("word/footer1.xml").decode("utf-8")
            # Header should have lastname replaced
            assert "Doe " in header
            assert "{{LASTNAME}}" not in header
            # Footer should be stripped
            assert "Page footer" not in footer
            assert "Footer" in footer  # has the empty footer style
        print("  Header postprocess OK")

        # Rebuild for no-author test
        with zipfile.ZipFile(docx_path, "w") as zf:
            zf.writestr("word/header1.xml", header_xml)
            zf.writestr("word/document.xml", b"<w:document/>")

        _postprocess_docx(docx_path, {"style": "mla"})
        with zipfile.ZipFile(docx_path, "r") as zf:
            header = zf.read("word/header1.xml").decode("utf-8")
            # No author: placeholder removed, not replaced
            assert "{{LASTNAME}}" not in header
        print("  No-author postprocess OK")


def test_detect_tools():
    # These should return str or None, never raise
    pandoc = detect_pandoc()
    assert pandoc is None or isinstance(pandoc, str)
    print(f"  detect_pandoc: {pandoc or '(not found)'}")

    lo = detect_libreoffice()
    assert lo is None or isinstance(lo, str)
    print(f"  detect_libreoffice: {lo or '(not found)'}")


def test_list_continuation():
    cases = {
        "- item": (False, "- "),
        "* item": (False, "* "),
        "+ item": (False, "+ "),
        "1. item": (False, "2. "),
        "3) item": (False, "4) "),
        "- [ ] task": (False, "- [ ] "),
        "- [x] done": (False, "- [ ] "),
        "  - nested": (False, "  - "),
        "   1. deep": (False, "   2. "),
        "- ": (True, ""),
        "1. ": (True, ""),
        "- [ ] ": (True, ""),
        "plain text": None,
        "---": None,
        "-": None,
        "# heading": None,
        "": None,
    }
    for line, expected in cases.items():
        got = _list_continuation(line)
        assert got == expected, f"{line!r}: {got!r} != {expected!r}"
    print("  List continuation OK")


def test_iter_md_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        v = Path(tmpdir)
        storage = VaultStorage(v)
        (v / "a.md").write_text("x", encoding="utf-8")
        (v / "sub").mkdir()
        (v / "sub" / "b.md").write_text("x", encoding="utf-8")
        (v / ".stversions").mkdir()
        (v / ".stversions" / "old.md").write_text("x", encoding="utf-8")
        (v / ".trash").mkdir()
        (v / ".trash" / "t.md").write_text("x", encoding="utf-8")
        (v / ".hidden.md").write_text("x", encoding="utf-8")
        (v / "pdf" / "p.md").write_text("x", encoding="utf-8")
        names = sorted(p.relative_to(v).as_posix()
                       for p in storage.iter_md_paths())
        assert names == ["a.md", "sub/b.md"], names
    print("  Hidden/trash/export dirs excluded OK")


def test_soft_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = VaultStorage(Path(tmpdir))
        e = storage.create_entry("Note")
        e.path.write_text("body", encoding="utf-8")
        storage.delete_entry(e)
        assert not e.path.exists()
        assert (Path(tmpdir) / ".trash" / "Note.md").read_text(encoding="utf-8") == "body"
        # Collision bumps instead of overwriting the trashed copy
        e2 = storage.create_entry("Note")
        e2.path.write_text("body2", encoding="utf-8")
        storage.delete_entry(e2)
        assert (Path(tmpdir) / ".trash" / "Note 2.md").read_text(encoding="utf-8") == "body2"
    print("  Soft delete to .trash OK")


def test_ensure_writable():
    if getattr(os, "geteuid", lambda: 1)() == 0:
        print("  (skipped: running as root)")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        # The repair path is POSIX-only by nature: Windows carries the
        # read-only bit on files, not directories, so os.chmod cannot
        # make one unwritable and the precondition simply cannot be set
        # up. Permissions there are ACLs, which chmod does not touch --
        # so _ensure_writable's mkdir half is all that runs, and that is
        # exercised by the nested case below.
        if sys.platform != "win32":
            d = Path(tmpdir) / "ro"
            d.mkdir()
            os.chmod(d, 0o555)
            assert not os.access(d, os.W_OK)
            assert _ensure_writable(d) is True
            assert os.access(d, os.W_OK)
            os.chmod(d, 0o755)
        # Missing directories are created
        nested = Path(tmpdir) / "new" / "nested"
        assert _ensure_writable(nested) is True
        assert nested.is_dir()
    print("  Read-only dir repair OK")


def test_detect_printers():
    class R:
        def __init__(self, rc, out):
            self.returncode = rc
            self.stdout = out

    orig = journal.subprocess.run

    def via_e(args, **kw):
        if args[:2] == ["lpstat", "-e"]:
            return R(0, "P_One\nP_Two\n")
        return R(1, "")

    def via_a(args, **kw):
        if args[:2] == ["lpstat", "-e"]:
            return R(1, "")
        return R(0, "HP accepting requests since now\n")

    def none(args, **kw):
        return R(1, "")

    try:
        journal.subprocess.run = via_e
        assert journal._detect_printers() == ["P_One", "P_Two"]
        journal.subprocess.run = via_a
        assert journal._detect_printers() == ["HP"]
        journal.subprocess.run = none
        assert journal._detect_printers() == []
    finally:
        journal.subprocess.run = orig
    print("  lpstat -e primary, -a fallback OK")


def test_markdown_lexer():
    from prompt_toolkit.document import Document
    doc = "\n".join([
        "---", "tags: x", "---",
        "# H",
        "- [ ] task",
        "see [[Wiki]]",
        "> quote",
        "---",
        "-",
    ])
    gl = MarkdownLexer().lex_document(Document(doc))
    assert gl(0) == [("class:md.frontmatter", "---")]
    assert gl(1) == [("class:md.frontmatter", "tags: x")]
    assert gl(2) == [("class:md.frontmatter", "---")]
    assert gl(3)[0][0] == "class:md.heading-marker"
    assert gl(4)[0] == ("class:md.list-marker", "- [ ]")
    assert any(s == "class:md.wikilink" for s, _ in gl(5))
    assert gl(6)[0] == ("class:md.quote-marker", "> ")
    assert gl(7) == [("", "---")]   # mid-document HR is not frontmatter
    assert gl(8) == [("", "-")]     # lone dash is not a list
    # Leading --- with no closing fence is not treated as frontmatter
    gl2 = MarkdownLexer().lex_document(Document("---\nno close"))
    assert gl2(0) == [("", "---")]
    # Footnote highlight is only terminated by an UNESCAPED ]
    gl3 = MarkdownLexer().lex_document(
        Document("x ^[whole \\[Mosaic\\] law, see \\[ὅλον\\]] after"))
    fn = [t for s, t in gl3(0) if s == "class:md.footnote"]
    assert fn == ["^[whole \\[Mosaic\\] law, see \\[ὅλον\\]]"], fn
    print("  Wikilink/quote/frontmatter lexing OK")


def test_clipboard_paste_no_clobber():
    orig_cmds = (journal._CLIP_COPY_CMD, journal._CLIP_PASTE_CMD)
    orig_detect = journal._detect_clipboard
    calls = {"detect": 0}

    def spy_detect():
        calls["detect"] += 1
        return (["false"], ["false"])

    try:
        journal._detect_clipboard = spy_detect
        # Paste cmd configured but failing: must NOT re-detect (the probe
        # writes "" to the clipboard and would wipe what we're reading).
        journal._CLIP_COPY_CMD = ["false"]
        journal._CLIP_PASTE_CMD = ["false"]
        assert journal._clipboard_paste() is None
        assert calls["detect"] == 0
        # No paste tool at all: nothing to clobber, re-detect once.
        journal._CLIP_PASTE_CMD = None
        journal._clipboard_paste()
        assert calls["detect"] == 1
    finally:
        journal._detect_clipboard = orig_detect
        journal._CLIP_COPY_CMD, journal._CLIP_PASTE_CMD = orig_cmds
    print("  Paste retry without clipboard clobber OK")


def test_run_power():
    import journal
    real = journal.subprocess.Popen
    try:
        calls = []
        def fake(cmd, *a, **k):
            calls.append(cmd)
            if cmd[0] == "/sbin/shutdown":   # simulate /sbin not on PATH
                raise FileNotFoundError(2, "No such file", cmd[0])
            return object()
        journal.subprocess.Popen = fake
        assert journal._run_power(reboot=True) is True
        assert calls[0][0] == "/sbin/shutdown"          # tried first
        assert calls[1][0] == "/usr/sbin/shutdown"      # fell through
        assert "-r" in calls[1]                         # reboot flag
        # All candidates missing -> False, no exception
        journal.subprocess.Popen = lambda cmd, *a, **k: (
            _ for _ in ()).throw(FileNotFoundError(2, "x", cmd[0]))
        assert journal._run_power() is False
    finally:
        journal.subprocess.Popen = real
    print("  Power command fallback OK")


def test_extract_headings():
    from journal import _extract_headings
    t = ("# Title\n\nintro\n\n## Section A\nbody\n\n"
         "```\n# not a heading\n```\n\n### Sub B\nx\n## Section C\n")
    h = _extract_headings(t)
    assert [lvl for _, lvl, _ in h] == [1, 2, 3, 2]      # fence # skipped
    assert [title for _, _, title in h] == \
        ["Title", "Section A", "Sub B", "Section C"]
    assert [i for i, _, _ in h] == [0, 4, 11, 13]
    assert _extract_headings("no headings here\njust text") == []
    # '#' without a space is not a heading; trailing space title trims
    assert _extract_headings("#nospace\n#  spaced  ") == [(1, 1, "spaced")]
    print("  Heading extraction OK")


def test_nmcli_parse():
    from journal import (_parse_nmcli_terse, _parse_wifi_list,
                         _wifi_signal_bars)
    # Escaped colon in an SSID survives the terse split
    assert _parse_nmcli_terse(r"*:My\:SSID:WPA2:72") == \
        ["*", "My:SSID", "WPA2", "72"]
    assert _parse_nmcli_terse(r":Plain\\Net::55") == \
        ["", r"Plain\Net", "", "55"]
    sample = "\n".join([
        "*:HomeFiber:WPA2:80",
        " :HomeFiber:WPA2:40",     # weaker dup -> merged away
        " :Cafe Open::55",          # open network
        " ::WPA2:90",               # hidden -> skipped
        r" :NETGEAR\:guest:WPA2:30",
    ])
    nets = _parse_wifi_list(sample)
    assert len(nets) == 3                       # hidden skipped, dup merged
    assert nets[0]["ssid"] == "HomeFiber" and nets[0]["active"]  # active first
    assert nets[0]["signal"] == 80              # strongest dup kept
    cafe = [n for n in nets if n["ssid"] == "Cafe Open"][0]
    assert cafe["secured"] is False
    assert any(n["ssid"] == "NETGEAR:guest" for n in nets)
    assert _wifi_signal_bars(80).count("▮") == 4
    assert _wifi_signal_bars(5).count("▮") == 1
    print("  nmcli terse/wifi parsing OK")


def test_trash_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = VaultStorage(Path(tmpdir))
        e = storage.create_entry("Note")
        e.path.write_text("body", encoding="utf-8")
        storage.delete_entry(e)
        trashed = storage.list_trash()
        assert [p.name for p in trashed] == ["Note.md"]
        # Restore returns it to the vault root
        dest = storage.restore_trashed(trashed[0])
        assert dest == Path(tmpdir) / "Note.md" and dest.read_text(encoding="utf-8") == "body"
        assert storage.list_trash() == []
        # Restore collision bumps
        e2 = storage.create_entry("Note2")
        e2.path.write_text("x", encoding="utf-8")
        storage.delete_entry(e2)
        (Path(tmpdir) / "Note2.md").write_text("occupied", encoding="utf-8")
        dest2 = storage.restore_trashed(storage.list_trash()[0])
        assert dest2.name == "Note2 2.md"
        # Empty trash
        for name in ("a", "b"):
            en = storage.create_entry(name)
            en.path.write_text(name, encoding="utf-8")
            storage.delete_entry(en)
        assert storage.empty_trash() == 2
        assert storage.list_trash() == []
    print("  Trash list/restore/empty OK")


def test_foot_font_size():
    with tempfile.TemporaryDirectory() as tmpdir:
        ini = Path(tmpdir) / "foot.ini"
        # Existing size= gets replaced, other params preserved
        ini.write_text("[main]\nfont=Noto Sans Mono:size=13:antialias=true\n", encoding="utf-8")
        assert _set_foot_font_size(16, ini) is True
        assert "font=Noto Sans Mono:size=16:antialias=true" in ini.read_text(encoding="utf-8")
        assert _get_foot_font_size(ini) == 16
        # Font line without size= gets one appended
        ini.write_text("[main]\nfont=Noto Sans Mono\n", encoding="utf-8")
        _set_foot_font_size(14, ini)
        assert _get_foot_font_size(ini) == 14
        # [main] without a font line
        ini.write_text("[main]\npad=2x2\n", encoding="utf-8")
        _set_foot_font_size(12, ini)
        assert _get_foot_font_size(ini) == 12
        assert "pad=2x2" in ini.read_text(encoding="utf-8")
        # Missing file gets created
        ini2 = Path(tmpdir) / "sub" / "foot.ini"
        assert _set_foot_font_size(15, ini2) is True
        assert _get_foot_font_size(ini2) == 15
    print("  foot.ini font-size rewrite OK")


def test_color_schemes():
    schemes = list(COLOR_SCHEMES)
    assert schemes == ["dark", "light", "green", "amber"], schemes
    dark_keys = set(COLOR_SCHEMES["dark"])
    for name, style in COLOR_SCHEMES.items():
        assert set(style) == dark_keys, (
            f"{name} keys differ: {set(style) ^ dark_keys}")
        for key, val in style.items():
            assert isinstance(val, str), f"{name}/{key} not a string"
    print("  Scheme key parity across dark/light/green/amber OK")


if __name__ == "__main__":
    print("Testing data models...")
    test_entry_dataclass()
    test_bib_entry_dataclass()
    print("  \u2713 Data model tests passed\n")

    print("Testing vault storage...")
    test_vault_storage()
    print("  \u2713 Storage tests passed\n")

    print("Testing .bib parsing...")
    test_parse_bib_lightweight()
    test_find_bib_file()
    test_load_bib_entries()
    print("  \u2713 Bib parsing tests passed\n")

    print("Testing fuzzy filter...")
    test_fuzzy_filter()
    test_fuzzy_filter_entries()
    print("  \u2713 Fuzzy filter tests passed\n")

    print("Testing YAML frontmatter parsing...")
    test_parse_yaml_frontmatter()
    print("  \u2713 YAML frontmatter tests passed\n")

    print("Testing reference doc resolution...")
    test_resolve_reference_doc()
    print("  \u2713 Reference doc tests passed\n")

    print("Testing Lua filter generation...")
    test_lua_filter_generation()
    print("  \u2713 Lua filter tests passed\n")

    print("Testing DOCX post-processing...")
    test_postprocess_docx()
    print("  \u2713 DOCX post-processing tests passed\n")

    print("Testing Typst export path...")
    test_author_lastname()
    test_format_export_date()
    test_typst_str()
    test_typst_wrapper()
    test_typst_template_exists()
    test_pdf_engine_routing()
    test_resolve_bib_path()
    test_resolve_csl_path()
    test_strip_frontmatter()
    test_initial_pdf_engine()
    test_bundled_bin()
    test_template_selection()
    test_new_templates_exist()
    test_new_templates_expose_conf()
    test_mla_date_keys_off_style()
    test_default_csl_by_style()
    test_explicit_csl_wins_over_default()
    test_bundled_csls_are_the_right_class()
    test_column_widths_fit_the_page()
    test_column_widths_edge_cases()
    test_autofit_rewrites_table_widths()
    test_cell_text_rows()
    test_bib_blocks_survive_unbalanced_parens()
    test_bib_blocks_paren_delimited_entry()
    test_filter_bib_keeps_what_is_cited()
    test_filter_bib_follows_crossref()
    test_filter_bib_gives_up_rather_than_lose_a_source()
    test_narrow_bib_falls_back_when_unhelpful()
    test_cited_keys_extraction()
    test_rts_rejection_detected()
    test_rts_flags_are_removable()
    test_cite_timeout_is_larger()
    test_rts_is_bound_before_it_is_read()
    test_typst_writer_disables_native_citations()
    test_turabian_heading_levels()
    test_bundled_fonts_present_and_licensed()
    test_templates_name_the_bundled_face_first()
    test_strip_bib_noise_removes_only_noise()
    test_strip_bib_noise_leaves_unterminated_fields_alone()
    test_bib_value_end_forms()
    test_bib_openers_is_independent_of_block_parsing()
    test_journal_template_untouched_by_new_ones()
    test_line_box_pinned_explicitly()
    test_first_line_indent_matches_reference_docx()
    test_journal_typ_has_no_style_branches()
    print("  \u2713 Typst export tests passed\n")

    print("Testing tool detection...")
    test_detect_tools()
    print("  \u2713 Tool detection tests passed\n")

    print("Testing cross-platform shims...")
    test_env_bin()
    test_env_bin_wins_in_detectors()
    test_config_path()
    test_default_vault()
    test_normalise_pasted()
    test_no_console()
    test_detect_clipboard_shape()
    test_config_path_windows()
    test_normalise_pasted_windows()
    test_no_console_windows()
    test_powershell_paste_command()
    test_safe_entry_name()
    test_create_entry_sanitises()
    test_export_writes_utf8()
    test_no_default_encoding_io()
    print("  \u2713 Cross-platform shim tests passed\n")

    print("Testing list continuation...")
    test_list_continuation()
    print("  \u2713 List continuation tests passed\n")

    print("Testing vault path filtering...")
    test_iter_md_paths()
    print("  \u2713 Vault path filtering tests passed\n")

    print("Testing soft delete...")
    test_soft_delete()
    print("  \u2713 Soft delete tests passed\n")

    print("Testing writable-dir repair...")
    test_ensure_writable()
    print("  \u2713 Writable-dir repair tests passed\n")

    print("Testing printer detection...")
    test_detect_printers()
    print("  \u2713 Printer detection tests passed\n")

    print("Testing markdown lexer...")
    test_markdown_lexer()
    print("  \u2713 Markdown lexer tests passed\n")

    print("Testing clipboard paste retry...")
    test_clipboard_paste_no_clobber()
    print("  \u2713 Clipboard paste tests passed\n")

    print("Testing power command fallback...")
    test_run_power()
    print("  ✓ Power command tests passed\n")

    print("Testing heading extraction...")
    test_extract_headings()
    print("  ✓ Heading extraction tests passed\n")

    print("Testing nmcli parsing...")
    test_nmcli_parse()
    print("  ✓ nmcli parse tests passed\n")

    print("Testing trash round-trip...")
    test_trash_roundtrip()
    print("  ✓ Trash tests passed\n")

    print("Testing foot.ini font size...")
    test_foot_font_size()
    print("  \u2713 foot.ini tests passed\n")

    print("Testing color schemes...")
    test_color_schemes()
    print("  \u2713 Color scheme tests passed\n")

    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)
