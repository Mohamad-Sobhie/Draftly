#!/usr/bin/env bash
# Draftly one-time setup: Python venv, dependencies, folders, self-test.
# Safe to run again at any time (e.g. after updating the template).
set -u

cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; exit 1; }

case "$(uname -s 2>/dev/null)" in
  Darwin) OS=mac ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  *) OS=linux ;;
esac

bold "Draftly setup ($OS)"

# 1. Python 3.10+ ------------------------------------------------------------
PY=""
for cand in python3.13 python3.12 python3.11 python3.10 python3 python py; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  warn "Python 3.10 or newer is required."
  [ "$OS" = mac ] && echo "    Install: brew install python   (or https://www.python.org/downloads/)"
  [ "$OS" = windows ] && echo "    Install from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')"
  fail "Python not found"
fi
ok "Python: $("$PY" --version 2>&1)"

# 2. Virtual environment + requirements ---------------------------------------
if [ "$OS" = windows ]; then VPY="$ROOT/.venv/Scripts/python.exe"; else VPY="$ROOT/.venv/bin/python"; fi
if [ ! -x "$VPY" ]; then
  "$PY" -m venv .venv || fail "Could not create .venv"
fi
"$VPY" -m pip install --quiet --upgrade pip >/dev/null 2>&1
if "$VPY" -m pip install --quiet -r scripts/requirements.txt; then
  ok "Python packages installed in .venv"
else
  fail "pip install failed (check your internet connection and run again)"
fi

# 3. Optional system tools ----------------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }
if have pdftotext && have pdftoppm; then ok "poppler (pdftotext) found"; else
  warn "poppler not found (optional: better text for tricky PDFs, needed for OCR)"
  [ "$OS" = mac ] && echo "    brew install poppler"
  [ "$OS" = windows ] && echo "    winget install oschwartz10612.Poppler   (or download 'poppler for Windows' and add its bin folder to PATH)"
  [ "$OS" = linux ] && echo "    sudo apt install poppler-utils"
fi
if have tesseract; then ok "tesseract (OCR for scanned PDFs) found"; else
  warn "tesseract not found (optional: needed to read scanned PDFs)"
  [ "$OS" = mac ] && echo "    brew install tesseract"
  [ "$OS" = windows ] && echo "    winget install UB-Mannheim.TesseractOCR   (then add it to PATH)"
  [ "$OS" = linux ] && echo "    sudo apt install tesseract-ocr"
fi
if have ocrmypdf; then ok "ocrmypdf found"; else
  echo "    (optional) ocrmypdf gives the best OCR results: brew install ocrmypdf / pip install ocrmypdf"
fi

# 4. Folders --------------------------------------------------------------------
for d in references/inbox references/pdf references/text notes sessions drafts; do
  mkdir -p "$d"; [ -f "$d/.gitkeep" ] || touch "$d/.gitkeep"
done
ok "Folders ready"

# 5. Self-test ------------------------------------------------------------------
bold "Self-test"
if "$VPY" scripts/selftest.py; then
  ok "Self-test passed"
else
  fail "Self-test failed - see the messages above"
fi

# 6. Build the (empty) library page so it exists
"$VPY" scripts/build_library.py >/dev/null && ok "library.html built"

echo
bold "All set."
echo "Next: open this folder in Claude Code and type:  menu"
echo "      (first time: do the short setup questions together with the student)"
