"""Tile rendered PNGs into 2-column contact sheets for review (display only)."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw
PNG = Path(__file__).resolve().parents[1] / "png"
samples = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
paths = [Path(s["png"]) for s in samples]
per = 4
for n in range(0, len(paths), per):
    chunk = paths[n:n + per]
    ims = [Image.open(p).convert("RGB") for p in chunk]
    w = max(i.width for i in ims); h = max(i.height for i in ims)
    sheet = Image.new("RGB", (w * 2, h * ((len(ims) + 1) // 2)), "white")
    for k, im in enumerate(ims):
        sheet.paste(im, ((k % 2) * w, (k // 2) * h))
    out = PNG / f"MONTAGE_{n // per + 1:02d}.png"
    sheet.save(out)
    print(out.name, [p.name for p in chunk])
