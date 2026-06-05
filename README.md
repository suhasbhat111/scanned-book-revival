# Scanned Book → Clean HTML + PDF

A small, local, **free** pipeline that turns an old scanned book into a clean, modern,
mobile-friendly **HTML** reader and a **PDF** edition — with the original scan always one click
away. It uses [Surya OCR](https://github.com/datalab-to/surya) locally (no cloud, no API keys),
so your pages never leave your machine.

The worked example here is **_Hindu Holidays and Ceremonials_** by Rai Bahadur B. A. Gupte
(Thacker, Spink & Co., Calcutta, 1919) — 412 pages, public domain
([archive.org/details/cu31924024133922](https://archive.org/details/cu31924024133922), Cornell
University Library, no known U.S. copyright restrictions). The same pipeline is built to carry
other books and other scripts (English, Marathi, Hindi, Sanskrit).

**Get the finished editions:** see the [Releases](../../releases) page for the ready-to-read
HTML (zip) and PDF. This repo holds the **code** and the **structured OCR output** so you can
reproduce or adapt them.

---

## What you get

- **`book.html` + `assets/`** — a reader with Light/Sepia/Dark themes, a generated **Contents**
  drawer + jump-to-page, a **Compare** toggle (clean text ⇄ original scan), and **click-to-locate**
  (click any paragraph to highlight its exact spot on the scan). Images are external and
  lazy-loaded so it works on phones.
- **`book.pdf`** — strict 1:1 (each book page = one A4 sheet), warm background, real page numbers
  placed by the book's own convention, PDF bookmarks, and every clean page linked to its appended
  original scan (and back).

Design philosophy and the full decision log are in **[PLAYBOOK.md](PLAYBOOK.md)** — read it first.

## How it works (3 stages, each checkpointed to disk)

1. **Render + OCR** (`ocr_book.py`, launched via `run_full_ocr.sh`): PyMuPDF renders each page to
   300 DPI, Surya OCRs it, and one JSON per page is written atomically to `full/pNNNN.json` (plus
   the scan to `full/scans/`). **Resumable** — re-run any time and it skips finished pages.
2. **Build HTML** (`build_html.py`): reads all `full/*.json` → `book.html` + `assets/`.
3. **Build PDF** (`build_pdf.py`): reads the same JSON → `book.pdf` (weasyprint).

## Quick start

```bash
# 1. deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install llama.cpp pango          # Surya backend + weasyprint libs

# 2. OCR a PDF (resumable; safe to stop/re-run). Drop your scan in as source1.pdf
./run_full_ocr.sh                     # or: python ocr_book.py --pdf source1.pdf --dpi 300

# 3. build the editions
python build_html.py
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib   # weasyprint needs this on macOS
python build_pdf.py                   # add --pilot to test on 10 representative pages first
```

The OCR output for the example book is included (`full/*.json`), so you can run steps 2–3 without
re-OCRing. The page **scans** are not in the repo (they're large and reproducible) — get the
source PDF from the archive.org link above and run step 1, or grab the built editions from Releases.

## Adapting it to another book

Most of the pipeline is generic; a few things are per-book and are called out in **PLAYBOOK.md**:
the **folio (page-number) map**, which pages are plates/blanks/covers, the pilot page list, the
page geometry, and — for non-Latin scripts — a script-complete font (e.g. Noto Serif Devanagari)
and turning off Latin hyphenation. Edit the `folio()` functions and the CSS font stack in the two
builders.

## License

MIT — see [LICENSE](LICENSE). Code, OCR data, and editions may be reused freely. The source book
is public domain; please preserve its provenance front matter (library bookplate, copyright-status
notice) if you redistribute the edition.
