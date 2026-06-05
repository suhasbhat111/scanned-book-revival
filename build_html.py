"""Full-book HTML builder for Diwali1.
Adapted 1:1 from the signed-off .work/build_prototype.py — identical rendering
rules and CSS/JS — but reads all full/pNNNN.json + full/scans/, and writes images
to an external assets/ folder (lazy-loaded) instead of inlining base64, so the
output works on mobile. Emits book.html at the project root.
"""
import json, pathlib, re, shutil, sys
import html as _html
from PIL import Image

ROOT   = pathlib.Path(__file__).resolve().parent
FULL   = ROOT / "full"
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

PAGES = list(range(1, 413))   # all 412 pages, strict 1:1 mapping

def to_roman(n):
    vals=[(1000,'m'),(900,'cm'),(500,'d'),(400,'cd'),(100,'c'),(90,'xc'),(50,'l'),
          (40,'xl'),(10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i')]
    out=''
    for v,s in vals:
        while n>=v: out+=s; n-=v
    return out
def folio(pdf):                       # PDF 1-6 unnumbered, 7-60 roman, 61+ arabic
    if pdf <= 6: return None
    if pdf <= 60: return to_roman(pdf-6)
    return str(pdf-60)
def folio_n(pdf):
    if pdf <= 6: return None
    return (pdf-6) if pdf <= 60 else (pdf-60)

TEXTISH={"Text","TextInlineMath","List-item","ListItem","Footnote","Caption",
         "Section-header","SectionHeader","Title","Heading"}
HEADISH={"Section-header","SectionHeader","Title","Heading"}
PICT={"Picture","Figure"}

def clean_text(html):
    return re.sub(r"\s+", " ", _html.unescape(re.sub("<[^>]+>", " ", html or ""))).strip()
def good_heading(t):                       # filter noise out of the generated Contents
    if len(t) < 4: return False            # drops the single-letter A/B/C index dividers
    if "]" in t or "[" in t: return False  # drops running-head artifacts ("Topic] HINDU HOLIDAYS")
    return True
def strip_p(h): return re.sub(r"</?p>","",h).strip()
def bbstr(bb): return ",".join(str(int(x)) for x in bb)
def ink_fraction(p):
    im=Image.open(p).convert("L").resize((120,160)); px=list(im.getdata())
    return sum(1 for v in px if v<110)/len(px)

def render_block(blk, scan, pno, idx, has_pic):
    lab=blk["label"]; html=(blk["html"] or "").strip(); bb=bbstr(blk["bbox"])
    if lab in ("Page-header","PageHeader"): return ""          # running head: always drop
    if lab in ("Page-footer","PageFooter"):                    # folio (drop) OR plate credit (keep)
        return f'<p class="credit" data-bbox="{bb}">{strip_p(html)}</p>' if (has_pic and html) else ""
    if lab in PICT:
        x0,y0,x1,y1=[int(v) for v in blk["bbox"]]
        crop=Image.open(scan).crop((x0,y0,x1,y1))
        cp=ASSETS/f"crop_p{pno:04d}_{idx}.png"; crop.save(cp)
        return f'<figure class="plate" data-bbox="{bb}"><img loading="lazy" src="assets/{cp.name}"></figure>'
    if not html: return ""
    if lab in HEADISH: return f'<h2 class="hd" data-bbox="{bb}">{strip_p(html)}</h2>'
    if lab=="Caption":  return f'<p class="cap" data-bbox="{bb}">{strip_p(html)}</p>'
    if lab=="Footnote":
        return f'<div class="fn" data-bbox="{bb}">{re.sub(r"<hr ?/?>","",html).strip()}</div>'
    return f'<div class="blk" data-bbox="{bb}">{html}</div>'

sections=[]
toc=[]                                      # (pno, folio_label, heading_text) for the Contents drawer
for pno in PAGES:
    jf = FULL / f"p{pno:04d}.json"
    page=json.load(open(jf)); blocks=page["blocks"]; w=page["w"]
    scan = FULL / "scans" / f"scan_p{pno:04d}.png"
    # copy the full scan into assets/ once (referenced by Compare view, lazy-loaded)
    dst = ASSETS / f"scan_p{pno:04d}.png"
    if not dst.exists(): shutil.copy(scan, dst)
    scan_src = f"assets/scan_p{pno:04d}.png"

    fol=folio(pno)
    # collect cleaned section headings for the generated Contents (skip noise + dups)
    for b in blocks:
        if b["label"] in HEADISH:
            ht=clean_text(b["html"])
            if good_heading(ht) and not (toc and toc[-1][2]==ht):
                toc.append((pno, fol or "—", ht))
    real_text=any(b["label"] in TEXTISH and (b["html"] or "").strip() for b in blocks)
    has_pic=any(b["label"] in PICT for b in blocks)
    ink=ink_fraction(scan)

    show_folio=True
    if not real_text and ink>0.95:
        inner='<div class="notext">Cover &mdash; no readable text</div>'; show_folio=False
    elif not real_text and ink<0.03:
        inner='<div class="notext">No Text on original book</div>'; show_folio=False
    else:
        body="\n".join(render_block(b,scan,pno,i,has_pic) for i,b in enumerate(blocks))
        inner=body or f'<figure class="plate"><img loading="lazy" src="{scan_src}"></figure>'

    top_folio=bot_folio=''
    if show_folio and fol:
        if pno <= 60:   # roman front matter -> top outer corner (even=left, odd=right)
            pos='fl' if folio_n(pno)%2==0 else 'fr'
            top_folio=f'<div class="folio-mark {pos}">{fol}</div>'
        else:           # arabic body -> bottom center
            bot_folio=f'<div class="folio-bottom">{fol}</div>'
    sections.append(f"""
  <div class="pagewrap" id="page-{pno}">
    <div class="meta"><span>PDF page {pno}</span>
      <button class="toggle" data-act="compare">Compare</button></div>
    <section class="page" data-w="{w}"><div class="body">
      <article class="clean">{top_folio}{inner}{bot_folio}</article>
      <div class="scan"><div class="scanwrap"><img loading="lazy" src="{scan_src}"><div class="hl"></div></div></div>
    </div></section>
  </div>""")
    if pno % 25 == 0 or pno == PAGES[-1]:
        print(f"  ...rendered {pno}/{PAGES[-1]}", flush=True)

CSS="""
:root{--maxw:40rem;}
html[data-theme=light]{--bg:#F6F2E9;--ink:#21201C;--soft:#8c8678;--card:#fffdf8;--line:#e4ded0;--accent:#1b6e3c;}
html[data-theme=sepia]{--bg:#FBF0D9;--ink:#4B3F30;--soft:#a08a66;--card:#fff8e9;--line:#ecdcbf;--accent:#8a5a1b;}
html[data-theme=dark]{--bg:#1C1B19;--ink:#CFC9BE;--soft:#7d776c;--card:#252320;--line:#37332d;--accent:#7bbf93;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:"Iowan Old Style","Palatino Linotype",Palatino,Charter,Georgia,serif;line-height:1.62;}
.topbar{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);
 padding:10px 18px;display:flex;justify-content:space-between;align-items:center;font-family:system-ui,sans-serif;}
.topbar .t{font-weight:600;font-size:14px;} .topbar .t small{color:var(--soft);font-weight:400;}
.themes button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--card);color:var(--ink);
 padding:4px 10px;border-radius:14px;margin-left:6px;cursor:pointer;}
.themes button.on{background:var(--accent);color:#fff;border-color:var(--accent);}
.pagewrap{max-width:74rem;margin:30px auto;padding:0 18px;}
.meta{display:flex;justify-content:space-between;align-items:center;margin:0 2px 7px;
 font-family:system-ui,sans-serif;font-size:11.5px;color:var(--soft);}
.meta b{color:var(--ink);}
.toggle{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:4px 16px;border-radius:13px;cursor:pointer;}
.toggle.on{background:var(--accent);color:#fff;border-color:var(--accent);}
.body{background:var(--card);border:1px solid var(--line);border-radius:10px;
 box-shadow:0 1px 5px rgba(0,0,0,.06);display:grid;grid-template-columns:1fr;overflow:hidden;}
.page.compare .body{grid-template-columns:1fr 1fr;}
.clean{padding:32px 56px 40px;max-width:var(--maxw);margin:0 auto;text-align:justify;hyphens:auto;-webkit-hyphens:auto;
 font-size:18px;display:flex;flex-direction:column;min-height:72vh;}
.folio-mark{color:var(--soft);font-size:.98em;font-variant-numeric:oldstyle-nums;letter-spacing:.03em;margin-bottom:1.6em;}
.folio-mark.fl{text-align:left;} .folio-mark.fr{text-align:right;}
.folio-bottom{margin-top:auto;padding-top:2em;text-align:center;color:var(--soft);font-size:.98em;font-variant-numeric:oldstyle-nums;}
.page.compare .clean{margin:0;max-width:none;}
.clean .blk{margin:0 0 1.05em;} .clean .blk p{margin:0 0 1.05em;}
.clean b{font-weight:700;} .clean i{font-style:italic;}
.clean .hd{font-size:1.12em;text-align:center;font-weight:600;margin:0 0 .9em;line-height:1.3;letter-spacing:.02em;text-wrap:balance;}
.clean .cap{text-align:center;color:var(--soft);font-size:.92em;font-style:italic;margin:.4em 0 0;}
.clean .credit{text-align:center;color:var(--soft);font-size:.8em;margin:.5em 0 0;}
.clean .fn{font-size:.84em;color:var(--soft);border-top:1px solid var(--line);margin-top:1.6em;padding-top:.6em;}
.clean .fn p{margin:.2em 0;}
.clean [data-bbox]{cursor:pointer;border-radius:3px;transition:background .1s;}
.page.compare .clean [data-bbox]:hover{background:color-mix(in srgb,var(--accent) 10%,transparent);}
.clean [data-bbox].sel{background:color-mix(in srgb,var(--accent) 18%,transparent);}
.plate{margin:0 0 1em;text-align:center;} .plate img{max-width:80%;height:auto;border:1px solid var(--line);background:#fff;}
.notext{margin:auto;padding:60px 20px;text-align:center;color:var(--soft);font-style:italic;font-size:17px;}
.scan{display:none;background:#cfc8ba;padding:14px;border-left:1px solid var(--line);max-height:90vh;overflow:auto;}
.page.compare .scan{display:block;}
.scanwrap{position:relative;} .scanwrap img{width:100%;display:block;border:1px solid #999;background:#fff;}
.hl{position:absolute;background:rgba(255,210,0,.30);outline:2px solid rgba(230,160,0,.9);border-radius:2px;display:none;pointer-events:none;transition:all .12s;}
.navbtn{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:4px 12px;border-radius:14px;cursor:pointer;}
.drawer{position:fixed;top:0;left:0;height:100vh;width:340px;max-width:85vw;background:var(--card);border-right:1px solid var(--line);box-shadow:2px 0 18px rgba(0,0,0,.18);transform:translateX(-100%);transition:transform .22s;z-index:20;display:flex;flex-direction:column;}
.drawer.open{transform:none;}
.drawer h3{font-family:system-ui,sans-serif;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--soft);margin:0;padding:16px 18px 10px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;}
.drawer h3 .close{font:inherit;border:none;background:none;color:var(--soft);font-size:20px;cursor:pointer;line-height:1;}
.jump{display:flex;gap:6px;padding:10px 18px;border-bottom:1px solid var(--line);font-family:system-ui,sans-serif;}
.jump input{flex:1;min-width:0;font:inherit;font-size:13px;padding:5px 8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);}
.jump button{font:inherit;font-size:13px;border:1px solid var(--accent);background:var(--accent);color:#fff;border-radius:8px;padding:5px 12px;cursor:pointer;}
.toc{list-style:none;margin:0;padding:6px 0;overflow:auto;flex:1;font-family:system-ui,sans-serif;}
.toc a{display:flex;justify-content:space-between;gap:10px;padding:6px 18px;text-decoration:none;color:var(--ink);font-size:13.5px;line-height:1.35;}
.toc a:hover{background:color-mix(in srgb,var(--accent) 12%,transparent);}
.toc .tf{color:var(--soft);font-variant-numeric:oldstyle-nums;flex:none;}
.scrim{position:fixed;inset:0;background:rgba(0,0,0,.28);opacity:0;pointer-events:none;transition:opacity .22s;z-index:15;}
.scrim.open{opacity:1;pointer-events:auto;}
"""
JS="""
const root=document.documentElement;
// --- Contents drawer + jump-to-page ---
const drawer=document.querySelector('.drawer'), scrim=document.querySelector('.scrim');
function setDrawer(o){drawer.classList.toggle('open',o);scrim.classList.toggle('open',o);}
document.querySelector('.navbtn').onclick=()=>setDrawer(!drawer.classList.contains('open'));
scrim.onclick=()=>setDrawer(false);
document.querySelector('.drawer .close').onclick=()=>setDrawer(false);
document.querySelectorAll('.toc a').forEach(a=>a.onclick=()=>setDrawer(false));
const jin=document.querySelector('.jump input');
function doJump(){const v=parseInt(jin.value,10); if(!isNaN(v)){location.hash='#page-'+(v+60); setDrawer(false);}}
document.querySelector('.jump button').onclick=doJump;
jin.addEventListener('keydown',e=>{if(e.key==='Enter')doJump();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')setDrawer(false);});
document.querySelectorAll('.themes button').forEach(b=>b.onclick=()=>{
  root.setAttribute('data-theme',b.dataset.theme);
  document.querySelectorAll('.themes button').forEach(x=>x.classList.toggle('on',x===b));});
document.querySelectorAll('.pagewrap').forEach(wrap=>{
  const pg=wrap.querySelector('.page'), btn=wrap.querySelector('.toggle');
  const img=pg.querySelector('.scanwrap img'), hl=pg.querySelector('.hl'), W=+pg.dataset.w;
  let sel=null;
  function clear(){ if(sel){sel.classList.remove('sel'); sel=null;} hl.style.display='none'; }
  function place(el){
    const [x0,y0,x1,y1]=el.dataset.bbox.split(',').map(Number), sc=img.clientWidth/W;
    hl.style.display='block';hl.style.left=(x0*sc)+'px';hl.style.top=(y0*sc)+'px';
    hl.style.width=((x1-x0)*sc)+'px';hl.style.height=((y1-y0)*sc)+'px';
    hl.scrollIntoView({block:'center',behavior:'smooth'});
  }
  btn.onclick=()=>{ const on=pg.classList.toggle('compare'); btn.classList.toggle('on',on); if(!on) clear(); };
  pg.querySelectorAll('.clean [data-bbox]').forEach(el=>el.onclick=(e)=>{
    e.stopPropagation();
    if(sel===el){ clear(); return; }                 // click again = deselect
    if(!pg.classList.contains('compare')){pg.classList.add('compare');btn.classList.add('on');}
    if(sel) sel.classList.remove('sel');
    sel=el; el.classList.add('sel');
    // scan may be lazy-loading; recompute once it has width
    if(img.clientWidth) place(el); else img.addEventListener('load',()=>{ if(sel===el) place(el); },{once:true});
  });
  pg.querySelector('.clean').addEventListener('click', clear);  // click empty space = clear
  pg.querySelector('.scanwrap').addEventListener('click', clear); // click scan = clear
});
"""
toc_html="".join(
    f'<li><a href="#page-{p}"><span class="tt">{_html.escape(t)}</span><span class="tf">{f}</span></a></li>'
    for p,f,t in toc)
drawer=f"""<div class="scrim"></div>
<aside class="drawer">
  <h3>Contents <button class="close" title="Close">&times;</button></h3>
  <div class="jump"><input type="number" min="1" max="352" placeholder="Go to printed page #"><button>Go</button></div>
  <ul class="toc">{toc_html}</ul>
</aside>"""

doc=f"""<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hindu Holidays and Ceremonials — B. A. Gupte</title><style>{CSS}</style></head><body>
<div class="topbar"><button class="navbtn">&#9776; Contents</button>
 <div class="t">Hindu Holidays and Ceremonials &nbsp;<small>B. A. Gupte &middot; 1919 &middot; 412 pp</small></div>
 <div class="themes"><button class="on" data-theme="light">Light</button><button data-theme="sepia">Sepia</button><button data-theme="dark">Dark</button></div></div>
{drawer}
{''.join(sections)}
<script>{JS}</script></body></html>"""
OUT = ROOT / "Hindu Holidays and Ceremonials - B. A. Gupte.html"
OUT.write_text(doc, encoding="utf-8")
print(f"wrote {OUT}  ({len(doc)/1048576:.1f} MB of HTML, {len(toc)} contents entries)")
