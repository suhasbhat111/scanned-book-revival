"""Full-book PDF builder for Diwali1.
Adapted from the signed-off .work/build_pdf.py — same design (1 book page = 1 sheet
via auto-shrink, folio placement, footnotes pinned, warm sheet, appended source
scans with bidirectional Original<->Back links) — extended for all 412 pages with:
  * appended source scans downscaled to ~150 DPI JPEG (single-pass render fits 8GB,
    links stay intact); clean reading pages + figure crops stay full quality
  * PDF bookmarks (outline) generated from the same cleaned headings as the HTML TOC
  * heading size trimmed to match the signed-off HTML
Run with --pilot to smoke-test on the 10 pilot pages.
Needs: DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib (weasyprint C libs).
"""
import json, base64, pathlib, re, io, sys, time
import html as _html
from PIL import Image
import weasyprint

ROOT = pathlib.Path(__file__).resolve().parent
FULL = ROOT / "full"
(ROOT / "build_tmp").mkdir(exist_ok=True)   # scratch for figure crops
PILOT = [1, 7, 14, 43, 47, 60, 61, 62, 349, 350]
PAGES = PILOT if "--pilot" in sys.argv else list(range(1, 413))

def to_roman(n):
    vals=[(1000,'m'),(900,'cm'),(500,'d'),(400,'cd'),(100,'c'),(90,'xc'),(50,'l'),
          (40,'xl'),(10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i')]
    out=''
    for v,s in vals:
        while n>=v: out+=s; n-=v
    return out
def folio(pdf):
    if pdf<=6: return None
    return to_roman(pdf-6) if pdf<=60 else str(pdf-60)
def folio_n(pdf):
    if pdf<=6: return None
    return (pdf-6) if pdf<=60 else (pdf-60)

TEXTISH={"Text","TextInlineMath","List-item","ListItem","Footnote","Caption",
         "Section-header","SectionHeader","Title","Heading"}
HEADISH={"Section-header","SectionHeader","Title","Heading"}
PICT={"Picture","Figure"}

def clean_text(html):
    return re.sub(r"\s+"," ",_html.unescape(re.sub("<[^>]+>"," ",html or ""))).strip()
def good_heading(t):
    if len(t)<4: return False
    if "]" in t or "[" in t: return False
    return True
def b64(p): return base64.b64encode(pathlib.Path(p).read_bytes()).decode()
def strip_p(h): return re.sub(r"</?p>","",h).strip()
def ink_fraction(p):
    im=Image.open(p).convert("L").resize((120,160)); px=list(im.getdata())
    return sum(1 for v in px if v<110)/len(px)
def src_jpeg_b64(scan, max_w=720, q=80):           # downscale appended reference scans
    im=Image.open(scan).convert("RGB")
    if im.width>max_w:
        im=im.resize((max_w, round(im.height*max_w/im.width)))
    buf=io.BytesIO(); im.save(buf,"JPEG",quality=q,optimize=True)
    return base64.b64encode(buf.getvalue()).decode()

# per-page caches so the auto-shrink loop doesn't redo image work each attempt
_page_cache={}
def load_page(pno):
    if pno not in _page_cache:
        _page_cache[pno]=json.load(open(FULL/f"p{pno:04d}.json"))
    return _page_cache[pno]

def norm_key(t): return re.sub(r"[^a-z0-9]","",t.lower())

def render_block(blk, scan, pno, idx, has_pic, is_bk=False):
    lab=blk["label"]; html=(blk["html"] or "").strip()
    if lab in ("Page-header","PageHeader"): return ""
    if lab in ("Page-footer","PageFooter"):
        return f'<p class="credit">{strip_p(html)}</p>' if (has_pic and html) else ""
    if lab in PICT:
        x0,y0,x1,y1=[int(v) for v in blk["bbox"]]
        cp=ROOT/"build_tmp"/f"pcrop_p{pno}_{idx}.png"
        if not cp.exists(): Image.open(scan).crop((x0,y0,x1,y1)).save(cp)
        return f'<figure class="plate"><img src="data:image/png;base64,{b64(cp)}"></figure>'
    if not html: return ""
    if lab in HEADISH:
        inner=re.sub(r"</?h[1-6][^>]*>","",html)   # drop OCR's <h1> wrapper (weasyprint auto-bookmarks it, and it sizes wrong)
        inner=re.sub(r"<br ?/?>"," ",inner)          # drop forced breaks so the heading flows to one line
        inner=strip_p(re.sub(r"\s+"," ",inner)).strip()
        if is_bk:
            return f'<div class="hd bk" data-bk="{_html.escape(clean_text(html), quote=True)}">{inner}</div>'
        return f'<div class="hd">{inner}</div>'
    if lab=="Caption":  return f'<p class="cap">{strip_p(html)}</p>'
    if lab=="Footnote": return f'<div class="fn">{re.sub(r"<hr ?/?>","",html).strip()}</div>'
    return f'<div class="blk">{html}</div>'

def page_section(pno, pt=None):
    page=load_page(pno); blocks=page["blocks"]; scan=str(FULL/"scans"/f"scan_p{pno:04d}.png")
    fol=folio(pno)
    real_text=any(b["label"] in TEXTISH and (b["html"] or "").strip() for b in blocks)
    has_pic=any(b["label"] in PICT for b in blocks)
    style=f' style="font-size:{pt}pt"' if pt else ''
    orig=f'<a class="orig" href="#src{pno}">See Original Page &#8599;</a>'
    if not real_text and ink_fraction(scan)>0.95:
        return f'<section class="pdfpage" id="p{pno}"{style}><div class="notext">Cover &mdash; no readable text</div>{orig}</section>'
    if not real_text and ink_fraction(scan)<0.03:
        return f'<section class="pdfpage" id="p{pno}"{style}><div class="notext">No Text on original book</div>{orig}</section>'
    top_folio=''
    if fol and pno<=60:
        pos='fl' if folio_n(pno)%2==0 else 'fr'
        top_folio=f'<div class="folio-mark {pos}">{fol}</div>'
    bk_ids=BK_MAP.get(pno, set())     # precomputed once, with global cross-page dedup
    npic=sum(1 for b in blocks if b["label"] in PICT)
    if npic>=2:                       # multi-figure plate: show the whole scan (keeps original layout), not stacked crops
        fns=[]
        main_html=top_folio+f'<figure class="plate plate-full"><img src="data:image/png;base64,{b64(scan)}"></figure>'
    else:
        main=[]; fns=[]
        for i,b in enumerate(blocks):
            (fns if b["label"]=="Footnote" else main).append(render_block(b,scan,pno,i,has_pic,i in bk_ids))
        main_html=top_folio+"".join(x for x in main if x)
        if not main_html.strip():
            main_html=top_folio+f'<figure class="plate"><img src="data:image/png;base64,{b64(scan)}"></figure>'
    bot_folio=f'<div class="folio-bottom">{fol}</div>' if (fol and pno>60) else ''
    bottom="".join(x for x in fns if x)+bot_folio
    bottom=f'<div class="pagebottom">{bottom}</div>' if bottom.strip() else ''
    return f'<section class="pdfpage" id="p{pno}"{style}><div class="main">{main_html}</div>{bottom}{orig}</section>'

CSS="""
@page{ size:21cm 29.7cm; margin:1.5cm 2.5cm; background:#F6F2E9; }
html{ background:#F6F2E9; color:#21201C; font-family:Georgia,"Times New Roman",serif; }
.pdfpage{ position:relative; height:26.7cm; font-size:11.5pt; line-height:1.5; text-align:justify; hyphens:auto; }
.blk{margin:0 0 .9em;} .blk p{margin:0 0 .9em;}
b{font-weight:700;} i{font-style:italic;}
.hd{font-size:1.15em;text-align:center;font-weight:600;margin:0 0 .8em;line-height:1.3;letter-spacing:.02em;}
.bk{ bookmark-level:1; bookmark-label:attr(data-bk); }
.cap{text-align:center;color:#8c8678;font-size:.92em;font-style:italic;margin:.3em 0 0;}
.credit{text-align:center;color:#8c8678;font-size:.8em;margin:.4em 0 0;}
.folio-mark{color:#8c8678;font-size:1em;margin-bottom:1.4em;}
.folio-mark.fl{text-align:left;} .folio-mark.fr{text-align:right;}
.pagebottom{position:absolute;left:0;right:0;bottom:0;}
.fn{font-size:.85em;color:#6f6a5f;border-top:1px solid #d9d2c2;padding-top:.5em;margin-top:0;}
.fn p{margin:.15em 0;}
.folio-bottom{text-align:center;color:#8c8678;margin-top:.6em;}
.plate{margin:0 0 .8em;text-align:center;} .plate img{max-width:74%;max-height:21cm;border:1px solid #d9d2c2;background:#fff;}
.plate-full img{max-width:96%;max-height:24.5cm;}   /* full-plate scan fits one sheet */
.notext{position:absolute;top:45%;left:0;right:0;text-align:center;color:#8c8678;font-style:italic;}
.orig{position:absolute;right:0;bottom:-.25cm;font-family:system-ui,sans-serif;font-size:7.5pt;color:#1b6e3c;text-decoration:none;}
.srcpage{height:26.7cm;position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;break-after:page;}
.srcpage img{max-width:100%;max-height:25cm;border:1px solid #999;background:#fff;}
.srccap{font-family:system-ui,sans-serif;font-size:8pt;color:#8c8678;margin-top:.4cm;}
.back{position:absolute;left:0;top:-.1cm;font-family:system-ui,sans-serif;font-size:7.5pt;color:#1b6e3c;text-decoration:none;}
.pdfpage{break-after:page;}
"""
def wrap(body):
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
def n_pages(body):
    return len(weasyprint.HTML(string=wrap(body)).render().pages)

# Precompute bookmark-worthy headings once (global dedup: a repeated heading = running head,
# keep only its first occurrence). Mirrors the HTML Contents but cleaner.
BK_MAP={}; _bk_seen=set()
for pno in PAGES:
    ids=set()
    for i,b in enumerate(load_page(pno)["blocks"]):
        if b["label"] in HEADISH:
            ct=clean_text(b["html"]); k=norm_key(ct)
            if good_heading(ct) and k and k not in _bk_seen:
                _bk_seen.add(k); ids.add(i)
    BK_MAP[pno]=ids
print(f"  bookmarks to emit: {sum(len(v) for v in BK_MAP.values())}", flush=True)

LADDER=(11.5,11,10.5,10,9.5,9,8.5,8,7.5,7)   # extended below the pilot's 8pt floor for dense index pages
t0=time.time(); clean_pages=[]; overflow=[]
for k,pno in enumerate(PAGES,1):
    chosen=LADDER[-1]
    for pt in LADDER:
        if n_pages(page_section(pno, pt))==1: chosen=pt; break
    else:
        overflow.append(pno)            # still >1 sheet even at the smallest size
    clean_pages.append(page_section(pno, chosen))
    if k%25==0 or k==len(PAGES):
        print(f"  fit {k}/{len(PAGES)} (p{pno}) … {time.time()-t0:.0f}s", flush=True)

print("  rendering appended source scans (downscaled)…", flush=True)
src_pages=[f'<section class="srcpage" id="src{pno}"><a class="back" href="#p{pno}">&#8617; Back to New PDF</a>'
           f'<img src="data:image/jpeg;base64,{src_jpeg_b64(str(FULL/"scans"/f"scan_p{pno:04d}.png"))}">'
           f'<div class="srccap">Original scan &middot; PDF page {pno}</div></section>'
           for pno in PAGES]

print("  final weasyprint pass…", flush=True)
OUT = ROOT / ("Hindu Holidays and Ceremonials - B. A. Gupte" + ("-pilot" if "--pilot" in sys.argv else "") + ".pdf")
weasyprint.HTML(string=wrap("".join(clean_pages)+"".join(src_pages))).write_pdf(str(OUT))
mb=OUT.stat().st_size/1048576
print(f"wrote {OUT}  ({mb:.1f} MB, {len(PAGES)} pages)  in {time.time()-t0:.0f}s")
if overflow: print(f"  NOTE: {len(overflow)} page(s) still exceed one sheet at 7pt: {overflow}")
