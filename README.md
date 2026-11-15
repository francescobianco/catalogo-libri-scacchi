# Catalogo Circolo del Re

Catalogo PDF di libri di scacchi per le librerie: copertina, prezzo, link e QR code verso Amazon.it.

## Uso

1. Modifica `libri.yaml` (titolo, autore, ASIN, prezzo, eventuale `bestseller: true`).
2. Genera il PDF:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # solo la prima volta
.venv/bin/python build.py
```

Output: `catalogo-circolo-del-re.pdf`. Le copertine sono in `covers/<ASIN>.jpg`
(se mancano vengono scaricate da Amazon). Serve Google Chrome o Chromium.
