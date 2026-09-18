#!/usr/bin/env python3
"""Compose a print-ready cover page (single-page PDF) from a cover artwork image.

The artwork is fitted into the target page (contain + edge-colour bars), optional
text lines (author / disclaimer) are drawn centred over blank bands of the
artwork, and the result is written as a single-page PDF with an exact MediaBox
and an embedded JPEG. Run setmeta.js after merging to (re)set PDF /Info.

Usage:
  python build_cover.py --cover cover.png --outdir build --probe
  python build_cover.py --cover cover.png --outdir build \
      --author "作者：DefTruth" --disclaimer "声明：..." \
      --author-y 0.907 --disclaimer-y 0.9552

-y positions are vertical centres as fractions of the artwork height; --probe
lists blank bands. Defaults suit the 2174x2990 artwork of lihang-notes on A4.

Requires pillow + numpy.
"""
import argparse
import io
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = (
  "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
  "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
  "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
)


def load_cjk_font(size, path=None):
  """Load a CJK-capable truetype font, preferring the Simplified Chinese face."""
  for p in (path,) if path else FONT_CANDIDATES:
    if not p or not os.path.exists(p):
      continue
    first = None
    for idx in range(16):
      try:
        font = ImageFont.truetype(p, size, index=idx)
      except OSError:
        break
      if first is None:
        first = font
      if "SC" in " ".join(font.getname()):
        return font
    if first is not None:
      return first
  raise SystemExit("no CJK font found; pass --font")


def probe(image):
  """Report vertical blank bands of the artwork, for placing overlay text."""
  w, h = image.size
  lum = np.asarray(image.convert("RGB")).astype(np.float32).mean(axis=2)
  band = lum[:, int(w * 0.30):int(w * 0.70)]
  bright = band > 120
  print(f"artwork {w}x{h}; fractions are y/height")
  print("  bucket   y-range        mean   bright%")
  for i in range(25):
    y0, y1 = h * i // 25, h * (i + 1) // 25
    print(f"  {i*4:3d}-{(i+1)*4:3d}%  [{y0:5d}:{y1:5d}]  {band[y0:y1].mean():6.1f}  "
          f"{bright[y0:y1].mean()*100:6.2f}")
  print("blank bands (no bright pixel in the centre 40% column band):")
  run = None
  for y in range(h):
    if not bright[y].any():
      if run is None:
        run = y
    elif run is not None:
      if y - run >= 24:
        print(f"  y[{run}:{y-1}]  frac {run/h:.4f}..{(y-1)/h:.4f}")
      run = None
  if run is not None and h - run >= 24:
    print(f"  y[{run}:{h-1}]  frac {run/h:.4f}..{(h-1)/h:.4f}")


def parse_hex(s):
  s = s.lstrip("#")
  return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def page_size(spec):
  try:
    w, h = spec.lower().split("x")
    return float(w), float(h)
  except ValueError:
    raise SystemExit(f"bad --page {spec!r}, expected WxH in points")


def compose(image, page_w, page_h, args):
  """Fit the artwork into the page canvas and draw the optional text lines."""
  w, h = image.size
  pxp = w / page_w
  canvas_w = w
  canvas_h = round(page_h * pxp)
  top_pad = (canvas_h - h) // 2
  bot_pad = canvas_h - h - top_pad

  arr = np.asarray(image).astype(np.float32)
  top_col = tuple(int(round(v)) for v in arr[:4].mean(axis=(0, 1)))
  bot_col = tuple(int(round(v)) for v in arr[-4:].mean(axis=(0, 1)))
  print(f"cover {w}x{h} -> canvas {canvas_w}x{canvas_h} "
        f"(pad {top_pad}/{bot_pad}px, {pxp:.4f} px/pt)")

  canvas = Image.new("RGB", (canvas_w, canvas_h))
  canvas.paste(Image.new("RGB", (canvas_w, top_pad), top_col), (0, 0))
  canvas.paste(image, (0, top_pad))
  canvas.paste(Image.new("RGB", (canvas_w, bot_pad), bot_col), (0, top_pad + h))

  lines = []
  if args.author:
    lines.append((args.author, args.author_y, args.author_pt,
                  parse_hex(args.author_color)))
  if args.disclaimer:
    lines.append((args.disclaimer, args.disclaimer_y, args.disclaimer_pt,
                  parse_hex(args.disclaimer_color)))
  draw = ImageDraw.Draw(canvas)
  for text, frac, size_pt, color in lines:
    font = load_cjk_font(round(size_pt * pxp), args.font)
    cy = top_pad + round(frac * h)
    draw.text((canvas_w // 2, cy), text, font=font, fill=color, anchor="mm")
    print(f"text {text[:24]!r} centred at y={cy} ({frac} of artwork)")
  return canvas


def build_pdf(canvas, page_w, page_h, quality):
  """Assemble a minimal single-page PDF with the canvas embedded as JPEG."""
  buf = io.BytesIO()
  canvas.save(buf, "JPEG", quality=quality, subsampling=0, optimize=True)
  jb = buf.getvalue()
  w, h = canvas.size
  objs = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w:g} {page_h:g}] "
    f"/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>".encode(),
    f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
    f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
    f"/Length {len(jb)} >>".encode() + b"\nstream\n" + jb + b"\nendstream",
  ]
  content = f"q {page_w:g} 0 0 {page_h:g} 0 0 cm /Im0 Do Q".encode()
  objs.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
              + content + b"\nendstream")

  out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
  offsets = []
  for i, o in enumerate(objs, start=1):
    offsets.append(len(out))
    out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
  xref_pos = len(out)
  out += f"xref\n0 {len(objs)+1}\n".encode() + b"0000000000 65535 f \n"
  for off in offsets:
    out += f"{off:010d} 00000 n \n".encode()
  out += (f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\n"
          f"startxref\n{xref_pos}\n%%EOF\n").encode()
  return bytes(out)


def main():
  ap = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument("--cover", required=True, help="cover artwork image (png/jpg)")
  ap.add_argument("--outdir", default=".", help="output directory (default: .)")
  ap.add_argument("--name", default="cover", help="output stem (default: cover)")
  ap.add_argument("--page", default="595.22x842", help="page size WxH in points (default: A4)")
  ap.add_argument("--author", help="author line text")
  ap.add_argument("--author-y", type=float, default=0.907, help="author centre as fraction of artwork height")
  ap.add_argument("--author-pt", type=float, default=16.0, help="author font size in points")
  ap.add_argument("--author-color", default="E8C791", help="author text colour RRGGBB")
  ap.add_argument("--disclaimer", help="disclaimer line text")
  ap.add_argument("--disclaimer-y", type=float, default=0.9552, help="disclaimer centre as fraction of artwork height")
  ap.add_argument("--disclaimer-pt", type=float, default=8.5, help="disclaimer font size in points")
  ap.add_argument("--disclaimer-color", default="9C8E76", help="disclaimer text colour RRGGBB")
  ap.add_argument("--font", help="CJK font file (auto-detected when omitted)")
  ap.add_argument("--quality", type=int, default=93, help="JPEG quality (default: 93)")
  ap.add_argument("--probe", action="store_true", help="print blank-band report and exit")
  args = ap.parse_args()

  image = Image.open(args.cover).convert("RGB")
  if args.probe:
    probe(image)
    return

  page_w, page_h = page_size(args.page)
  os.makedirs(args.outdir, exist_ok=True)
  canvas = compose(image, page_w, page_h, args)
  canvas.save(os.path.join(args.outdir, f"{args.name}_full.png"))
  canvas.resize((canvas.width // 3, canvas.height // 3), Image.LANCZOS).save(
    os.path.join(args.outdir, f"preview-{args.name}.png"))
  pdf = build_pdf(canvas, page_w, page_h, args.quality)
  path = os.path.join(args.outdir, f"{args.name}.pdf")
  with open(path, "wb") as f:
    f.write(pdf)
  print(f"{path}: {len(pdf)/1e6:.2f} MB")


if __name__ == "__main__":
  main()
