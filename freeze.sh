#!/usr/bin/env bash
# Freeze Folio into a single executable for the desktop wrapper to spawn.
#
# The --add-data list is the whole point of this script. Every one of
# these directories is read at export time rather than imported, so
# PyInstaller cannot discover them by following imports -- and the
# failure modes are not equal:
#
#   templates/  missing -> export fails, loudly, with "Missing export
#               template", the first time a student tries to export
#   fonts/      missing -> export SUCCEEDS and silently uses whatever
#               face typst picks, changing the typography of every
#               document with no warning anywhere
#   csl/        missing -> citation style falls back to pandoc's default
#   refs/       missing -> the docx path cannot find a reference document
#
# fonts/ is the one to watch. Check a frozen build's *output* against a
# source-checkout render, not merely that it produces a PDF.
# pandoc and typst are bundled too. Every export path runs through
# pandoc -- the typst engine included, since the markdown is converted to
# typst by pandoc first -- so an unbundled build tells a student "Pandoc
# not found. Install pandoc for export." on a machine where they have no
# way to fix that. They are resolved from PATH rather than committed:
# together they are ~300MB, which does not belong in git.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

resolve_tool() {
  # Follow symlinks: Homebrew's bin entries point into Cellar, and
  # PyInstaller would otherwise embed the link rather than the binary.
  local found
  found="$(command -v "$1" 2>/dev/null)" || {
    echo "error: $1 not found on PATH." >&2
    echo "       Folio cannot export without it; install it and re-run." >&2
    exit 1
  }
  "$PY" -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$found"
}

PANDOC="$(resolve_tool pandoc)"
TYPST="$(resolve_tool typst)"
echo "Bundling pandoc: $PANDOC"
echo "Bundling typst:  $TYPST"

"$PY" -m PyInstaller --noconfirm --onefile --name folio \
  --add-data "templates:templates" \
  --add-data "fonts:fonts" \
  --add-data "csl:csl" \
  --add-data "refs:refs" \
  --add-binary "${PANDOC}:bin" \
  --add-binary "${TYPST}:bin" \
  folio.py

# Stage the sidecar for the desktop wrapper.
#
# Tauri resolves an externalBin by target triple and drops it beside the
# app executable, which is the only layout that survives being moved to
# another machine. The previous bundle.resources route mangled
# ../../dist/folio into Contents/Resources/_up_/_up_/dist/folio, which the
# lookup missed -- so the app silently fell back to an absolute path into
# this source tree and ran correctly here and nowhere else.
SIDECAR_DIR="desktop/src-tauri/binaries"
if TRIPLE="$(rustc -vV 2>/dev/null | sed -n 's/^host: //p')" && [ -n "$TRIPLE" ]; then
  mkdir -p "$SIDECAR_DIR"
  cp dist/folio "${SIDECAR_DIR}/folio-${TRIPLE}"
  chmod +x "${SIDECAR_DIR}/folio-${TRIPLE}"
  echo "Staged sidecar ${SIDECAR_DIR}/folio-${TRIPLE}"
else
  echo "warning: rustc not on PATH; sidecar not staged for the wrapper." >&2
fi

echo
echo "Built dist/folio ($(du -h dist/folio | cut -f1))"
echo "Verify resources with: ./freeze.sh --check"
