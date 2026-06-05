#!/bin/zsh
# Launch the full-book OCR so it survives an idle Mac (caffeinate) and is easy to resume.
# Just run:  ./run_full_ocr.sh        (or pass through args, e.g. ./run_full_ocr.sh --start 200)
# Safe to stop (Ctrl-C) and re-run any time — it resumes where it left off.
cd "$(dirname "$0")"
mkdir -p full
echo "Starting full-book OCR. Safe to stop and re-run; it resumes. Logging to full/run.log"
caffeinate -i -s .venv/bin/python ocr_book.py "$@" 2>&1 | tee -a full/run.log
