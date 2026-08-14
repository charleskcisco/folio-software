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
  doc,
) = {
  let leading = if spacing == "single" { leading-single } else { leading-double }

  // pgMar in refs/*.docx: 1440tw = 1in on every side.
  //
  // top/bottom used to read 2204/2206tw (1.53in) because LibreOffice, which
  // authored those files, folds the header allowance into the body margin.
  // Journal strips the header for every style but MLA, so that allowance
  // bought nothing and just made the margins look wrong. The reference docs
  // now say 1440 as well — change one, change the other, or the two engines
  // stop agreeing.
  set page(
    paper: "us-letter",
    margin: (left: 1in, right: 1in, top: 1in, bottom: 1in),
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

  // ── Bibliography ───────────────────────────────────────────────────────
  //
  // Citations and the reference list are rendered by pandoc's citeproc,
  // not by Typst, and arrive already formatted. pandoc emits the list as a
  // block labelled <refs>; this styles it to match what the Lua filter did
  // to the docx — page break before it, a heading, 0.5in hanging indent.
  //
  // Typst's own bibliography() cannot do this job under a note style: it
  // renders each citation as a *new* footnote, and notes in this vault put
  // citations inside footnotes already (^[Again, @key]). Footnotes do not
  // nest, so the citation silently vanished and left an empty note behind.
  // citeproc knows it is already inside a note and inlines the text.
  //
  // Declared before doc, since a show rule only affects what follows it.
  show <refs>: it => {
    pagebreak(weak: true)
    heading(level: 1, if style == "mla" { "Works Cited" } else { "Bibliography" })
    set par(hanging-indent: 0.5in)
    it
  }

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
}
