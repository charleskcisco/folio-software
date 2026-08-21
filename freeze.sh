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

# FOLIO_PYTHON picks the interpreter, which matters for universal builds:
# PyInstaller freezes for the architecture of the interpreter running it,
# so a universal2 binary needs a universal2 Python and nothing else will
# do. CI installs one from python.org and points this at it.
PY="${FOLIO_PYTHON:-}"
[ -n "$PY" ] && [ ! -x "$PY" ] && { echo "error: FOLIO_PYTHON=$PY is not executable." >&2; exit 1; }
[ -n "$PY" ] || for candidate in .venv/bin/python .venv/Scripts/python.exe python3 python; do
  if [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; then
    PY="$candidate"; break
  fi
done
[ -n "$PY" ] || { echo "error: no python interpreter found." >&2; exit 1; }

resolve_tool() {
  # Follow symlinks: Homebrew's bin entries point into Cellar, and
  # PyInstaller would otherwise embed the link rather than the binary.
  #
  # FOLIO_TOOLS_DIR wins when set. Cross-architecture builds need the
  # tools for the architecture being *built*, not the one building: an
  # Intel binary with an arm64 pandoc inside it is not a build failure,
  # it is a build that fails on the student's machine.
  local found real
  if [ -n "${FOLIO_TOOLS_DIR:-}" ] && [ -x "${FOLIO_TOOLS_DIR}/$1${EXE}" ]; then
    printf '%s' "${FOLIO_TOOLS_DIR}/$1${EXE}"
    return 0
  fi
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

# FOLIO_UNIVERSAL=1 asks for a binary that runs on both Intel and Apple
# Silicon Macs. PyInstaller refuses unless *everything* it collects is
# universal2 -- the interpreter, its extension modules, and the pandoc and
# typst binaries embedded below -- so the caller has to have prepared all
# of them. It fails loudly rather than quietly producing a thin binary.
ARCH_ARGS=""
if [ "${FOLIO_UNIVERSAL:-}" = "1" ]; then
  ARCH_ARGS="--target-arch universal2"
  echo "Building universal2 (Intel + Apple Silicon)"
fi

"$PY" -m PyInstaller --noconfirm --onefile --name folio ${ARCH_ARGS} \
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

# What was built is not necessarily what the host is. An Intel build made
# on an Apple Silicon Mac under Rosetta is still an Intel binary, and
# Tauri looks for the sidecar under the target it was asked to build -- so
# ask the binary what it actually is rather than assuming it matches the
# machine that produced it. Getting this wrong is silent: the wrong-named
# sidecar simply is not found, and the app falls back to something else.
if [ -z "${EXE}" ] && command -v lipo >/dev/null 2>&1; then
  ARCHS="$(lipo -archs "dist/folio${EXE}" 2>/dev/null || true)"
  case "$ARCHS" in
    *arm64*x86_64*|*x86_64*arm64*) FORCED_TRIPLE="universal-apple-darwin" ;;
    *x86_64*)                      FORCED_TRIPLE="x86_64-apple-darwin" ;;
    *arm64*)                       FORCED_TRIPLE="aarch64-apple-darwin" ;;
  esac
fi

if TRIPLE="${FORCED_TRIPLE:-$(detect_triple)}" && [ -n "$TRIPLE" ]; then
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
  # Refresh only the copies this build is actually for.
  #
  # Tauri puts a --target build under target/<triple>/ and a native one
  # directly under target/. Refreshing both unconditionally means a cross
  # build overwrites the native copy: freezing for Intel on an Apple
  # Silicon Mac would leave the arm64 app running an x86_64 sidecar, which
  # works -- under Rosetta, slowly, silently -- until it does not.
  HOST_TRIPLE="$(detect_triple || true)"
  REFRESH_DIRS="desktop/src-tauri/target/${TRIPLE}"
  [ "$TRIPLE" = "$HOST_TRIPLE" ] && REFRESH_DIRS="$REFRESH_DIRS desktop/src-tauri/target"

  for dir in $REFRESH_DIRS; do
    for build in debug release; do
      copy="${dir}/${build}/folio${EXE}"
      if [ -f "$copy" ]; then
        cp "dist/folio${EXE}" "$copy"
        chmod +x "$copy" 2>/dev/null || true
        echo "Refreshed ${copy}"
      fi
    done
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
