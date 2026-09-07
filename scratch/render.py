"""Render a page of a held PDF to PNG so a session can read it by eye.

    python scratch/render.py Palmer2025 1 200            whole page
    python scratch/render.py Palmer2025 1 300 0,0.5,1,1  bottom half (x0,y0,x1,y1 as fractions)

Writes to the scratchpad and prints the path.
"""
import os
import sys

import pymupdf

OUT = os.environ.get("RENDER_OUT", "/tmp/claude-0/-home-user/"
                     "317155fe-4b2c-55c7-b5b5-9b2bea2f6a25/scratchpad/pages")


def main():
    stem, page, dpi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    box = sys.argv[4] if len(sys.argv) > 4 else None
    path = os.path.join("data", "pdfs", stem + ".pdf")
    doc = pymupdf.open(path)
    p = doc[page - 1]
    clip = None
    if box:
        x0, y0, x1, y1 = [float(v) for v in box.split(",")]
        r = p.rect
        clip = pymupdf.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height,
                            r.x0 + x1 * r.width, r.y0 + y1 * r.height)
    pix = p.get_pixmap(dpi=dpi, clip=clip)
    os.makedirs(OUT, exist_ok=True)
    name = f"{stem}_p{page}_{dpi}" + (f"_{box.replace(',', '-')}" if box else "")
    out = os.path.join(OUT, name + ".png")
    pix.save(out)
    print(out, f"{pix.width}x{pix.height}", f"pages={doc.page_count}",
          f"rot={p.rotation}")


main()
