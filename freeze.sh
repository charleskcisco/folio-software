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

# Windows differs in three ways that all have to be handled here, because
# this script is what CI runs on every platform: PyInstaller separates
# --add-data source from destination with ';' rather than ':', the frozen
# output carries a .exe suffix, and a venv puts python under Scripts/.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) EXE=".exe"; SEP=";" ;;
  *)                    EXE="";     SEP=":" ;;
esac

PY=""
for candidate in .venv/bin/python .venv/Scripts/python.exe python3 python; do
  if [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; then
    PY="$candidate"; break
  fi
done
[ -n "$PY" ] || { echo "error: no python interpreter found." >&2; exit 1; }

resolve_tool() {
  # Follow symlinks: Homebrew's bin entries point into Cellar, and
  # PyInstaller would otherwise embed the link rather than the binary.
  local found real
  found="$(command -v "$1$EXE" 2>/dev/null)" \
    || found="$(command -v "$1" 2>/dev/null)" \
    || {
      echo "error: $1 not found on PATH." >&2
      echo "       Folio cannot export without it; install it and re-run." >&2
      exit 1
    }
  real="$("$PY" -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$found")"

  # Git Bash resolves `command -v pandoc` to a path with no .exe, because
  # it appends the suffix implicitly when executing. PyInstaller does not:
  # it takes the string literally and fails with "Unable to find
  # C:\...\pandoc when adding binary and data files".
  [ ! -f "$real" ] && [ -f "${real}${EXE}" ] && real="${real}${EXE}"

  [ -f "$real" ] || {
    echo "error: resolved $1 to '$real', which is not a file." >&2
    exit 1
  }
  printf '%s' "$real"
}

PANDOC="$(resolve_tool pandoc)"
TYPST="$(resolve_tool typst)"
echo "Bundling pandoc: $PANDOC"
echo "Bundling typst:  $TYPST"

"$PY" -m PyInstaller --noconfirm --onefile --name folio \
  --add-data "templates${SEP}templates" \
  --add-data "fonts${SEP}fonts" \
  --add-data "csl${SEP}csl" \
  --add-data "refs${SEP}refs" \
  --add-binary "${PANDOC}${SEP}bin" \
  --add-binary "${TYPST}${SEP}bin" \
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

detect_triple() {
  local candidate t
  for candidate in rustc "$HOME/.cargo/bin/rustc" \
                   /opt/homebrew/opt/rustup/bin/rustc; do
    t="$(command -v "$candidate" >/dev/null 2>&1 && "$candidate" -vV 2>/dev/null \
         | sed -n 's/^host: //p')" || t=""
    [ -n "$t" ] && { printf '%s' "$t"; return 0; }
  done
  return 1
}

if TRIPLE="$(detect_triple)" && [ -n "$TRIPLE" ]; then
  mkdir -p "$SIDECAR_DIR"
  cp "dist/folio${EXE}" "${SIDECAR_DIR}/folio-${TRIPLE}${EXE}"
  chmod +x "${SIDECAR_DIR}/folio-${TRIPLE}${EXE}" 2>/dev/null || true
  echo "Staged sidecar ${SIDECAR_DIR}/folio-${TRIPLE}${EXE}"

  # Refresh the copies Tauri has already made. It only re-copies an
  # externalBin when it rebuilds, and editing Python does not trigger a
  # Rust rebuild -- so without this a freeze succeeds, reports success,
  # and the desktop app carries on running the previous binary. That has
  # burned an afternoon twice: the fix looks like it did not work, and
  # the thing being tested is not the thing that was built.
  #
  # Only refresh what already exists. A missing copy means Tauri has not
  # built yet, and it will take the staged sidecar when it does.
  for build in debug release; do
    copy="desktop/src-tauri/target/${build}/folio${EXE}"
    if [ -f "$copy" ]; then
      cp "dist/folio${EXE}" "$copy"
      chmod +x "$copy" 2>/dev/null || true
      echo "Refreshed ${copy}"
    fi
  done
else
  # Never leave a stale sidecar behind. The wrapper resolves Folio from
  # beside its own executable, so an old copy here is not inert -- Tauri
  # copies it into the build and the app runs it, silently, in place of
  # the build that just happened. Warning and continuing meant a freeze
  # could appear to succeed while changing nothing that ran.
  rm -f "${SIDECAR_DIR}"/folio-*
  echo "error: cannot determine the Rust host triple (rustc not found)." >&2
  echo "       Removed any stale sidecar rather than leave the wrapper" >&2
  echo "       running an older Folio. Install rustup and re-run." >&2
  exit 1
fi

echo
echo "Built dist/folio${EXE} ($(du -h "dist/folio${EXE}" | cut -f1))"
echo "Verify resources with: ./freeze.sh --check"
