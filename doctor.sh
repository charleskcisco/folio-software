#!/usr/bin/env bash
# doctor.sh — report which of Folio's external dependencies are present,
# and optionally install just the ones that are not.
#
# Folio shells out to a lot of things. Most failures are quiet: an absent
# tool disables one feature and says nothing until someone reaches for it,
# often in front of a class. This lists them in one place.
#
#   ./doctor.sh         report only
#   ./doctor.sh --fix   install what is missing, and nothing else
#
# --fix exists because app-setup.sh is the wrong tool for a deck that is
# only missing a couple of things: it reinstalls everything including
# LibreOffice, which on a Pi Zero is an hour and a reboot. This installs
# the gaps and does not reboot.
#
# Migration is the usual reason for gaps. setup.sh and device-setup.sh do
# not install system tools, so a deck moved by cloning and running those
# two keeps whatever it already had and gains nothing new.

cd "$(dirname "${BASH_SOURCE[0]}")"

FIX=0
[ "${1:-}" = "--fix" ] && FIX=1

pkgs=()          # apt packages to install
need_typst=0     # not in apt; install-typst.sh handles it
need_filebrowser=0
ok=0; missing=0

check() {
  local cmd="$1" what="$2" pkg="$3"
  if command -v "$cmd" >/dev/null 2>&1; then
    printf '   ok   %-14s %s\n' "$cmd" "$what"
    ok=$((ok + 1))
    return
  fi
  printf '  MISS  %-14s %s\n' "$cmd" "$what"
  missing=$((missing + 1))
  case "$pkg" in
    typst)       need_typst=1 ;;
    filebrowser) need_filebrowser=1 ;;
    "")          ;;
    *)           pkgs+=($pkg) ;;
  esac
}

echo
echo "Export"
check pandoc      "every export path runs through it"   pandoc
check typst       "PDF engine (falls back to LibreOffice)" typst
check soffice     "docx -> PDF, and .docx export"       libreoffice

echo
echo "Writing"
check aspell      "spell check"                         "aspell aspell-en"
check wl-copy     "clipboard (Wayland)"                 wl-clipboard
check xclip       "clipboard (X11 fallback)"            xclip

echo
echo "Device"
check lp          "printing from the exports screen"    cups-client
check nmcli       "Wi-Fi picker in Options"             network-manager
check filebrowser "web share of the vault (s on exports)" filebrowser
check grim        "F12 screenshot"                      grim

echo
echo "Session"
check cage        "kiosk compositor"                    cage
check foot        "terminal"                            foot
check git         "self-update (^u)"                    git

echo
echo "  $ok present, $missing missing"
echo

[ "$missing" -eq 0 ] && exit 0

if [ "$FIX" -eq 0 ]; then
  echo "  Install just these with:  ./doctor.sh --fix"
  echo "  (app-setup.sh also works, but reinstalls everything and reboots.)"
  echo
  exit 0
fi

if [ "${#pkgs[@]}" -gt 0 ]; then
  echo "  Installing: ${pkgs[*]}"
  sudo apt install -y "${pkgs[@]}" || {
    echo "  apt failed. Try 'sudo apt update' first." >&2
    exit 1
  }
fi

if [ "$need_typst" -eq 1 ]; then
  echo "  Installing typst..."
  ./install-typst.sh || echo "  typst failed; export falls back to LibreOffice." >&2
fi

if [ "$need_filebrowser" -eq 1 ]; then
  # Same installer app-setup.sh uses: a single Go binary, and the official
  # script picks the right build for this CPU.
  echo "  Installing File Browser..."
  curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash \
    || echo "  File Browser failed; the vault web share stays unavailable." >&2
fi

echo
echo "  Done. No reboot needed."
echo
