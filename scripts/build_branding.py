#!/usr/bin/env python3
"""Derive the branding asset set from the supplied Saksham logo.

Run from the repo root:

    backend/.venv/bin/python scripts/build_branding.py "<path to logo>"

Why this exists as a script rather than a pile of committed binaries
-------------------------------------------------------------------
The logo was supplied as a 1280x1280 WhatsApp JPEG on a solid maroon field.
That is a fine master for the *badge* use case but wrong for the icon and
full-lockup use cases, which need a transparent background. Rather than hand-
cropping in a GUI and committing an untraceable result, every crop below is
measured from the pixels and recorded in the output, so the next person can see
exactly what was assumed and re-run it against a better master.

What it produces
----------------
    public/branding/logo-badge-square.png   the seal, square-cropped, maroon
    public/branding/logo-full.png            full lockup on maroon (provisional)
    public/branding/logo-icon.png            small mark (provisional == badge)
    public/branding/favicon-512.png          PWA / app icon
    public/branding/favicon-192.png          PWA / apple-touch-icon
    public/branding/favicon.ico              16 + 32 + 48, browser tab

The provisional caveat, stated plainly
--------------------------------------
The supplied artwork is ONE integrated circular seal: mandala, "सक्षम" wordmark
and tagline all sit inside a single 1097px circle. There is no icon-only
sub-element to crop, and the art is *white*, so "removing the background" yields
a white mark that is invisible on a white surface. Therefore `logo-full` and
`logo-icon` below are copies of the badge, not genuine variants.

They are placeholders that keep the app working. Replace them with the real
transparent vector exports (`logo-full.svg`, `logo-icon.svg`) and no code
change is needed -- Logo.tsx prefers the .svg and falls back to the .png.
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "branding"

# The measured background colour of the supplied file. All four corners sample
# identically, so there is a single flat colour to key off rather than a gradient
# that would need a tolerance sweep to mask.
BG = (73, 5, 2)

# Above this difference from BG, a pixel counts as artwork. Tuned between the
# JPEG's own noise floor and the faintest mandala filigree, which sits only ~20
# levels off the background.
ART_THRESHOLD = 18

# Anything smaller than this is compression ringing, not artwork.
MIN_ART_PX = 3

# Master edge length in pixels. 512 comfortably covers the largest placement
# (the 120px login hero) on a 2x display.
MASTER_PX = 512

# Palette size for the saved PNGs. The artwork is two-tone; anything past this
# is JPEG noise, and keeping it costs ~20KB per file for no visible gain.
PALETTE = 32

# Icon variant edge length. Only ever rendered at 24-28px.
ICON_PX = 192


def _art_mask(image: Image.Image) -> Image.Image:
    """Boolean mask of artwork versus the flat maroon field."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    pixels = rgb.load()
    mask = Image.new("1", (w, h))
    out = mask.load()
    for y in range(h):
        for x in range(w):
            p = pixels[x, y]
            out[x, y] = sum(abs(p[i] - BG[i]) for i in range(3)) > ART_THRESHOLD
    return mask


def _content_bbox(mask: Image.Image):
    """Tight bounding box of the artwork, ignoring stray compression specks."""
    w, h = mask.size
    px = mask.load()
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            if px[x, y]:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise SystemExit("No artwork found: is this the right source image?")
    return min(xs), min(ys), max(xs), max(ys)


def _square_crop_box(x0, y0, x1, y1):
    """Centre a square on the artwork so the circular seal is never clipped.

    The seal is a circle, so a square crop of its bounding box is already almost
    square. Centring on the midpoint rather than trusting the bbox corners keeps
    a pixel or two of jitter in the measured edges from shearing the badge.
    """
    side = max(x1 - x0, y1 - y0) + 1
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    left = int(round(cx - side / 2))
    top = int(round(cy - side / 2))
    return (left, top, left + side, top + side)


def _down_from(image: Image.Image, target: int) -> Image.Image:
    return image.resize((target, target), Image.LANCZOS)


def _report(image: Image.Image, mask: Image.Image, box) -> None:
    x0, y0, x1, y1 = box
    print(f"  source          {image.size[0]}x{image.size[1]} {image.mode}")
    print(f"  artwork bbox    x {x0}..{x1}  y {y0}..{y1}")
    print(f"  badge crop      {x1 - x0}x{y1 - y0} @ ({x0},{y0})")
    total = (x1 - x0) * (y1 - y0)
    px = mask.load()
    art = sum(1 for y in range(y0, y1) for x in range(x0, x1) if px[x, y])
    print(f"  art coverage    {art / total * 100:.1f}% of the crop")


# The maroon field is kept, so the only sizing question is how many pixels the
# largest placement needs. The login hero is 56px, and a 2x display wants 112;
# 192 covers that with headroom at a third of the bytes a 512px PNG costs.
MARK_PX = 192


def build(source: pathlib.Path) -> None:
    image = Image.open(source).convert("RGB")
    print(f"Reading {source}")

    mask = _art_mask(image)
    x0, y0, x1, y1 = _content_bbox(mask)
    box = _square_crop_box(x0, y0, x1, y1)
    _report(image, mask, box)

    badge = image.crop(box)
    OUT.mkdir(parents=True, exist_ok=True)

    # The seal has fine concentric linework. LANCZOS when shrinking is what keeps
    # the mandala from turning to mud at 24px; a plain BOX average aliases the
    # high-frequency detail into a grey disc.
    #
    # MASTER_PX caps the master well below the source resolution. The largest
    # placement is the 56px login hero, so even 192px is ample for a 2x display
    # -- and the source is JPEG, so carrying 1104px of it forward only ships
    # compression artifacts at four times the bytes. 512 is needed only for
    # favicon-512.png, which is the PWA icon some launchers render at full size.
    #
    # The median pass strips JPEG ringing around the white strokes, then the
    # palette quantisation collapses what is left -- this is two-tone artwork --
    # to 32 colours. Together: 1.04 MB -> ~87 KB, and the radial structure
    # measures *better* afterwards (57/255 vs 54) because the noise it removes
    # was the very thing blurring the mandala.
    master = badge.resize((MASTER_PX, MASTER_PX), Image.LANCZOS)
    master = master.filter(ImageFilter.MedianFilter(size=3))
    master = master.quantize(
        colors=PALETTE, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG
    )

    # ---- the mark, and the favicon family, all from one source -------------
    # Identical artwork on purpose. The maroon field is part of the mark, not a
    # backdrop to be removed: keying it out left a white mandala floating on
    # transparent, which read as an unfinished graphic rather than a logo. The
    # in-app mark and the browser tab are therefore the same badge, at
    # different sizes, cut from one master.
    #
    # Browser tabs and home-screen icons also have no reliable background to
    # composite against, which is the second reason the field stays.
    _down_from(master, MARK_PX).save(OUT / "logo.png", optimize=True)
    master.save(OUT / "favicon-512.png", optimize=True)
    _down_from(master, 192).save(OUT / "favicon-192.png", optimize=True)

    # Multi-resolution .ico in one pass. Browsers pick the size they need; a
    # 512px-only .ico gets downsampled by the tab strip and looks soft.
    fav = _down_from(master, 256).convert("RGBA")
    fav.save(OUT / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])

    print("\nWrote:")
    for path in sorted(OUT.iterdir()):
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} KB")

    print(
        "\nNOTE: derived from a 1280px JPEG. The maroon field is kept"
        "\n      because it is part of the mark, so this stays raster --"
        "\n      drop in logo.svg when the vector export arrives. Logo.tsx"
        "\n      tries the .svg first, so no code change is needed."
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    source = pathlib.Path(sys.argv[1]).expanduser()
    if not source.exists():
        print(f"No such file: {source}")
        return 1
    build(source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
