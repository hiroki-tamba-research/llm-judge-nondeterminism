"""Render NOTE.md -> NOTE.pdf.

Dependencies (build-time only, not part of the experiment):
    pip install markdown xhtml2pdf

Usage:
    python tools/render_pdf.py            # renders NOTE.md
    python tools/render_pdf.py README.md  # render a different markdown file
"""
import pathlib
import sys

import markdown
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import pisa

ROOT = pathlib.Path(__file__).resolve().parent.parent
src = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "NOTE.md")
out = src.with_suffix(".pdf")

# Register Arial directly with reportlab (xhtml2pdf's @font-face URL handling is
# unreliable for absolute Windows paths). This gives the document glyphs for the
# section sign, arrows, approx / greater-equal, and em-dash.
_FONTS = "C:/Windows/Fonts"
pdfmetrics.registerFont(TTFont("ArialU", f"{_FONTS}/arial.ttf"))
pdfmetrics.registerFont(TTFont("ArialU-Bold", f"{_FONTS}/arialbd.ttf"))
pdfmetrics.registerFont(TTFont("ArialU-Italic", f"{_FONTS}/ariali.ttf"))
registerFontFamily(
    "ArialU", normal="ArialU", bold="ArialU-Bold",
    italic="ArialU-Italic", boldItalic="ArialU-Bold",
)

html_body = markdown.markdown(
    src.read_text(encoding="utf-8"),
    extensions=["tables", "footnotes", "fenced_code", "sane_lists", "toc"],
)

# Arial is registered explicitly so non-ASCII glyphs (section sign, arrows,
# approx/greater-equal, em-dash) render instead of falling back to tofu boxes.
CSS = """
@page { size: A4; margin: 2cm 2cm 2.2cm 2cm; }
body { font-family: "ArialU"; font-size: 10.5pt; line-height: 1.42; color: #111; }
h1 { font-size: 17pt; margin-bottom: 4pt; }
h2 { font-size: 13pt; margin-top: 16pt; border-bottom: 1px solid #ccc; padding-bottom: 2pt; }
h3 { font-size: 11pt; }
p, li { text-align: justify; }
table { border-collapse: collapse; margin: 8pt 0; }
th, td { border: 1px solid #999; padding: 3pt 6pt; font-size: 9.5pt; }
th { background: #f0f0f0; }
code { font-family: "Courier"; background: #f4f4f4; font-size: 9.5pt; }
pre { background: #f4f4f4; padding: 6pt; }
pre code { background: transparent; }
a { color: #1a5fb4; text-decoration: none; }
hr { border: none; border-top: 1px solid #ccc; margin: 12pt 0; }
.footnote { font-size: 9pt; color: #333; border-top: 1px solid #ccc; margin-top: 16pt; }
.footnote ol { padding-left: 14pt; }
"""

html = (
    "<html><head><meta charset='utf-8'><style>"
    + CSS
    + "</style></head><body>"
    + html_body
    + "</body></html>"
)

with open(out, "wb") as fh:
    result = pisa.CreatePDF(html, dest=fh, encoding="utf-8")

if result.err:
    print(f"PDF generation reported {result.err} error(s)")
    sys.exit(1)
print(f"wrote {out}")
