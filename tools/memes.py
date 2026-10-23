"""Перерисовка китайских подписей на мемах.

python tools/memes.py --config tools/memes.json --src <memes> --out <dir> [--only a,b]
Операции элемента (в порядке списка ops):
  fill   {"rect":[x1,y1,x2,y2], "color":"#ffffff"}
  bubble {"rect":[...], "radius":18, "fill":"#fff", "border":"#2a3550", "width":3,
          "tail":"left|right|none", "tail_at":0.7}
  bar    {"rect":[...], "color":"#000000", "alpha":170, "radius":6}
  text   {"rect":[...], "text":"...", "size":40, "color":"#fff",
          "stroke":0, "stroke_color":"#000", "align":"center|left"}
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = Path(
    r"C:\Users\areko\.dsh\profiles\desktop\node_modules\dsh-pet\assets\fonts\ShangshouSoftCandy.ttf"
)


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        probe = (cur + " " + word).strip()
        if draw.textlength(probe, font=font) <= max_w or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_text(img, spec):
    x1, y1, x2, y2 = spec["rect"]
    max_w, max_h = x2 - x1, y2 - y1
    size = spec.get("size", 40)
    while True:
        font = ImageFont.truetype(str(FONT_PATH), size)
        d = ImageDraw.Draw(img)
        lines = wrap(d, spec["text"], font, max_w)
        line_h = int(size * 1.12)
        if size <= 8 or (len(lines) * line_h <= max_h and all(d.textlength(l, font=font) <= max_w for l in lines)):
            break
        size -= 1
    cy = y1 + (max_h - len(lines) * line_h) / 2
    for line in lines:
        d = ImageDraw.Draw(img)
        w = d.textlength(line, font=font)
        cx = x1 + (max_w - w) / 2 if spec.get("align", "center") == "center" else x1
        d.text(
            (cx, cy), line, font=font,
            fill=spec.get("color", "#ffffff"),
            stroke_width=spec.get("stroke", 0),
            stroke_fill=spec.get("stroke_color", "#000000"),
        )
        cy += line_h


def bubble(img, spec):
    x1, y1, x2, y2 = spec["rect"]
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        [x1, y1, x2, y2],
        radius=spec.get("radius", 18),
        fill=spec.get("fill", "#ffffff"),
        outline=spec.get("border"),
        width=spec.get("width", 0),
    )
    tail = spec.get("tail", "none")
    if tail in ("left", "right"):
        cy = y1 + (y2 - y1) * spec.get("tail_at", 0.72)
        w = spec.get("tail_w", 11)
        if tail == "left":
            d.polygon([(x1 + 3, cy), (x1 - w, cy + w), (x1 + 3, cy + w + 3)], fill=spec.get("fill", "#ffffff"),
                      outline=spec.get("border"))
        else:
            d.polygon([(x2 - 3, cy), (x2 + w, cy + w), (x2 - 3, cy + w + 3)], fill=spec.get("fill", "#ffffff"),
                      outline=spec.get("border"))


def bar(img, spec):
    x1, y1, x2, y2 = spec["rect"]
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    r, g, b = hex_rgb(spec.get("color", "#000000"))
    ImageDraw.Draw(overlay).rounded_rectangle(
        [x1, y1, x2, y2], radius=spec.get("radius", 6), fill=(r, g, b, spec.get("alpha", 170))
    )
    img.alpha_composite(overlay)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    done = 0
    for name, spec in cfg.items():
        if args.only and name not in args.only.split(","):
            continue
        path = src / f"{name}.png"
        if not path.exists():
            print(f"нет файла: {path}")
            continue
        canvas = Image.open(path).convert("RGBA")
        for op in spec.get("ops", []):
            kind = op["op"]
            if kind == "fill":
                ImageDraw.Draw(canvas).rectangle(op["rect"], fill=hex_rgb(op["color"]))
            elif kind == "bubble":
                bubble(canvas, op)
            elif kind == "bar":
                bar(canvas, op)
            elif kind == "text":
                draw_text(canvas, op)
        canvas.convert("RGB").save(out / path.name)
        done += 1
    print(f"готово: {done}")


if __name__ == "__main__":
    main()
