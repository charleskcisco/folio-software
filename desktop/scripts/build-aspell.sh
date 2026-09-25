#!/usr/bin/env bash
# Build a self-contained aspell with the English dictionaries, for
# freeze.sh to bundle into the Mac app.
#
#   desktop/scripts/build-aspell.sh builds/arm64-toolchain/aspell
#   desktop/scripts/build-aspell.sh builds/intel-toolchain/aspell x86_64
#
# The Intel copy is cross-compiled rather than built under Rosetta, unlike
# the Intel freeze: the Command Line Tools no longer carry an x86_64 slice,
# so under `arch -x86_64` the compiler cannot start at all ("unable to load
# libxcrun ... missing compatible architecture"). Its dictionaries are
# still compiled by running the Intel aspell, which Rosetta handles.
#
# From source rather than Homebrew so the result depends on nothing but
# macOS: static libaspell, filters compiled in, no gettext. Homebrew's
# aspell links Homebrew's libraries, which a student's Mac does not have,
# and there is no Intel Homebrew here to take an Intel one from anyway.
#
# The layout written to PREFIX is the one folio.py's _aspell_argv expects:
#   bin/aspell              the program
#   lib/aspell-0.60/        data files and dictionaries (data-dir = dict-dir)
# Windows gets the same layout from MSYS2 in CI instead.
set -euo pipefail

ASPELL_VERSION="0.60.8.1"
ASPELL_SHA256="d6da12b34d42d457fa604e435ad484a74b2effcd120ff40acd6bb3fb2887d21b"
DICT_VERSION="2020.12.07-0"
DICT_SHA256="4c8f734a28a088b88bb6481fcf972d0b2c3dc8da944f7673283ce487eac49fb3"

[ $# -ge 1 ] && [ $# -le 2 ] || { echo "usage: $0 <prefix> [arm64|x86_64]" >&2; exit 1; }
ARCH="${2:-$(uname -m)}"
mkdir -p "$1"
PREFIX="$(cd "$1" && pwd)"

# The deployment target is the oldest macOS the binary will start on. Left
# to default it is the SDK's -- whatever this Mac runs -- and the binary
# refuses to start anywhere older, which is precisely the older machines
# the Intel build exists for. Matched to each architecture's Python, which
# sets the floor for the whole app anyway.
CONFIGURE_HOST=()
case "$ARCH" in
  x86_64)
    export MACOSX_DEPLOYMENT_TARGET=10.15
    export CC="clang -arch x86_64" CXX="clang++ -arch x86_64"
    CONFIGURE_HOST=(--host=x86_64-apple-darwin --build=aarch64-apple-darwin)
    ;;
  arm64)
    export MACOSX_DEPLOYMENT_TARGET=11.0
    ;;
  *) echo "error: unknown architecture '$ARCH'" >&2; exit 1 ;;
esac

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CACHE="${REPO}/builds/src"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$CACHE"

fetch() {  # url sha256
  local file="${CACHE}/$(basename "$1")"
  [ -f "$file" ] || curl -fsSL -o "$file" "$1"
  echo "$2  $file" | shasum -a 256 -c - >/dev/null || {
    echo "error: checksum mismatch for $file" >&2
    exit 1
  }
  printf '%s' "$file"
}

src="$(fetch "https://ftp.gnu.org/gnu/aspell/aspell-${ASPELL_VERSION}.tar.gz" "$ASPELL_SHA256")"
dict="$(fetch "https://ftp.gnu.org/gnu/aspell/dict/en/aspell6-en-${DICT_VERSION}.tar.bz2" "$DICT_SHA256")"

rm -rf "$PREFIX"
tar -xzf "$src" -C "$WORK"
(
  cd "${WORK}/aspell-${ASPELL_VERSION}"
  # recalc_size() names members that do not exist (this->e, this->_size).
  # It is never instantiated, so older compilers let it pass; current
  # clang checks templates eagerly and refuses. 0.60.8.2 fixes it the same
  # way; patched here rather than upgraded to stay on the 0.60.8 line the
  # deck's Debian ships.
  sed -i.orig 's/i != this->e; ++i, ++this->_size/i != end(); ++i, ++size_/' \
    modules/speller/default/vector_hash-t.hpp
  grep -q 'i != end(); ++i, ++size_' modules/speller/default/vector_hash-t.hpp
  ./configure --prefix="$PREFIX" ${CONFIGURE_HOST[@]+"${CONFIGURE_HOST[@]}"} \
    --disable-shared --enable-static \
    --enable-compile-in-filters \
    --disable-nls >/dev/null
  make -j"$(sysctl -n hw.ncpu)" >/dev/null
  make install >/dev/null
)

tar -xjf "$dict" -C "$WORK"
(
  cd "${WORK}/aspell6-en-${DICT_VERSION}"
  ./configure --vars ASPELL="${PREFIX}/bin/aspell" \
    PREZIP="${PREFIX}/bin/prezip-bin" >/dev/null
  make >/dev/null
  make install >/dev/null
)

# Keep only what runs: the program and its data. Headers, the static
# library, docs and the helper scripts are build-time only.
find "${PREFIX}/bin" -mindepth 1 ! -name aspell -delete
rm -rf "${PREFIX}/include" "${PREFIX}/share" "${PREFIX}/lib/"*.a "${PREFIX}/lib/"*.la

"${PREFIX}/bin/aspell" --version
echo "Dictionaries: $("${PREFIX}/bin/aspell" \
  --data-dir="${PREFIX}/lib/aspell-0.60" --dict-dir="${PREFIX}/lib/aspell-0.60" \
  dump dicts | tr '\n' ' ')"
echo "Built ${PREFIX} ($(du -sh "$PREFIX" | cut -f1))"
