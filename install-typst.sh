#!/usr/bin/env bash
# install-typst.sh — install typst, the PDF export engine.
#
# typst is not in Raspberry Pi OS / Debian bookworm's apt repos, so this
# pulls the static musl build from GitHub releases — the same approach
# app-setup.sh uses for File Browser.
#
# Split out of app-setup.sh so an existing device can gain typst without
# a full apt upgrade and reboot: just run ./install-typst.sh.
#
# Safe to re-run; exits early if typst is already installed.

set -e

if command -v typst >/dev/null 2>&1; then
    echo "typst already installed: $(typst --version)"
    exit 0
fi

case "$(uname -m)" in
    aarch64|arm64)  TARGET="aarch64-unknown-linux-musl" ;;
    armv7l|armv6l)  TARGET="armv7-unknown-linux-musleabi" ;;
    x86_64|amd64)   TARGET="x86_64-unknown-linux-musl" ;;
    *)
        echo "Unsupported architecture: $(uname -m)" >&2
        echo "Install typst manually, or leave Options > PDF engine on" >&2
        echo "libreoffice — export keeps working either way." >&2
        exit 1
        ;;
esac

URL="https://github.com/typst/typst/releases/latest/download/typst-${TARGET}.tar.xz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading typst (${TARGET})..."
curl -fsSL "$URL" -o "${TMP}/typst.tar.xz"
tar -xJf "${TMP}/typst.tar.xz" -C "$TMP"

sudo install -m 0755 "${TMP}/typst-${TARGET}/typst" /usr/local/bin/typst
echo "Installed: $(typst --version)"
