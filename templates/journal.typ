// Journal export template — the Typst equivalent of refs/{single,double}.docx.
//
// Every measurement below is transcribed from the reference .docx files that
// the pandoc/LibreOffice chain uses, so the two engines produce comparable
// output. Word stores lengths in twips (1440 = 1in) and half-points; the
// conversions are noted inline. Re-measure against a LibreOffice export
// before changing anything here.
//
// Parameters come from the note's YAML frontmatter via _typst_wrapper().

// ── Fonts ────────────────────────────────────────────────────────────────
//
// The reference docs ask for Times New Roman (body) and Aptos Display
// (headings). Typst bundles neither, and a minimal writerdeck has neither
// either — so list real names first and fall back through metric-compatible
// substitutes. Tinos and Liberation Serif are Times-metric; TeX Gyre Termes
// is the usual free Times clone. Aptos has no free equivalent, so headings
// fall back to the serif rather than to something arbitrary.
#let body-fonts = (
  "Times New Roman", "Tinos", "Liberation Serif", "TeX Gyre Termes",
  "Nimbus Roman", "New Computer Modern",
)
#let heading-fonts = ("Aptos Display", "Aptos", ..body-fonts)
#let mono-fonts = ("Consolas", "DejaVu Sans Mono", "Liberation Mono")

// ── Vertical metrics ─────────────────────────────────────────────────────
//
// Typst's leading is the gap *between* line boxes, whereas Word's w:line is
// a multiple of the font's line height — so the two are not interchangeable
// and leading has to be derived from the line box.
//
// The line box depends on text.top-edge / bottom-edge, whose defaults are
// cap-height and baseline — a box of only ~0.66em. conf() overrides them to
// ascender/descender below so the box is a predictable 1.107em for a
// Times-metric face (ascender 0.891em + descender 0.216em), which is what
// these two constants are derived against. Change one, change the other.
//
//     single (w:line=240)  baseline-to-baseline 1.15em  -> leading 0.043em
//     double (w:line=480)  baseline-to-baseline 2.30em  -> leading 1.193em
#let leading-single = 0.043em
#let leading-double = 1.193em

// BodyText carries w:before=180 w:after=180 (9pt each), which Word adds on
// top of line spacing between consecutive paragraphs. Typst's par.spacing
// replaces the inter-line gap rather than adding to it, so fold the leading
// back in to land on the same baseline distance.
#let para-extra = 18pt

#let conf(
  title: "",
  author: "",
  course: "",
  instructor: "",
  date: "",
  style: "",
  spacing: "double",
  lastname: "",
  bib: none,
  csl: none,
  doc,
) = {
  let leading = if spacing == "single" { leading-single } else { leading-double }

  // pgMar: left/right 1440tw = 1in; top 2204tw = 1.531in; bottom 2206tw =
  // 1.532in; header 1440tw = 1in from the page top.
  set page(
    paper: "us-letter",
    margin: (left: 1in, right: 1in, top: 1.531in, bottom: 1.532in),
    // Only MLA gets a running head; the docx path achieves the same thing
    // by stripping header XML for every other style.
    header: if style == "mla" and lastname != "" {
      set text(font: body-fonts, size: 12pt)
      align(right)[#lastname #context counter(page).display()]
    },
    header-ascent: 0.35in,
  )

  // Pin the line box to ascender..descender so leading-single /
  // leading-double above are measured against a known quantity rather
  // than Typst's cap-height default.
  set text(
    font: body-fonts, size: 12pt, lang: "en",
    top-edge: "ascender", bottom-edge: "descender",
  )
  set par(leading: leading, spacing: leading + para-extra, justify: false)
  show raw: set text(font: mono-fonts)

  // Heading sizes and spacing from styles.xml (half-points -> pt, twips ->
  // pt at 20tw/pt). None of them are bold in the reference docs.
  show heading: set text(font: heading-fonts, weight: "regular")
  show heading.where(level: 1): set text(size: 20pt)
  show heading.where(level: 2): set text(size: 16pt)
  show heading.where(level: 3): set text(size: 14pt)
  show heading.where(level: 1): set block(above: 18pt, below: 4pt)
  show heading.where(level: 2): set block(above: 8pt, below: 4pt)
  show heading.where(level: 3): set block(above: 8pt, below: 4pt)

  // ── Front matter ───────────────────────────────────────────────────────
  if style == "chicago" {
    // Turabian cover page. w:before=2400tw = 1.667in above the title;
    // gap_before_author = 4320tw = 3in between title and the info block.
    // The cover is always single-spaced regardless of the body setting.
    set par(leading: leading-single, spacing: leading-single)
    v(1.667in)
    align(center)[#title]
    v(3in)
    align(center)[
      #let info = (author, course, instructor, date).filter(x => x != "")
      #info.join(linebreak())
    ]
    pagebreak(weak: true)
  } else if style == "mla" {
    // MLA header block: name / instructor / course / date, flush left and
    // double-spaced, followed by a centred title.
    let info = (author, instructor, course, date).filter(x => x != "")
    if info.len() > 0 {
      info.join(linebreak())
      linebreak()
    }
    if title != "" {
      align(center)[#title]
    }
  }

  doc

  // ── Bibliography ───────────────────────────────────────────────────────
  //
  // Replaces both --citeproc and the Lua OpenXML run-builder. Hayagriva
  // reads the .bib directly and formats entries itself, so italics inside
  // entries survive natively — that was the bug the Lua inlines_to_openxml
  // walker existed to work around.
  //
  // Hanging indent 720tw = 0.5in, matching the Lua filter, and the heading
  // starts on a new page as the filter's pageBreakBefore did.
  //
  // Citation style follows the note's csl: field, because pandoc's
  // --citeproc reads that same field from the frontmatter — so this is
  // what the docx path has been doing all along. It matters: a note
  // pointing at Chicago full-note expects footnote citations, and
  // falling back to author-date would silently rewrite every citation in
  // the document as an inline parenthetical.
  //
  // Without csl:, use chicago-author-date — citeproc's own default, so
  // the two engines still agree.
  if bib != none {
    pagebreak(weak: true)
    set par(hanging-indent: 0.5in)
    bibliography(
      bib,
      title: if style == "mla" { "Works Cited" } else { "Bibliography" },
      style: if csl != none { csl } else { "chicago-author-date" },
    )
  }
}
