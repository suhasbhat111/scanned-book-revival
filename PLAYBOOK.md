# Turning Old Scanned Books into Clean Modern Editions — A Playbook

*A working essay on what we set out to do, the walls we hit, the choices we made, and the
pipeline we ended up trusting. Written for a human to read first — and for a future
assistant (e.g. a cheaper Claude Code model) to pick up and run with. The first project was a
1916 English book; the same method is meant to carry English, Marathi, Hindi and Sanskrit
scans that are coming next.*

---

## 1. Where we started

The goal sounded simple: take an old scanned book — `source1.pdf`, 412 pages of
*Hindu Holidays and Ceremonies* (B. A. Gupte, Calcutta, 1916) — and turn it into a **clean,
beautiful, modern document that is a pleasure to read on a screen or phone**, as both an
**HTML** page and a **PDF**. Printing was explicitly *not* a goal; everything is for screens.

The first idea was to use "DeepSeek OCR" because an API key was already paid for, and to keep
costs low and avoid other AI providers. That starting assumption turned out to be wrong in an
instructive way, and unwinding it taught us most of what follows.

The deeper truth we kept returning to: **the original is a scanned image with, at best, a bad
buried text layer. OCR is genuinely required, and OCR is never perfect.** Every design
decision flows from accepting that honestly rather than pretending a machine will read a
110‑year‑old page flawlessly.

---

## 2. The problems we hit, the options we weighed, and how we chose

### 2.1 "DeepSeek OCR" is not what it sounds like

The single biggest early confusion: **DeepSeek's hosted cloud API has no OCR endpoint.** It
serves text models only (`deepseek-v4-flash`, `deepseek-v4-pro`). "DeepSeek‑OCR" / "DeepSeek‑OCR‑2"
are *open‑source vision models* you must run yourself or via a third‑party host — and, tested on
real Devanagari (a developer's Bhagavad Gita experiment), the pretrained model **could not read
the script** without fine‑tuning. So a paid DeepSeek key buys you nothing for OCR, and the
DeepSeek OCR model is weak on exactly the Indic scripts we care about.

**Lesson (generic):** separate the *company's hosted API* from an *open‑source model that
shares its name*. They have different capabilities, costs, and hosting stories. Verify the
endpoint actually exists before building on it.

### 2.2 Choosing the OCR engine — by evidence, not opinion

Rather than argue, we OCR'd the *same* representative pages with each candidate and compared
the raw output against the scan. This empirical bake‑off was the turning point.

| Engine | Verdict on real pages |
|---|---|
| **Existing archive text layer** | Garbage on anything stylized (signatures, botanical Latin), one‑word‑per‑line reading order. Unusable as "clean." |
| **Tesseract 5** | Big improvement over the old layer; correct on most prose. But **drops diacritics** (macrons), **misses unusual layout** (dropped a signature block), and stumbles on digits/odd glyphs. |
| **Google Document AI** (Enterprise Document OCR) | Excellent, ~tied with Surya on character accuracy, and *fast* (cloud, seconds). But basic OCR returns **no bold/italic**, it **dropped an em‑dash**, and it's a cloud service (pages leave the machine). ~$1.50 / 1,000 pages; $300 new‑account credit. |
| **Surya** (datalab‑to/surya) | **Winner.** Near‑publication quality *with* `<b>`/`<i>` formatting preserved, scholarly **diacritics intact**, correct **reading order**, and it caught the layout Tesseract dropped. Free, fully local, private. Slow (~50 s/page on an 8 GB M1 → ~5–6 h for the book). |

**Decision: Surya, run locally.** It won on the exact things this material needs — formatting,
diacritics, em‑dashes, faithful reading order — and stayed free and private. Its only real cost
is speed, which is fine for an overnight batch. Google remains a validated fast fallback if a
future project is huge or time‑critical.

**Lesson (generic):** pick the OCR engine by running it on *your* hardest representative pages
and reading the output, not by spec sheets. For old printed books rich in non‑English terms,
*formatting + diacritic fidelity* matters as much as raw character accuracy.

### 2.3 The "be clever and clean up the text" trap

Tempting idea: run a dictionary/spell‑checker over the OCR to fix the few errors. We tried it.
It was a **net negative**: an English dictionary doesn't know Sanskrit, Indian English, or
botanical Latin, so it "corrected" *correct* words into nonsense — `puja → puma`, `pipal →
papal`, `Ficus religiosa → religiose`, even British `neighbours → neighbors`.

**Lesson (generic, and crucial for Marathi/Hindi/Sanskrit):** **do faithful OCR with (almost)
no automated correction.** The cleverness is the saboteur, not the OCR. Where errors remain,
let the reader fall back to the original rather than letting software guess. This matters *more*
as scripts get more specialized.

### 2.4 LLMs are the wrong tool for the transcription itself

A separate temptation is to have an LLM "read" the page image and type it out. Don't. LLMs are
fluent but **unfaithful** — they hallucinate, silently normalize archaic spelling, and drop
lines, with no confidence signal. A **dedicated OCR engine** is deterministic, reports
per‑word confidence and bounding boxes, and cannot rewrite the book. Use the LLM (if at all)
for orchestration and assembly, never for the character recognition.

### 2.5 The OpenCV preprocessing myth

"OpenCV + OCR (deskew, denoise, binarize)" is real, useful advice — *for Tesseract‑era engines*.
For a modern neural OCR like Surya it is unnecessary and often **harmful**: binarization throws
away grayscale detail the model uses, denoise softens the fine strokes that distinguish `ā`
from `a`, and the detector already handles skew. **Feed Surya the raw 300‑DPI render.** The one
preprocessing knob that truly matters is **resolution (300 DPI)**.

**Lesson (generic):** classic-OCR folk wisdom doesn't transfer to neural OCR. Preprocess
reactively (only a specific bad page), never as a blanket pipeline.

### 2.6 Designing the *output*, decision by decision

Once OCR was settled, the real work was turning faithful per‑page text into a clean edition.
Each of these became a rule:

- **Strict 1:1 page mapping.** Book page *N* → output page *N*, always. No reflowing
  paragraphs across pages. This keeps the new edition anchored to the original for reference.
- **Page numbers (folios) shown clean and correct, derived from the *sequence*, not OCR.** The
  scanned corner number is tiny and noisy (book page 1 scanned as `a`); we compute the folio
  from verified anchors so noise is auto‑corrected. **Two placement rules** matched the book:
  roman front‑matter folios sit at the **top outer corner** (even→left, odd→right); arabic body
  folios sit **bottom‑center**. The folio lives *inside* the page (it's really on the page);
  the running PDF page index is metadata shown *outside* the page boundary.
- **Images reproduced as‑is.** OCR can't improve a photo or drawing, so we crop the region
  Surya labels `Picture` straight from the scan and place it. Captions/credits are kept.
- **Blank vs image vs cover.** A near‑white page → "No Text on original book." An all‑black
  cover scan → "Cover — no readable text" (never a black block). Decided by ink fraction, since
  Surya tags even a faint blank as a `Picture`.
- **Running heads dropped, real footnotes kept and pinned to the page bottom.**
- **Reading comfort, not period imitation.** Warm off‑white background (never pure white),
  dark‑grey text (never pure black), a diacritic‑complete serif, generous line height, a
  **standard modern page proportion (A4, 1:1.414)** — *not* the 1920 book's shape. The whole
  point is a modern edition.
- **Side‑by‑side belongs to HTML.** The HTML viewer does true interactive comparison
  (clean‑left / scan‑right toggle, synced, **click a paragraph to highlight it on the scan**).
  A PDF is sequential pages and can only *approximate* this; we kept the reading PDF clean, with
  a per‑page link that jumps to the appended original ("See Original Page ↗" / "↩ Back to New
  PDF"). True one‑gaze side‑by‑side in PDF would require a separate landscape "parallel edition."

### 2.7 Two engineering choices worth remembering

- **Constant font beats shrink‑to‑fit.** To keep strict 1:1 on a fixed page, dense pages would
  have to shrink their type — degrading quality unevenly. Because print isn't a goal, the better
  move is a **page tall/large enough that even dense pages fit at one constant font size**;
  treat per‑page shrinking only as a rare safety net. Screen readers don't care about whitespace
  on sparse pages.
- **weasyprint quirks (macOS).** Its flexbox ignores `margin-top:auto`, so "pin to bottom" must
  use **absolute positioning**. A warm page needs `background` on the **`@page`** rule (and use a
  single `@page`; a *named* `@page` may not paint its background). It needs Homebrew libs found
  via `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`.

### 2.8 How we *worked* — the method that kept us sane

- **Prototype before big effort.** We never ran the 5–6 hour OCR to test a layout idea. We
  curated a **10‑page sample that deliberately hits the hard cases** (cover, photo plate,
  drawing+caption, blank, roman folio, arabic folio, the noise‑corrected page 1, a footnote,
  dense formatting) and iterated the HTML and PDF on *those* in seconds.
- **Formal sign‑off gates.** HTML pilot and PDF pilot are explicit approvals before scaling.
- **Decide, don't dither.** Recommend firmly with the data; don't bury the user in optional
  experiments. Lock decisions and move.

---

## 3. The final pipeline (tools and stages)

**Environment:** macOS (Apple Silicon), Python venv. Long runs are a **standalone terminal
command, independent of any assistant**, wrapped in `caffeinate` so the Mac won't sleep.

**Tools:**
- **PyMuPDF (`fitz`)** — render each PDF page to a 300‑DPI PNG (`page.get_pixmap(dpi=300)`); also
  cheap page analysis (text length, ink fraction) to spot blanks/plates.
- **Surya OCR (0.20)** — the OCR engine. Needs the llama.cpp backend (`brew install llama.cpp`).
  Runs on Apple MPS. Per page it returns **blocks** with: `label` (Text, Section‑header,
  Page‑header, Page‑footer, Picture, Caption, Footnote…), `html` (preserves `<b>`/`<i>`),
  `bbox`/`polygon`, `reading_order`, `confidence`.
- **weasyprint (69)** — HTML/CSS → PDF (`brew install pango`; set `DYLD_FALLBACK_LIBRARY_PATH`).
- **Plain HTML + CSS + a little JS** — the interactive reading/compare viewer.
- (Benchmark‑only, not in the pipeline: Tesseract 5, Google Document AI via a gcloud access
  token.)

**Stages (each writes to disk so nothing is ever redone):**
1. **Render** — PDF → 300‑DPI page PNGs.
2. **OCR (the long step, resumable)** — Surya over every page, **writing one JSON per page
   immediately** (`full/pNNN.json`). On restart it skips finished pages and continues, so a
   crash/close costs at most one page (~1 min). Memory stays flat. A `X / N done` progress line.
3. **Assemble** — read the per‑page JSON and build (a) the **clean HTML** (themes, Compare
   toggle, click‑to‑locate) and (b) the **clean PDF** (A4, warm background, constant font,
   folios by the two rules, images as‑is, footnotes pinned, appended originals + jump links).

---

## 4. What is generic vs. book‑specific

**Generic — reuse for every scanned‑book project:**
- The whole tool stack and the three‑stage render → OCR → assemble pipeline.
- **Surya, local, raw 300 DPI** as the default engine and input (Google as fast fallback).
- The **"faithful OCR, no clever auto‑cleanup"** rule (even more important for Indic scripts).
- The **output‑rule framework**: 1:1 mapping; folios computed from sequence; images as‑is;
  blank/cover handling by ink; running heads dropped, footnotes kept; warm reading background;
  modern page proportion; constant font on a big‑enough page; side‑by‑side in HTML, links in PDF.
- The **resumable, checkpointed, independent** long‑run design (+ `caffeinate`).
- The **method**: curated hard‑case 10‑page pilots, formal sign‑off gates, decide‑don't‑dither.
- weasyprint macOS workarounds (absolute‑position bottom matter, `@page` background, DYLD path).

**Book‑specific — re‑derive per book:**
- **Folio map.** The numbering anchors and front‑matter boundaries (for this book: PDF 1–6
  unnumbered; 7–60 roman = pdf−6; 61+ arabic = pdf−60; verified PDF 14 = `viii`, 43 = `xxxvii`,
  61 = body `1`). Every book differs.
- **Which physical pages are plates, blanks, covers** (found by an ink/text scan, then eyeballed).
- **The curated pilot page list** (pick that book's hard cases).
- **Exact dimensions/margins/font size** (tuned so that book's densest page holds constant font).
- **Language & script.** This was English. For **Marathi / Hindi / Sanskrit** (Devanagari):
  Surya supports Devanagari and handled transliteration/diacritics well here, but **verify on a
  sample first**; choose a **Devanagari‑complete font** (e.g. a Noto Serif Devanagari) for the
  clean output; folios may be in Devanagari numerals; and remember these commentaries often
  **mix Sanskrit into Marathi/Hindi**, so the no‑auto‑correction rule is non‑negotiable.

---

## 5. The one‑paragraph version

Take the scan, render it at 300 DPI, and run **Surya locally** to get faithful text *with*
formatting, diacritics, reading order, and per‑word boxes — and resist every urge to "clean it
up" with a dictionary or an LLM, because that corrupts the very terms that make these books
worth preserving. Reassemble it 1:1 into a **modern, warm, comfortably‑typeset** HTML and PDF,
keeping the original page numbers and images as‑is, with the scanned original always one click
(HTML: live side‑by‑side; PDF: a jump link) away for when OCR inevitably slips. Prove every
design choice on a small, deliberately hard pilot before spending hours on the whole book, make
the long OCR run resumable so a crash costs a minute not a night, and treat the tool pipeline as
generic while re‑deriving the folio map, the plate/blank pages, and the language/font per book.
