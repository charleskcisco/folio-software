# Bundled citation styles

Default CSL styles, chosen by a note's `style:` frontmatter. A note's own
`csl:` always wins; these are only the fallback, so that `style: chicago`
produces Chicago notes rather than pandoc's built-in author-date default.

| `style:` | File |
|---|---|
| `chicago`, `turabian` | `chicago-fullnote-bibliography.csl` |
| `mla` | `modern-language-association.csl` |

Both files are unmodified copies from the Citation Style Language project
(<https://github.com/citation-style-language/styles>) and are licensed
under Creative Commons Attribution-ShareAlike 3.0
(<http://creativecommons.org/licenses/by-sa/3.0/>), as recorded in each
file's own `<rights>` element. They are redistributed here unchanged.

- Chicago Manual of Style 17th edition (full note) — Turabian 9th is
  built on Chicago 17th, which is why this is the Turabian default too.
- MLA Handbook 9th edition (in-text citations).
