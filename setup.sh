#!/usr/bin/env bash
# Set up dependencies for Journal.
#
# Creates a virtual environment and installs prompt_toolkit + pygments.
# If pip is not available, prompt_toolkit can also be vendored manually.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Setting up Journal..."

# Create venv if it doesn't exist
if [ ! -d "${SCRIPT_DIR}/.venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv "${SCRIPT_DIR}/.venv"
fi

echo "  Installing dependencies..."
"${SCRIPT_DIR}/.venv/bin/pip" install --quiet prompt_toolkit pygments

# typst is a system binary, not a Python package, so it is app-setup.sh's
# job -- but run.sh's self-update loop only calls this script. Flag it here
# so a device that updated into the Typst PDF engine learns why it is still
# exporting via LibreOffice. Non-fatal: the fallback is automatic.
if ! command -v typst >/dev/null 2>&1; then
    echo ""
    echo "  Note: typst not found — PDF export will use LibreOffice."
    echo "        Run ./install-typst.sh to enable the faster engine."
fi

echo "Done. Run with: ./run.sh"
