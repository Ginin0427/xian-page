#!/usr/bin/env python3
"""扫描 assets/，按文件名顺序生成 index.html 里的 <section class="slide">。

用法：
    python3 tools/build.py            首屏预加载，其余懒加载
    python3 tools/build.py --eager    全部预加载
"""

import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
TARGET = os.path.join(ROOT, "index.html")
HOTSPOTS = os.path.join(ROOT, "hotspots.json")
DESIGN_WIDTH = 1920
EXTS = (".webp", ".avif", ".png", ".jpg", ".jpeg", ".svg")
BEGIN = "<!-- BUILD:SLIDES -->"
END = "<!-- /BUILD:SLIDES -->"

WARN_SLIDE_BYTES = 1500000
WARN_TOTAL_BYTES = 15000000
WARN_HEIGHT = 6000


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def jpeg_size(data):
    if data[:2] != b"\xff\xd8":
        return None
    i, n = 2, len(data)
    while i < n - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xDA:
            break
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        i += 2 + length
    return None


def webp_size(data):
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    kind = data[12:16]
    if kind == b"VP8X":
        return (
            int.from_bytes(data[24:27], "little") + 1,
            int.from_bytes(data[27:30], "little") + 1,
        )
    if kind == b"VP8 ":
        return (
            int.from_bytes(data[26:28], "little") & 0x3FFF,
            int.from_bytes(data[28:30], "little") & 0x3FFF,
        )
    if kind == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def svg_size(text):
    box = re.search(r'viewBox="([-\d.\s,]+)"', text)
    if box:
        parts = [float(v) for v in re.split(r"[\s,]+", box.group(1).strip()) if v]
        if len(parts) == 4:
            return int(parts[2]), int(parts[3])
    width = re.search(r'width="([\d.]+)', text)
    height = re.search(r'height="([\d.]+)', text)
    if width and height:
        return int(float(width.group(1))), int(float(height.group(1)))
    return None


def image_info(path):
    with open(path, "rb") as handle:
        head = handle.read(4096)
    ext = os.path.splitext(path)[1].lower()
    by_ext = {
        ".png": png_size,
        ".jpg": jpeg_size,
        ".jpeg": jpeg_size,
        ".webp": webp_size,
        ".svg": lambda data: svg_size(data.decode("utf-8", "ignore")),
        ".avif": None,
    }
    order = [by_ext.get(ext)] if by_ext.get(ext) else []
    order += [png_size, jpeg_size, webp_size]
    size = None
    for reader in order:
        size = reader(head)
        if size:
            break
    return size, os.path.getsize(path)


def natural_key(text):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def split_name(name):
    stem, ext = os.path.splitext(name)
    match = re.match(r"^(.*)@(\d)x$", stem)
    if match:
        return match.group(1), ext.lower(), int(match.group(2)), True
    return stem, ext.lower(), 1, False


def collect():
    if not os.path.isdir(ASSETS):
        sys.exit("找不到 assets/ 目录：" + ASSETS)
    names = [
        name
        for name in os.listdir(ASSETS)
        if name.lower().endswith(EXTS) and not name.startswith(".")
    ]
    if not names:
        sys.exit("assets/ 里没有图片，支持 " + "、".join(EXTS))

    groups = {}
    for name in names:
        base, ext, scale, explicit = split_name(name)
        group = groups.setdefault(base.lower(), {"base": base, "files": {}, "named": {}})
        group["files"].setdefault(ext, {})[scale] = name
        group["named"][(ext, scale)] = explicit

    entries = []
    for group in groups.values():
        for ext in EXTS:
            scales = group["files"].get(ext)
            if not scales:
                continue
            src_scale = max(scales)
            entries.append(
                {
                    "src": scales[src_scale],
                    "base": group["base"],
                    "ext": ext,
                    "scale": src_scale,
                    "explicit": group["named"].get((ext, src_scale), False),
                    "variants": scales,
                }
            )
            break
    entries.sort(key=lambda entry: natural_key(entry["base"]))
    return entries


def hotspots_for(entry, hotspots):
    for key in (entry["src"], entry["base"] + entry["ext"], entry["base"]):
        if key in hotspots:
            return hotspots[key]
    return []


def slide_html(entry, first, lazy, hotspots):
    path = os.path.join(ASSETS, entry["src"])
    size, bytes_ = image_info(path)
    src = "assets/" + entry["src"]
    attrs = ['class="shot"', 'src="' + src + '"']
    notes = []
    height = 0

    if size:
        raw_width, raw_height = size
        scale = entry["scale"]
        derived = round(raw_width / DESIGN_WIDTH) if raw_width else 0
        derived = derived if 1 <= derived <= 4 and raw_width % DESIGN_WIDTH == 0 else 0
        if derived and derived != scale and entry["explicit"]:
            notes.append("文件名写着 %dx，实际宽度 %dpx，按 %dx 处理" % (scale, raw_width, derived))
        if derived:
            scale = derived
        elif raw_width % DESIGN_WIDTH:
            notes.append("宽度 %d 不是 %d 的整数倍" % (raw_width, DESIGN_WIDTH))
        height = max(2, round(round(raw_height / scale) / 2) * 2)
        attrs += ['width="%d"' % DESIGN_WIDTH, 'height="%d"' % height]
    else:
        notes.append("读不出尺寸，请手动给这页加 data-h")

    lower = [entry["variants"][s] for s in sorted(entry["variants"]) if s < entry["scale"]]
    if lower and size:
        candidates = []
        for scale in sorted(entry["variants"]):
            name = entry["variants"][scale]
            candidates.append("assets/%s %dw" % (name, DESIGN_WIDTH * scale))
        attrs.append('srcset="' + ", ".join(candidates) + '"')
        attrs.append('sizes="(max-width: %dpx) 100vw, %dpx"' % (DESIGN_WIDTH, DESIGN_WIDTH))

    if lazy and not first:
        attrs.append('loading="lazy"')
    elif first:
        attrs.append('fetchpriority="high"')
    attrs.append('decoding="async"')
    attrs.append('alt=""')

    lines = ['        <section class="slide">']
    lines.append("          <img " + " ".join(attrs) + " />")
    for spot in hotspots_for(entry, hotspots):
        lines.append(
            '          <a class="hotspot" href="%s" style="left:%dpx; top:%dpx; width:%dpx; height:%dpx"></a>'
            % (spot["href"], spot.get("x", 0), spot.get("y", 0), spot.get("w", 0), spot.get("h", 0))
        )
    lines.append("        </section>")
    return "\n".join(lines), height, bytes_, notes


def human(number):
    if number >= 1048576:
        return "%.1f MB" % (number / 1048576)
    return "%.0f KB" % (number / 1024)


def main():
    lazy = "--eager" not in sys.argv
    hotspots = {}
    if os.path.exists(HOTSPOTS):
        with open(HOTSPOTS, encoding="utf-8") as handle:
            hotspots = json.load(handle)

    with open(TARGET, encoding="utf-8") as handle:
        page = handle.read()
    if BEGIN not in page or END not in page:
        sys.exit("index.html 里缺少 " + BEGIN + " / " + END + " 标记")

    entries = collect()
    blocks, rows, total, warns = [], [], 0, []
    for position, entry in enumerate(entries):
        html, height, bytes_, notes = slide_html(entry, position == 0, lazy, hotspots)
        blocks.append(html)
        rows.append((entry["src"], height, bytes_, notes))
        total += bytes_
        if bytes_ > WARN_SLIDE_BYTES:
            warns.append("%s 单张 %s，偏大" % (entry["src"], human(bytes_)))
        if height > WARN_HEIGHT:
            warns.append("%s 高度 %d px，iOS 上可能渲染异常，建议再切一刀" % (entry["src"], height))
        for note in notes:
            warns.append("%s：%s" % (entry["src"], note))
    if total > WARN_TOTAL_BYTES:
        warns.append("整站图片合计 %s，手机流量下打开会慢" % human(total))

    head, rest = page.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    page = head + BEGIN + "\n" + "\n".join(blocks) + "\n        " + END + tail
    with open(TARGET, "w", encoding="utf-8") as handle:
        handle.write(page)

    width = max(len(row[0]) for row in rows)
    for name, height, bytes_, _ in rows:
        print("%-*s  高 %5d  %8s" % (width, name, height, human(bytes_)))
    print("\n共 %d 页，合计 %s，已写入 %s" % (len(rows), human(total), os.path.relpath(TARGET, ROOT)))
    if warns:
        print("\n注意：")
        for line in warns:
            print("  - " + line)


if __name__ == "__main__":
    main()
