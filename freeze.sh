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
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

"$PY" -m PyInstaller --noconfirm --onefile --name folio \
  --add-data "templates:templates" \
  --add-data "fonts:fonts" \
  --add-data "csl:csl" \
  --add-data "refs:refs" \
  folio.py

echo
echo "Built dist/folio ($(du -h dist/folio | cut -f1))"
echo "Verify resources with: ./freeze.sh --check"
