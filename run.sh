#!/usr/bin/env bash
# Folio launcher — uses venv with prompt_toolkit.
#
# Usage:
#   ./run.sh                    # normal run
#   FOLIO_VAULT=~/notes ./run.sh     # custom vault directory
#
# Self-update: the app exits with code 42 when the user chooses to update
# (^u). This launcher loop then pulls the latest code, reinstalls
# dependencies, and relaunches — so the user never drops to a shell. Any
# other exit (^Q quit, ^S shutdown, crash) just ends the loop normally.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/.venv/bin/python3" ]; then
    PY="${SCRIPT_DIR}/.venv/bin/python3"
else
    PY="python3"   # fall back to system python (prompt_toolkit must be installed)
fi

while true; do
    "$PY" "${SCRIPT_DIR}/folio.py" "$@"
    code=$?

    if [ "$code" -eq 43 ]; then
        continue              # plain relaunch (e.g. vault changed in Options)
    fi

    if [ "$code" -ne 42 ]; then
        exit "$code"          # normal quit / shutdown / error
    fi

    # Update requested.
    echo "Updating Folio…"
    if git -C "$SCRIPT_DIR" pull --ff-only; then
        "${SCRIPT_DIR}/setup.sh" || echo "Dependency update failed; continuing with current deps."
    else
        echo "Update failed (git pull). Continuing with the current version."
        sleep 2
    fi
    # exec a fresh launcher rather than looping.
    #
    # git pull has just rewritten this file underneath a running bash,
    # which reads a script incrementally by byte offset -- so continuing
    # the loop can resume at an offset that is now the middle of a
    # different line. exec replaces the process and re-reads from the
    # top, which is the only way to be sure the launcher that runs next
    # is the launcher that is now on disk.
    exec "${SCRIPT_DIR}/run.sh" "$@"
done
