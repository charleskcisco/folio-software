#!/usr/bin/env bash
# Freeze Folio into a folder the desktop wrapper ships and spawns.
#
# --onedir, not --onefile. A onefile build is a self-extracting archive:
# every launch unpacked ~190MB into a fresh temp directory before Folio
# ran a line, which was the 3-5 seconds of blank window at startup -- and
# a launch that was killed rather than quit left that directory behind,
# so a student's disk filled by 190MB a time. The folder build starts in
# a tenth of a second and leaves nothing behind.
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
# do.
#
# On a Mac, a standalone toolchain under builds/ is preferred when one
# exists for the architecture this script is running as (so under
# `arch -x86_64` it picks the Intel one). Homebrew's and python.org's
# Pythons are framework builds, and a folder frozen from one carries
# Python.framework with it: symlinks, dozens of extra binaries to sign,
# and a Python version that drifts from the one being shipped. The
# standalone build freezes to four binaries and a plain folder.
# desktop/README.md says how to rebuild the toolchains.
TOOLCHAIN=""
if [ "$(uname -s)" = "Darwin" ]; then
  case "$(uname -m)" in
    arm64)  TOOLCHAIN="builds/arm64-toolchain" ;;
    x86_64) TOOLCHAIN="builds/intel-toolchain" ;;
  esac
  [ -x "${TOOLCHAIN}/python/bin/python3.12" ] || TOOLCHAIN=""
fi
if [ -n "$TOOLCHAIN" ]; then
  [ -z "${FOLIO_PYTHON:-}" ] && FOLIO_PYTHON="$PWD/${TOOLCHAIN}/python/bin/python3.12"
  [ -z "${FOLIO_TOOLS_DIR:-}" ] && [ -d "${TOOLCHAIN}/bin" ] && FOLIO_TOOLS_DIR="$PWD/${TOOLCHAIN}/bin"
fi

PY="${FOLIO_PYTHON:-}"
[ -n "$PY" ] && [ ! -x "$PY" ] && { echo "error: FOLIO_PYTHON=$PY is not executable." >&2; exit 1; }
[ -n "$PY" ] && echo "Freezing with $PY"
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

# aspell is bundled as a whole directory -- the program plus its data and
# dictionaries -- because it is useless without them and looks them up in
# paths compiled into the binary. folio.py's _aspell_argv points it at the
# bundled copy. Without this a student's spell check reports "aspell not
# found", which on the deck is an apt install and on their laptop is a dead
# end.
#
# FOLIO_ASPELL_DIR wins; otherwise the toolchain's aspell/, which
# desktop/scripts/build-aspell.sh produces. CI's Windows job assembles one
# from MSYS2.
ASPELL_DIR="${FOLIO_ASPELL_DIR:-}"
[ -z "$ASPELL_DIR" ] && [ -n "$TOOLCHAIN" ] && ASPELL_DIR="$PWD/${TOOLCHAIN}/aspell"
ASPELL_BIN="${ASPELL_DIR}/bin/aspell${EXE}"
ASPELL_DATA="${ASPELL_DIR}/lib/aspell-0.60"
if [ -z "$ASPELL_DIR" ] || [ ! -x "$ASPELL_BIN" ]; then
  echo "error: no aspell to bundle (looked for '${ASPELL_BIN}')." >&2
  echo "       Build one with desktop/scripts/build-aspell.sh <toolchain>/aspell," >&2
  echo "       or point FOLIO_ASPELL_DIR at one." >&2
  exit 1
fi
# Prove it works before shipping it: a copy that cannot find its
# dictionaries fails silently in Folio -- every word comes back correct.
if ! printf 'recieve\n' | "$ASPELL_BIN" --data-dir="$ASPELL_DATA" --dict-dir="$ASPELL_DATA" \
     list --lang=en_US 2>&1 | tr -d '\r' | grep -qx recieve; then
  echo "error: ${ASPELL_BIN} does not flag 'recieve' with en_US from" >&2
  echo "       ${ASPELL_DATA}; its dictionaries are missing or broken." >&2
  exit 1
fi
echo "Bundling aspell: $ASPELL_DIR"

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

# A previous build may have left dist/folio as a *file* -- the onefile
# layout -- and PyInstaller will not replace a file with a directory.
#
# The staged copy goes too, before anything can fail. A freeze that stops
# halfway must not leave the last build staged: build.rs would accept it,
# and the app would ship it in place of the build that just failed.
rm -rf "dist/folio" "dist/folio${EXE}" desktop/src-tauri/folio-dist desktop/src-tauri/binaries

"$PY" -m PyInstaller --noconfirm --onedir --name folio ${ARCH_ARGS} \
  --add-data "templates${SEP}templates" \
  --add-data "fonts${SEP}fonts" \
  --add-data "csl${SEP}csl" \
  --add-data "refs${SEP}refs" \
  --add-data "${ASPELL_DIR}${SEP}aspell" \
  --add-binary "${PANDOC}${SEP}bin" \
  --add-binary "${TYPST}${SEP}bin" \
  folio.py

BUILT="dist/folio/folio${EXE}"
[ -f "$BUILT" ] || { echo "error: PyInstaller finished but $BUILT is missing." >&2; exit 1; }

# A framework Python leaves Python.framework, symlinks and all, inside the
# folder. sign-folio.mjs signs loose binaries, not nested bundles, so that
# layout builds, runs here, and then fails notarization -- stop now rather
# than an hour from now.
if [ "$(uname -s)" = "Darwin" ] && [ -n "$(find dist/folio -type l -print -quit)" ]; then
  echo "error: dist/folio contains symlinks, so $PY is a framework build" >&2
  echo "       (Homebrew and python.org Pythons both are). Freeze with a" >&2
  echo "       python-build-standalone interpreter -- see desktop/README.md." >&2
  exit 1
fi

# Nothing bundled may need a newer macOS than the students have. A binary
# records the oldest macOS it will start on, and a Homebrew one records
# the version of the Mac that built it: 0.1.0 and 0.1.1 shipped Homebrew's
# pandoc, which needed macOS 26, so on Sequoia the app opened, edited, and
# failed every single export. macOS gives no hint why.
MACOS_FLOOR="${FOLIO_MACOS_FLOOR:-15.0}"
if [ "$(uname -s)" = "Darwin" ]; then
  too_new=""
  while IFS= read -r f; do
    minos="$(otool -l "$f" | awk '/LC_BUILD_VERSION/{b=1} b&&/minos/{print $2; exit}')"
    [ -n "$minos" ] || continue
    if "$PY" -c "import sys; a,b=(tuple(map(int,v.split('.'))) for v in sys.argv[1:]); sys.exit(a<=b)" \
         "$minos" "$MACOS_FLOOR"; then
      too_new="${too_new}       ${f#dist/folio/} needs macOS ${minos}"$'\n'
    fi
  done < <(find dist/folio -type f -perm -u+x -o -type f -name '*.dylib')
  if [ -n "$too_new" ]; then
    echo "error: these need a newer macOS than ${MACOS_FLOOR} (FOLIO_MACOS_FLOOR):" >&2
    printf '%s' "$too_new" >&2
    echo "       Homebrew builds for the Mac it runs on; use the projects' own" >&2
    echo "       release binaries in the toolchain's bin/ -- see desktop/README.md." >&2
    exit 1
  fi
fi

# Stage the folder for the desktop wrapper.
#
# Tauri ships it as a bundle resource (tauri.conf.json maps folio-dist/ to
# folio/), which lands in Contents/Resources/folio on macOS and beside the
# executable on Windows. It is staged under src-tauri rather than pointed
# at dist/ directly because a resource path that climbs out of src-tauri
# is rewritten -- ../../dist/folio became Contents/Resources/_up_/_up_/,
# which the lookup missed, and the app silently fell back to an absolute
# path into this source tree: it ran on the machine that built it and on
# no other.
#
# TRIPLE records what the folder holds. build.rs refuses to build an app
# for one architecture around a Folio for another, which is otherwise a
# silent mistake: an Intel Folio inside an Apple Silicon app runs, under
# Rosetta, slowly, and nothing says why.
STAGE="desktop/src-tauri/folio-dist"

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
# on an Apple Silicon Mac under Rosetta is still an Intel binary, so ask
# the binary what it is rather than assuming it matches the machine that
# produced it.
if [ -z "${EXE}" ] && command -v lipo >/dev/null 2>&1; then
  ARCHS="$(lipo -archs "$BUILT" 2>/dev/null || true)"
  case "$ARCHS" in
    *arm64*x86_64*|*x86_64*arm64*) FORCED_TRIPLE="universal-apple-darwin" ;;
    *x86_64*)                      FORCED_TRIPLE="x86_64-apple-darwin" ;;
    *arm64*)                       FORCED_TRIPLE="aarch64-apple-darwin" ;;
  esac
fi

if ! TRIPLE="${FORCED_TRIPLE:-$(detect_triple)}" || [ -z "$TRIPLE" ]; then
  echo "error: cannot determine the Rust target triple (rustc not found)." >&2
  echo "       Nothing staged; install rustup and re-run." >&2
  exit 1
fi

cp -R "dist/folio" "$STAGE"
printf '%s\n' "$TRIPLE" > "${STAGE}/TRIPLE"
echo "Staged ${STAGE} for ${TRIPLE}"

# Refresh the copies Tauri has already made. It copies resources when the
# Rust side builds, and editing Python does not trigger a Rust build -- so
# without this a freeze succeeds and the desktop app carries on running
# the previous Folio. The fix looks like it did not work, and the thing
# being tested is not the thing that was built.
#
# Only refresh what already exists (a missing copy means Tauri has not
# built yet, and it will take the staged folder when it does), and only
# the copies this build is for: a --target build lives under
# target/<triple>/, a native one directly under target/, and refreshing
# both would let an Intel freeze overwrite the Apple Silicon dev copy.
HOST_TRIPLE="$(detect_triple || true)"
REFRESH_DIRS="desktop/src-tauri/target/${TRIPLE}"
[ "$TRIPLE" = "$HOST_TRIPLE" ] && REFRESH_DIRS="$REFRESH_DIRS desktop/src-tauri/target"

for dir in $REFRESH_DIRS; do
  for build in debug release; do
    [ -d "${dir}/${build}" ] || continue
    copy="${dir}/${build}/folio"
    # The onefile layout put a single executable here, and _up_ is where
    # the old resources route mangled its copy to. Both are dead weight
    # that Tauri would trip over when copying the folder in.
    rm -rf "${dir}/${build}/_up_" "${dir}/${build}/folio.exe"
    if [ -e "$copy" ]; then
      rm -rf "$copy"
      cp -R "$STAGE" "$copy"
      echo "Refreshed ${copy}"
    fi
  done
done

echo
echo "Built dist/folio/ ($(du -sh "dist/folio" | cut -f1))"
