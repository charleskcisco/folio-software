// Turabian export template — derived from A Manual for Writers (9th ed.),
// not from refs/*.docx.
//
// journal.typ already produces a Turabian-shaped document, because the
// reference .docx it was transcribed from is Charles's Turabian setup. The
// difference here is that the measurements come from the manual rather
// than from one person's Word styles, and that the things the manual is
// specific about -- an unnumbered title page, a half-inch paragraph
// indent, single-spaced block quotations -- are actually implemented.
//
// Nothing here affects journal.typ, the docx chain, or any note that does
// not ask for it: this file is only read when a note sets
// template: turabian.
//
// Parameters come from the note's YAML frontmatter via _typst_wrapper().

#let body-fonts = (
  "Times New Roman", "Tinos", "Liberation Serif", "TeX Gyre Termes",
  "Nimbus Roman", "New Computer Modern",
)
#let mono-fonts = ("Consolas", "DejaVu Sans Mono", "Liberation Mono")

// See mla.typ for the derivation and for why the line box is pinned with
// explicit lengths rather than the "ascender"/"descender" keywords.
#let box-top = 0.891em
#let box-bottom = -0.216em
#let leading-double = 1.193em
#let leading-single = 0.043em

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
  set text(
    font: body-fonts, size: 12pt, lang: "en",
    top-edge: box-top, bottom-edge: box-bottom,
  )

  // ── Title page ─────────────────────────────────────────────────────────
  //
  // Turabian puts the title about a third of the way down, with the
  // author, course, instructor and date lower on the same page. The title
  // page carries no page number and is not counted in the numbering the
  // reader sees, so it is emitted as its own page before numbering starts.
  //
  // Single-spaced regardless of the body setting: this is a block of
  // labels, not prose.
  set page(paper: "us-letter", margin: 1in, numbering: none, header: none)
  {
    set par(leading: leading-single, spacing: leading-single,
            first-line-indent: 0pt)
    // The manual asks for the title about a third of the way down the
    // page. 1in margin + 2.667in puts it at 3.667in on us-letter. This is
    // the one place turabian.typ deliberately departs from journal.typ,
    // whose 1.667in comes from the reference .docx.
    v(2.667in)
    align(center)[#title]
    v(2.5in)
    align(center)[
      #let info = (author, course, instructor, date).filter(x => x != "")
      #info.join(linebreak())
    ]
  }
  // Zero the counter *before* the break. A header reads the page counter
  // as the page is laid out, so an update placed after the break has
  // already been overtaken and the first body page comes out numbered 2.
  counter(page).update(0)
  pagebreak(weak: true)

  // ── Body pages ─────────────────────────────────────────────────────────
  //
  // A set rule on page takes effect from the next page, which is exactly
  // the boundary the pagebreak above just created.
  //
  // page.numbering is deliberately left unset: setting it makes Typst
  // generate its own centred footer, which lands a *second* page number
  // at the bottom of every page alongside the one in the header. The
  // counter is displayed explicitly instead, with its own pattern.
  set page(
    header-ascent: 0.35in,
    header: context {
      set text(font: body-fonts, size: 12pt)
      align(right)[#counter(page).display("1")]
    },
  )

  // Double-spaced body, no extra gap between paragraphs, half-inch indent
  // on every paragraph including the first after a heading.
  set par(
    leading: leading-double,
    spacing: leading-double,
    first-line-indent: (amount: 0.5in, all: true),
    justify: false,
  )

  show raw: set text(font: mono-fonts)

  // Turabian headings are distinguished by placement and weight rather
  // than by size: level 1 centred and bold, level 2 centred and regular,
  // level 3 flush left. All at body size.
  show heading: set text(font: body-fonts, size: 12pt, weight: "regular")
  show heading: set block(above: leading-double, below: leading-double)
  show heading.where(level: 1): it => align(center)[#strong(it.body)]
  show heading.where(level: 2): it => align(center)[#it.body]

  // Block quotations are indented and set single-spaced, which is one of
  // the few places Turabian departs from double spacing throughout.
  show quote.where(block: true): set pad(left: 0.5in)
  show quote.where(block: true): set block(
    above: leading-double, below: leading-double)
  show quote.where(block: true): set par(
    leading: leading-single, spacing: leading-single, first-line-indent: 0pt)

  // ── Bibliography ───────────────────────────────────────────────────────
  //
  // Only reachable when a note sets bibliography:, which the student build
  // never does. Entries are single-spaced with a blank line between them
  // and a half-inch hanging indent.
  show <refs>: it => {
    pagebreak(weak: true)
    align(center)[#strong[Bibliography]]
    set par(leading: leading-single, spacing: leading-double,
            hanging-indent: 0.5in, first-line-indent: 0pt)
    it
  }

  doc
}
