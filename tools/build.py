#!/usr/bin/env python3
"""扫描 assets/，按文件名顺序生成 index.html 里的 <section class="slide">。

每个 base（例 01）下的所有文件会合成一张 <picture>：
    <source type="image/avif">  01@1280w.avif … 01@3840w.avif
    <source type="image/webp">  01@1920w.webp（老浏览器兜底）
    <img>                       兜底 src + width/height（防跳版）

尺寸由文件里真实像素宽决定，不看文件名后缀，改名也不会算错高度。

用法：
    python3 tools/build.py            首个 <picture> 写进 <head> 预加载
    python3 tools/build.py --eager    全部图片都不懒加载
"""

import base64
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
LQIP_DIR = os.path.join(ASSETS, "lqip")
TARGET = os.path.join(ROOT, "index.html")
HOTSPOTS = os.path.join(ROOT, "hotspots.json")
DESIGN_WIDTH = 1920
EXTS = (".avif", ".webp", ".png", ".jpg", ".jpeg", ".svg")
BEGIN = "<!-- BUILD:SLIDES -->"
END = "<!-- /BUILD:SLIDES -->"
PRELOAD_BEGIN = "<!-- BUILD:PRELOAD -->"
PRELOAD_END = "<!-- /BUILD:PRELOAD -->"

MIME = {
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
}
FORMATS = (".avif", ".webp", ".png", ".jpg", ".jpeg", ".svg")
SIZES_ATTR = "(max-width: %dpx) 100vw, %dpx" % (DESIGN_WIDTH, DESIGN_WIDTH)

WARN_SLIDE_BYTES = 600000
WARN_TOTAL_BYTES = 8000000
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
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if kind == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def svg_size(text):
    box = re.search(r'viewBox="([^"]+)"', text)
    if box:
        parts = [float(v) for v in re.split(r"[\s,]+", box.group(1).strip()) if v]
        if len(parts) == 4:
            return int(parts[2]), int(parts[3])
    width = re.search(r'width="([\d.]+)', text)
    height = re.search(r'height="([\d.]+)', text)
    if width and height:
        return int(float(width.group(1))), int(float(height.group(1)))
    return None


def pil_size(path):
    """AVIF 没有纯标准库解析，交给 Pillow 读文件头（不解码像素）。"""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as handle:
            return handle.size
    except Exception:
        return None


def image_info(path):
    with open(path, "rb") as handle:
        head = handle.read(4096)
    ext = os.path.splitext(path)[1].lower()
    readers = {
        ".png": png_size,
        ".jpg": jpeg_size,
        ".jpeg": jpeg_size,
        ".webp": webp_size,
        ".svg": lambda data: svg_size(data.decode("utf-8", "ignore")),
    }
    size = None
    for reader in [readers.get(ext), png_size, jpeg_size, webp_size]:
        if not reader:
            continue
        size = reader(head)
        if size:
            break
    if not size:
        size = pil_size(path)
    return size, os.path.getsize(path)


def natural_key(text):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


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
        stem, ext = os.path.splitext(name)
        base = stem.split("@")[0]
        size, _ = image_info(os.path.join(ASSETS, name))
        if not size:
            print("跳过（读不出宽高）：%s" % name)
            continue
        group = groups.setdefault(base.lower(), {"base": base, "ladders": {}})
        group["ladders"].setdefault(ext.lower(), {})[size[0]] = name

    entries = []
    for group in groups.values():
        ordered = [
            (ext, group["ladders"][ext]) for ext in FORMATS if ext in group["ladders"]
        ]
        if not ordered:
            continue
        entries.append({"base": group["base"], "ladders": ordered})
    entries.sort(key=lambda entry: natural_key(entry["base"]))
    return entries


def ladder_srcset(ladder):
    return ", ".join("assets/%s %dw" % (ladder[width], width) for width in sorted(ladder))


def hotspots_for(entry, hotspots):
    top = entry["ladders"][0][1]
    for key in (top[max(top)], entry["base"] + ".webp", entry["base"]):
        if key in hotspots:
            return hotspots[key]
    return []


def lqip_data(base):
    path = os.path.join(LQIP_DIR, base + ".webp")
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return "data:image/webp;base64," + base64.b64encode(handle.read()).decode("ascii")


def slide_html(entry, first, lazy, hotspots):
    top_ext, top_ladder = entry["ladders"][0]
    top_width = max(top_ladder)
    size, bytes_ = image_info(os.path.join(ASSETS, top_ladder[top_width]))
    raw_width, raw_height = size
    height = max(1, round(raw_height * DESIGN_WIDTH / raw_width))
    notes = []
    if raw_width < DESIGN_WIDTH:
        notes.append("宽度只有 %dpx，放大到 1920 会糊，建议重新导出 2x" % raw_width)

    sources = [
        '<source type="%s" srcset="%s" sizes="%s" />'
        % (MIME[ext], ladder_srcset(ladder), SIZES_ATTR)
        for ext, ladder in entry["ladders"]
    ]

    fallback = None
    for ext, ladder in entry["ladders"]:
        if ext == ".webp":
            fallback = ladder[max(ladder)]
    if fallback is None:
        fallback = top_ladder[top_width]

    attrs = [
        'class="shot"',
        'src="assets/%s"' % fallback,
        'width="%d"' % DESIGN_WIDTH,
        'height="%d"' % height,
    ]
    if lazy and not first:
        attrs.append('loading="lazy"')
    elif first:
        attrs.append('fetchpriority="high"')
    attrs.append('decoding="async"')
    attrs.append('alt=""')

    opening = '        <section class="slide"'
    lqip = lqip_data(entry["base"])
    if lqip:
        opening += ' style="background-image:url(\'%s\')"' % lqip
    opening += ">"

    lines = [opening, "          <picture>"]
    lines += ["            " + source for source in sources]
    lines.append("            <img " + " ".join(attrs) + " />")
    lines.append("          </picture>")
    for spot in hotspots_for(entry, hotspots):
        lines.append(
            '          <a class="hotspot" href="%s" style="left:%dpx; top:%dpx; width:%dpx; height:%dpx"></a>'
            % (spot["href"], spot.get("x", 0), spot.get("y", 0), spot.get("w", 0), spot.get("h", 0))
        )
    lines.append("        </section>")
    return "\n".join(lines), height, bytes_, notes


def preload_html(entry):
    ext, ladder = entry["ladders"][0]
    return (
        '      <link rel="preload" as="image" type="%s" imagesrcset="%s" imagesizes="%s" />'
        % (MIME[ext], ladder_srcset(ladder), SIZES_ATTR)
    )


def human(number):
    if number >= 1048576:
        return "%.1f MB" % (number / 1048576)
    return "%.0f KB" % (number / 1024)


def replace_block(page, begin, end, body):
    if begin not in page or end not in page:
        return page
    head, rest = page.split(begin, 1)
    _, tail = rest.split(end, 1)
    return head + begin + body + end + tail


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
        top_width = max(entry["ladders"][0][1])
        rows.append((entry["base"], top_width, height, bytes_, notes))
        total += bytes_
        if bytes_ > WARN_SLIDE_BYTES:
            warns.append("%s 最高档 %s，偏大" % (entry["base"], human(bytes_)))
        if height > WARN_HEIGHT:
            warns.append("%s 高度 %d px，iOS 上可能渲染异常，建议再切一刀" % (entry["base"], height))
        for note in notes:
            warns.append("%s：%s" % (entry["base"], note))
    if total > WARN_TOTAL_BYTES:
        warns.append("最高档图片合计 %s，4K 屏用户会有点慢" % human(total))

    page = replace_block(page, BEGIN, END, "\n" + "\n".join(blocks) + "\n        ")
    if entries:
        page = replace_block(page, PRELOAD_BEGIN, PRELOAD_END, "\n" + preload_html(entries[0]) + "\n      ")
    with open(TARGET, "w", encoding="utf-8") as handle:
        handle.write(page)

    for base, top_width, height, bytes_, _ in rows:
        print("%-6s 高 %5d  最高档 %5dpx %8s" % (base, height, top_width, human(bytes_)))
    print("\n共 %d 页，最高档合计 %s，已写入 %s"
          % (len(rows), human(total), os.path.relpath(TARGET, ROOT)))
    if warns:
        print("\n注意：")
        for line in warns:
            print("  - " + line)


if __name__ == "__main__":
    main()
