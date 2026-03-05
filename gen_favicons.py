#!/usr/bin/env python3
"""Generate all favicon/app-icon assets from logo.svg."""
import os, json
from pathlib import Path
import cairosvg
from PIL import Image
import io

STATIC = Path("app/static")
SVG_PATH = STATIC / "logo.svg"
svg_data = SVG_PATH.read_bytes()

def svg_to_png(size):
    png_bytes = cairosvg.svg2png(bytestring=svg_data, output_width=size, output_height=size)
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")

def save_png(img, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "PNG")
    print(f"  ✓  {path}  ({img.size[0]}x{img.size[1]})")

# ── PNG favicons ─────────────────────────────────────────────────────────────
for size in (16, 32, 48, 96, 180, 192, 512):
    img = svg_to_png(size)
    if size == 180:
        save_png(img, STATIC / "apple-touch-icon.png")
    elif size == 192:
        save_png(img, STATIC / "android-chrome-192x192.png")
    elif size == 512:
        save_png(img, STATIC / "android-chrome-512x512.png")
    else:
        save_png(img, STATIC / f"favicon-{size}x{size}.png")

# ── favicon.ico (16 + 32 + 48 embedded) ──────────────────────────────────────
ico_sizes = [svg_to_png(s).resize((s, s), Image.LANCZOS) for s in (16, 32, 48)]
ico_path = STATIC / "favicon.ico"
ico_sizes[0].save(
    str(ico_path),
    format="ICO",
    sizes=[(16,16),(32,32),(48,48)],
    append_images=ico_sizes[1:],
)
print(f"  ✓  {ico_path}  (16+32+48)")

# ── site.webmanifest ──────────────────────────────────────────────────────────
manifest = {
    "name": "Won Door Portal",
    "short_name": "Portal",
    "icons": [
        {"src": "/static/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
    ],
    "theme_color": "#091c2d",
    "background_color": "#091c2d",
    "display": "standalone",
}
manifest_path = STATIC / "site.webmanifest"
manifest_path.write_text(json.dumps(manifest, indent=2))
print(f"  ✓  {manifest_path}")

print("\nDone — all favicon assets generated.")
