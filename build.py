#!/usr/bin/env python3
"""Genera il PDF del Catalogo Circolo del Re a partire da libri.yaml."""

import base64
import html
import io
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import qrcode
import qrcode.image.svg
import yaml

ROOT = Path(__file__).resolve().parent
COVERS = ROOT / "covers"
BUILD = ROOT / "build"
OUTPUT = ROOT / "catalogo-circolo-del-re.pdf"
AMAZON = "https://www.amazon.it/dp/{asin}"
COVER_URL = "https://images-na.ssl-images-amazon.com/images/P/{asin}.01.LZZZZZZZ.jpg"
UA = {"User-Agent": "Mozilla/5.0"}


def esc(s):
    return html.escape(str(s or ""))


def asin_from(book):
    if book.get("asin"):
        return str(book["asin"]).strip()
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", book.get("link", ""))
    return m.group(1) if m else None


def amazon_link(book, asin):
    if asin:
        return AMAZON.format(asin=asin)
    return book.get("link", "")


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def cover_data_uri(book, asin):
    src = book.get("copertina")
    data = None
    if src and re.match(r"https?://", src):
        data = fetch(src)
    elif src:
        data = (ROOT / src).read_bytes()
    if not data and asin:
        cached = COVERS / f"{asin}.jpg"
        if not cached.exists():
            try:
                blob = fetch(COVER_URL.format(asin=asin))
                # Amazon restituisce un GIF 1x1 (43 byte) se la copertina non esiste
                if len(blob) > 1000:
                    COVERS.mkdir(exist_ok=True)
                    cached.write_bytes(blob)
            except Exception as e:  # noqa: BLE001
                print(f"  ! copertina non scaricata per {asin}: {e}", file=sys.stderr)
        if cached.exists():
            data = cached.read_bytes()
    if not data:
        return None
    mime = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=0,
                      error_correction=qrcode.constants.ERROR_CORRECT_L)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode()
    return re.sub(r"<\?xml[^>]*\?>", "", svg)


def price(p):
    if p in (None, ""):
        return "—"
    return "€ " + f"{float(p):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def card(book):
    asin = asin_from(book)
    link = amazon_link(book, asin)
    cover = cover_data_uri(book, asin)
    cover_html = (f'<img src="{cover}" alt="">' if cover
                  else '<div class="nocover">♚</div>')
    note = f'<div class="note">{esc(book.get("note"))}</div>' if book.get("note") else ""
    code = f'<span class="asin">ASIN {esc(asin)}</span>' if asin else ""
    best = book.get("bestseller")
    badge = ('<div class="badge">★ Best seller · si consiglia di ordinare almeno 5 copie</div>'
             if best else "")
    return f"""
    <a class="card{' best' if best else ''}" href="{esc(link)}">
      {badge}
      <div class="cover">{cover_html}</div>
      <div class="info">
        <div class="title">{esc(book["titolo"])}</div>
        <div class="author">{esc(book["autore"])}</div>
        {note}
        <div class="bottom">
          <div>
            <div class="price">{price(book.get("prezzo"))}</div>
            <div class="buy">Su Amazon ›</div>
            {code}
          </div>
          <div class="qr">{qr_svg(link) if link else ""}</div>
        </div>
      </div>
    </a>"""


def render(cfg):
    groups = {}
    for b in cfg["libri"]:
        groups.setdefault(b.get("categoria") or "", []).append(b)

    sections = []
    for name, books in groups.items():
        print(f"- {name or '(senza categoria)'}: {len(books)} libri")
        head = f'<h2>{esc(name)}<span>{len(books)}</span></h2>' if name else ""
        sections.append(f'<section>{head}<div class="grid">{"".join(card(b) for b in books)}</div></section>')

    logo = base64.b64encode((ROOT / "assets" / "logo.png").read_bytes()).decode()
    css = (ROOT / "assets" / "catalogo.css").read_text()
    total = len(cfg["libri"])
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<title>Catalogo Circolo del Re</title>
<style>{css}</style></head>
<body>
  <header>
    <img class="logo" src="data:image/png;base64,{logo}" alt="Circolo del Re">
    <div class="htext">
      <div class="kicker">A.S.D. Circolo del Re · Castelvetrano Scacchi</div>
      <h1>Catalogo Circolo del Re</h1>
      <div class="sub">Libri di scacchi selezionati per librerie · {esc(cfg.get("edizione", ""))} · {total} titoli</div>
    </div>
  </header>
  <div class="howto">Clicca su una scheda o inquadra il QR code per aprire il libro su Amazon.
    Prezzi al pubblico su Amazon.it{" aggiornati al " + esc(cfg["aggiornamento_prezzi"]) if cfg.get("aggiornamento_prezzi") else ""},
    soggetti a variazione: fa fede il listino Amazon riservato alla libreria.</div>
  {"".join(sections)}
  <footer>circolodelre.it · 320 046 6987</footer>
</body></html>"""


def find_chrome():
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(name):
            return name
    sys.exit("Serve Google Chrome o Chromium per generare il PDF.")


def main():
    cfg = yaml.safe_load((ROOT / "libri.yaml").read_text())
    BUILD.mkdir(exist_ok=True)
    page = BUILD / "catalogo.html"
    page.write_text(render(cfg))
    subprocess.run([find_chrome(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={OUTPUT}", page.as_uri()],
                   check=True, stderr=subprocess.DEVNULL)
    print(f"PDF generato: {OUTPUT}")


if __name__ == "__main__":
    main()
