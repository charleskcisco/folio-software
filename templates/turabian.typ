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

// De Gruyter Serif first, because it is the one face guaranteed to be
// present: it ships in fonts/ and typst is given --font-path. Everything
// after it is a fallback for a build that somehow lacks the bundle.
//
// It is not Times-metric -- Noto SemiCondensed underneath, so narrower --
// which moves line breaks and page counts. Vertical spacing does not
// move, because conf() pins the line box to explicit lengths rather than
// to whatever the font reports.
// Two backstops, not six. typst warns for every family it cannot find,
// even when an earlier one resolved, and those warnings land in the
// export log a person reads when something has gone wrong. Times covers
// macOS and Windows, Liberation covers Linux, for the case where the
// bundle is missing entirely.
#let body-fonts = (
  "De Gruyter Serif", "Times New Roman", "Liberation Serif",
)
#let math-fonts = ("De Gruyter Sans Math", "New Computer Modern Math")
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
  // Operators the serif does not carry.
  show math.equation: set text(font: math-fonts)

  // Turabian distinguishes its five heading levels by placement and
  // weight, never by size -- all of them sit at body size:
  //
  //   1  centred, bold
  //   2  centred, regular
  //   3  flush left, bold
  //   4  flush left, regular
  //   5  run in at the head of its own paragraph, bold, ending with a
  //      period, with the text continuing on the same line
  //
  // The manual permits italic wherever bold is used at 1, 3 and 5; bold
  // is chosen consistently here so the three read as one system.
  //
  // Capitalisation is the writer's business, not the template's: levels
  // 1 to 3 take headline style and 4 to 5 sentence style, and nothing
  // here changes the case of what was typed.
  show heading: set text(font: body-fonts, size: 12pt, weight: "regular")
  show heading: set block(above: leading-double, below: leading-double)
  show heading.where(level: 1): it => align(center)[#strong(it.body)]
  show heading.where(level: 2): it => align(center)[#it.body]
  // set, not a content rule: returning strong(it.body) yields inline
  // content, which drops the heading's block and runs it into the
  // paragraph beneath. That is what level 5 wants and what level 3 must
  // not do.
  show heading.where(level: 3): set text(weight: "bold")

  // Level 5 is a paragraph opening rather than a line of its own, so it
  // cannot use the block spacing above: the heading and the text that
  // follows it are one paragraph. Typst has no way to pull the next
  // block up, so the run-in is emitted as an inline box with no space
  // after it and the following text flows on.
  show heading.where(level: 5): it => box(strong[#it.body.])

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
