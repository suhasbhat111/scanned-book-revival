#!/usr/bin/env python3
"""
Resumable, constant-memory Surya OCR for an entire scanned book.

For each PDF page it: renders to <dpi> PNG, runs Surya, and writes ONE json per
page *immediately* (atomically). Stop it, crash it, close the lid, close the
Terminal — re-run the exact same command and it skips finished pages and
continues. At most the single in-flight page (~1 min) is ever lost.

    .venv/bin/python ocr_book.py                     # all pages of source1.pdf
    .venv/bin/python ocr_book.py --start 60 --end 80 # a range
    .venv/bin/python ocr_book.py --pdf other.pdf --out full2

Output (default dir ./full):
    full/pNNNN.json        one structured page (blocks: label, html, bbox, conf, order)
    full/scans/scan_pNNNN.png   the 300-DPI render (used later for images + compare)
    full/errors.log        any page that failed (left unwritten so it retries next run)
"""
import argparse, json, time, gc, pathlib, traceback
import fitz
from PIL import Image


def poly_to_bbox(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return [min(xs), min(ys), max(xs), max(ys)]


def extract_blocks(res):
    blocks = []
    for b in sorted(res.blocks, key=lambda b: b.reading_order if b.reading_order is not None else 0):
        if not (b.html or "").strip() and b.label not in ("Picture", "Figure"):
            continue
        blocks.append({
            "order": b.reading_order,
            "label": b.label,
            "conf": round(b.confidence or 0, 3),
            "html": b.html,
            "bbox": poly_to_bbox(b.polygon),
        })
    return blocks


def main():
    ap = argparse.ArgumentParser(description="Resumable full-book Surya OCR")
    ap.add_argument("--pdf", default="source1.pdf")
    ap.add_argument("--out", default="full")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=0, help="0 = last page")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    (out / "scans").mkdir(parents=True, exist_ok=True)

    doc = fitz.open(args.pdf)
    N = doc.page_count
    end = args.end or N
    wanted = list(range(args.start, end + 1))
    todo = [p for p in wanted if not (out / f"p{p:04d}.json").exists()]
    done = len(wanted) - len(todo)
    print(f"[{args.pdf}] {N} pages total. Range {args.start}-{end}: "
          f"{done} already done, {len(todo)} to OCR.", flush=True)
    if not todo:
        print("Nothing to do — all requested pages already OCR'd.", flush=True)
        return

    print("Loading Surya models (one time)…", flush=True)
    from surya.detection import DetectionPredictor
    from surya.recognition import RecognitionPredictor
    det = DetectionPredictor()
    rec = RecognitionPredictor()

    t_start = time.time()
    n = 0
    for p in todo:
        t0 = time.time()
        try:
            pix = doc[p - 1].get_pixmap(dpi=args.dpi)
            scan_path = out / "scans" / f"scan_p{p:04d}.png"
            pix.save(str(scan_path))
            w, h = pix.width, pix.height
            img = Image.open(scan_path).convert("RGB")

            res = rec([img], full_page=True)[0]
            data = {"pdf_page": p, "w": w, "h": h, "dpi": args.dpi,
                    "blocks": extract_blocks(res)}
            nb = len(data["blocks"])

            tmp = out / f"p{p:04d}.json.tmp"
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(out / f"p{p:04d}.json")          # atomic: never a half-written file

            img.close()
            del img, res, pix, data
            gc.collect()

            n += 1
            elapsed = time.time() - t_start
            eta = (elapsed / n) * (len(todo) - n)
            print(f"[{n:>3}/{len(todo)}] page {p:>4}: {nb:>2} blocks  "
                  f"{time.time()-t0:4.0f}s   ETA {eta/60:5.1f} min", flush=True)
        except KeyboardInterrupt:
            print("\nInterrupted — all completed pages are saved. Re-run to resume.", flush=True)
            return
        except Exception as e:
            (out / "errors.log").open("a").write(
                f"page {p}: {e}\n{traceback.format_exc()}\n")
            print(f"[!] page {p} FAILED: {e}  (logged; will retry next run)", flush=True)
            continue

    print(f"\nFinished this run: {n} pages in {(time.time()-t_start)/60:.1f} min. "
          f"Run again any time to fill in any that failed.", flush=True)


if __name__ == "__main__":
    main()
