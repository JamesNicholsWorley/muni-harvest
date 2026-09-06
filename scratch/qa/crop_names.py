"""Crop the line a disputed name sits on, out of the page, at reading size.

Opening the document is the rule, and for a one-word disagreement the document
is one line.  Rendering forty whole pages to check forty spellings is the
expensive way to obey it; this finds the word on the page, crops the line
around it and stitches the crops onto a sheet, so a run can read what the page
actually prints without paging through the documents one at a time.

The crop is of the RENDERED GLYPHS, which is the point: the text layer is what
is in dispute, so the answer cannot come from the text layer.

    python scratch/qa/crop_names.py sheet.png Ashland2025:JOSPEH ...
"""
import io, os, sys
import fitz
from PIL import Image, ImageDraw

DPI = 200
PAD_X, PAD_Y = 210, 12


def crop(stem, token):
    p = f"data/pdfs/{stem}.pdf"
    if not os.path.exists(p):
        return None
    d = fitz.open(p)
    for pno, page in enumerate(d):
        hits = page.search_for(token)
        if not hits:
            continue
        r = hits[0]
        box = fitz.Rect(max(0, r.x0 - PAD_X), max(0, r.y0 - PAD_Y),
                        min(page.rect.x1, r.x1 + PAD_X * 2),
                        min(page.rect.y1, r.y1 + PAD_Y))
        pix = page.get_pixmap(clip=box, dpi=DPI)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        d.close()
        return img, pno + 1
    d.close()
    return None


def main():
    out = sys.argv[1]
    jobs = [a.split(":", 1) for a in sys.argv[2:]]
    tiles = []
    for stem, token in jobs:
        got = crop(stem, token)
        if not got:
            print(f"  {stem}: '{token}' not found on any page")
            continue
        img, pno = got
        tiles.append((f"{stem} p{pno}", img))
    if not tiles:
        return
    W = max(400, max(t[1].width for t in tiles) + 260)
    H = sum(t[1].height + 14 for t in tiles) + 14
    sheet = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(sheet)
    y = 7
    for label, img in tiles:
        dr.text((6, y + img.height // 2 - 6), label, fill="black")
        sheet.paste(img, (250, y))
        dr.line([(0, y + img.height + 6), (W, y + img.height + 6)], fill="#bbb")
        y += img.height + 14
    sheet.save(out)
    print(f"{len(tiles)} crops -> {out}  ({W}x{H})")


if __name__ == "__main__":
    main()
