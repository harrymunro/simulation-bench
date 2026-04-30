#!/usr/bin/env bash
#
# Reproducibility verification driver for AC 11.
#
# Builds a brand-new virtualenv at ./.repro-venv from the *documented*
# requirements (requirements.txt + pyproject.toml), executes
# `python -m mine_sim run-all`, and asserts that the freshly produced
# results.csv / summary.json / event_log.csv match the artefacts shipped
# at the project root byte-for-byte.
#
# Usage:
#   bash scripts/verify_reproducibility.sh [python_interpreter]
#
# Defaults the interpreter to `python3.13` if none is supplied. Exits
# non-zero on the first mismatch with a contextual message.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

PY_BIN="${1:-python3.13}"
VENV_DIR="$REPO_ROOT/.repro-venv"
RUN_DIR="$REPO_ROOT/.repro-run"

# Reset previous artefacts so we never accidentally pass on stale state.
rm -rf "$VENV_DIR" "$RUN_DIR"

echo "==> Creating clean virtualenv at $VENV_DIR using $PY_BIN"
"$PY_BIN" -m venv "$VENV_DIR"

VENV_PY="$VENV_DIR/bin/python"
"$VENV_PY" -m pip install --quiet --upgrade pip

echo "==> Installing pinned requirements"
"$VENV_PY" -m pip install --quiet -r "$REPO_ROOT/requirements.txt"

echo "==> Installing mine_sim (editable, pulls from pyproject.toml)"
"$VENV_PY" -m pip install --quiet -e "$REPO_ROOT"

echo "==> Running python -m mine_sim run-all (30 reps × 7 scenarios)"
( cd "$REPO_ROOT" && "$VENV_PY" -m mine_sim run-all \
    --output-dir "$RUN_DIR" --quiet )

echo "==> Comparing artefacts to shipped copies"
mismatch=0
for artefact in results.csv summary.json event_log.csv; do
    shipped="$REPO_ROOT/$artefact"
    produced="$RUN_DIR/$artefact"
    if [[ ! -f "$produced" ]]; then
        echo "    MISSING: $produced"
        mismatch=1
        continue
    fi
    if cmp -s "$shipped" "$produced"; then
        echo "    OK     : $artefact"
    else
        echo "    DIFFERS: $artefact"
        diff -u "$shipped" "$produced" | head -20 || true
        mismatch=1
    fi
done

if (( mismatch != 0 )); then
    echo "==> FAILED: at least one artefact differs from shipped output."
    exit 1
fi

echo "==> SUCCESS: all artefacts reproduced byte-for-byte from a clean install."
