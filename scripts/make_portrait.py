#!/usr/bin/env python3
"""Render an image as profile/portrait.svg, an ASCII portrait that types itself out.

Run it by hand when the source image changes. The scheduled workflow does not run it.

    pip install pillow numpy
    python scripts/make_portrait.py source.jpg --crop 40,0,440,400
    python scripts/make_portrait.py source.jpg --preview     # print the grid too

Bright pixels become dense characters by default. That suits a subject on a dark
background. For a subject on a light background, pass --dark-is-dense.

A transparent PNG cutout works best. Pixels outside the cutout stay blank.
Best source: a sharp headshot of 1200 px or more, lit from one side, cropped
from chin to just above the hair.

The grid assumes a monospace advance of 0.6 em. The SVG embeds a JetBrains Mono
subset (scripts/fonts/mono-portrait.woff2) so every viewer gets that width.
GitHub strips scripts from READMEs, so the typing effect uses SMIL.
"""
import argparse
import base64
import os
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT_FILE = os.path.join(HERE, "fonts", "mono-portrait.woff2")

RAMP = " .,:;-=+*ox%#@"   # sparse to dense; the leading space is blank
COLS = 90
ROW_RATIO = 0.48          # a monospace cell is about twice as tall as wide
FONT_SIZE = 12.9
CHAR_W = FONT_SIZE * 0.6
LINE_H = 15
PAD = 14
ROW_STEP = 0.07           # seconds between rows starting to type
ROW_TIME = 0.12           # seconds for one row to type
FILL_DARK = "#C4B5FD"     # violet-300 on GitHub dark
FILL_LIGHT = "#6D28D9"    # violet-700 on GitHub light


def load(path, crop, dark_is_dense, contrast, curve, blur, floor=0.0):
    src = Image.open(path)
    if crop:
        src = src.crop(crop)
    matte = None
    if src.mode in ("RGBA", "LA") or "transparency" in src.info:
        # A cutout: put it on white so the backdrop maps to blank cells.
        src = src.convert("RGBA")
        matte = np.asarray(src.split()[-1])
        white = Image.new("RGBA", src.size, (255, 255, 255, 255))
        src = Image.alpha_composite(white, src)
    img = src.convert("L")
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    img = ImageOps.autocontrast(img, cutoff=1)
    eq = ImageOps.equalize(img)
    img = Image.blend(img, eq, contrast)
    a = np.asarray(img, dtype=np.float64) / 255.0
    if dark_is_dense:
        a = 1.0 - a
    if floor:
        a = np.clip((a - floor) / (1.0 - floor), 0.0, 1.0)   # treat the backdrop as blank
    a = a ** curve            # >1 pushes mid tones toward blank, keeps highlights
    if matte is not None:
        a[matte < 20] = 0.0   # outside the cutout stays blank
    return a


def to_grid(a, cols):
    h, w = a.shape
    rows = max(1, int(round(cols * (h / w) * ROW_RATIO)))
    img = Image.fromarray((a * 255).astype("uint8")).resize((cols, rows), Image.LANCZOS)
    v = np.asarray(img, dtype=np.float64) / 255.0
    idx = np.clip((v * len(RAMP)).astype(int), 0, len(RAMP) - 1)
    lines = ["".join(RAMP[i] for i in row).rstrip() for row in idx]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def font_rule():
    if not os.path.exists(FONT_FILE):
        return ""
    with open(FONT_FILE, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return ("@font-face{font-family:PMono;font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")


def to_svg(lines, cols):
    width = round(cols * CHAR_W + PAD * 2)
    height = len(lines) * LINE_H + PAD * 2
    family = "PMono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="ASCII portrait">',
        f"<style>{font_rule()}"
        f".t{{fill:{FILL_LIGHT};font-family:{family};font-size:{FONT_SIZE}px;white-space:pre}}"
        f".k{{fill:{FILL_LIGHT}}}"
        f"@media (prefers-color-scheme:dark){{.t,.k{{fill:{FILL_DARK}}}}}</style>",
    ]
    # Each row rests fully typed. Its animations start at 0s and hold the empty
    # state until the row's turn, so a viewer that skips SMIL still sees the
    # whole portrait.
    for i, line in enumerate(lines):
        y = PAD + i * LINE_H
        start = i * ROW_STEP
        dur = start + ROW_TIME
        k = start / dur
        w = max(len(line), 1) * CHAR_W
        text = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        out.append(
            f'<clipPath id="r{i}"><rect x="{PAD}" y="{y}" width="{w:.1f}" height="{LINE_H}">'
            f'<animate attributeName="width" values="0;0;{w:.1f}" keyTimes="0;{k:.3f};1" '
            f'dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>'
            f'<text class="t" x="{PAD}" y="{y + 11.2:.1f}" xml:space="preserve" '
            f'clip-path="url(#r{i})">{text}</text>'
            f'<rect class="k" x="{PAD + w:.1f}" y="{y + 1.5}" width="6" height="12" opacity="0">'
            f'<animate attributeName="x" values="{PAD};{PAD};{PAD + w:.1f}" keyTimes="0;{k:.3f};1" '
            f'dur="{dur:.2f}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;0.85;0" keyTimes="0;{k:.3f};1" '
            f'calcMode="discrete" dur="{dur:.2f}s" fill="freeze"/></rect>'
        )
    out.append("</svg>")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser(description="Render an image as an animated ASCII portrait SVG.")
    ap.add_argument("image")
    ap.add_argument("out", nargs="?", default=os.path.join(ROOT, "profile", "portrait.svg"))
    ap.add_argument("--crop", help="left,top,right,bottom in source pixels")
    ap.add_argument("--cols", type=int, default=COLS)
    ap.add_argument("--dark-is-dense", action="store_true",
                    help="map dark pixels to dense characters (subject on a light background)")
    ap.add_argument("--contrast", type=float, default=0.5, help="0 to 1, blend toward histogram equalization")
    ap.add_argument("--curve", type=float, default=1.3, help="tone curve exponent")
    ap.add_argument("--blur", type=float, default=0.6, help="pre-blur radius in source pixels")
    ap.add_argument("--floor", type=float, default=0.0,
                    help="0 to 1, tones below this become blank (drops a dim backdrop)")
    ap.add_argument("--preview", action="store_true", help="print the grid to the terminal")
    args = ap.parse_args()

    crop = None
    if args.crop:
        crop = tuple(int(v) for v in args.crop.split(","))
        if len(crop) != 4:
            sys.exit("--crop takes four numbers: left,top,right,bottom")

    lines = to_grid(load(args.image, crop, args.dark_is_dense, args.contrast, args.curve, args.blur, args.floor), args.cols)
    if args.preview:
        print("\n".join(lines))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(to_svg(lines, args.cols))
    print(f"wrote {args.out}: {len(lines)} rows x {args.cols} cols")


if __name__ == "__main__":
    main()
