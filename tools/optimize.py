#!/usr/bin/env python3
"""把 assets/ 里的 PNG/JPG 转成分级 AVIF（WebP 兜底），原图移出仓库，再重建页面。

产出（都放在 assets/ 下）：
    NN@1280w.avif  NN@1920w.avif  NN@2560w.avif  NN@3200w.avif  NN@3840w.avif
    NN@1920w.webp        不支持 AVIF 的浏览器走这张
    lqip/NN.webp         20px 宽的模糊占位图，构建时内联进 index.html

页面用 <picture> + srcset/sizes 让浏览器按「窗口宽度 × 像素密度」自己挑档：
4K 屏拿 3840，笔记本拿 3200/2560，手机拿 1280，谁都不会多下流量。

用法：
    python3 tools/optimize.py                        # AVIF 质量 68 / WebP 86
    python3 tools/optimize.py --avif-q 72 --webp-q 90
    python3 tools/optimize.py --keep                 # 转换但保留原图在 assets/
"""

import os
import re
import shutil
import subprocess
import sys
import time

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
BACKUP = os.path.join(os.path.dirname(ROOT), "png-originals")
LQIP_DIR = os.path.join(ASSETS, "lqip")
SOURCES = (".png", ".jpg", ".jpeg")

TIERS = (1280, 1920, 2560, 3200, 3840)
FALLBACK_TIER = 1920
LQIP_WIDTH = 20
LQIP_QUALITY = 40
AVIF_SPEED = 6


def find_cwebp():
    candidates = [
        os.path.join(os.path.dirname(ROOT), "bin", "cwebp"),
        os.path.join(os.path.dirname(ROOT), "cwebp"),
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    found = shutil.which("cwebp")
    if found:
        return found
    sys.exit(
        "找不到 cwebp。可从 https://storage.googleapis.com/downloads.webmproject.org/"
        "releases/webp/libwebp-1.6.0-mac-x86-64.tar.gz 下载后放到 ../bin/cwebp"
    )


def arg_value(flag, default):
    if flag in sys.argv:
        index = sys.argv.index(flag)
        if index + 1 < len(sys.argv):
            return sys.argv[index + 1]
    return default


def human(number):
    if number >= 1048576:
        return "%.2f MB" % (number / 1048576)
    if number >= 1024:
        return "%.0f KB" % (number / 1024)
    return "%d B" % number


def drop_useless_alpha(image):
    """alpha 全不透明就去掉，能省一点体积；真有透明才保留。"""
    has_alpha = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )
    if not has_alpha:
        return image if image.mode in ("RGB", "RGBA") else image.convert("RGB")
    rgba = image.convert("RGBA")
    if rgba.getchannel("A").getextrema() == (255, 255):
        return rgba.convert("RGB")
    return rgba


def tiers_for(width):
    return sorted(set([tier for tier in TIERS if tier < width] + [width]))


def clear_stale(base):
    pattern = re.compile(r"^%s(@\d+w)?\.(avif|webp)$" % re.escape(base))
    for name in os.listdir(ASSETS):
        if pattern.match(name):
            os.remove(os.path.join(ASSETS, name))


def main():
    cwebp = find_cwebp()
    avif_quality = int(arg_value("--avif-q", "68"))
    webp_quality = int(arg_value("--webp-q", "86"))
    keep = "--keep" in sys.argv

    names = sorted(
        name
        for name in os.listdir(ASSETS)
        if name.lower().endswith(SOURCES) and not name.startswith(".")
    )
    if not names:
        print("assets/ 里没有 PNG/JPG，直接重建页面")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build.py")], check=True)
        return

    backup = os.path.join(BACKUP, time.strftime("%Y%m%d-%H%M%S"))
    if not keep:
        os.makedirs(backup, exist_ok=True)
    os.makedirs(LQIP_DIR, exist_ok=True)

    before_total = 0
    tier_totals = {}
    print("%-6s %-12s %s" % ("页", "原始尺寸", "AVIF 各档 / WebP 兜底"))
    for name in names:
        src = os.path.join(ASSETS, name)
        base = os.path.splitext(name)[0]
        with Image.open(src) as handle:
            image = drop_useless_alpha(handle)
            image.load()
        width, height = image.size
        clear_stale(base)
        tiers = tiers_for(width)

        parts = []
        for tier in tiers:
            out = os.path.join(ASSETS, "%s@%dw.avif" % (base, tier))
            if tier == width:
                frame = image
            else:
                frame = image.resize(
                    (tier, max(1, round(height * tier / width))), Image.LANCZOS
                )
            frame.save(out, "AVIF", quality=avif_quality, speed=AVIF_SPEED)
            size = os.path.getsize(out)
            tier_totals[tier] = tier_totals.get(tier, 0) + size
            parts.append("%d=%s" % (tier, human(size)))

        fallback = FALLBACK_TIER if FALLBACK_TIER in tiers else tiers[-1]
        webp = os.path.join(ASSETS, "%s@%dw.webp" % (base, fallback))
        command = [
            cwebp, "-quiet", "-q", str(webp_quality), "-m", "6", "-sharp_yuv",
            "-metadata", "none",
        ]
        if fallback != width:
            command += ["-resize", str(fallback), "0"]
        subprocess.run(command + [src, "-o", webp], check=True)
        parts.append("webp=%s" % human(os.path.getsize(webp)))

        small = image.resize(
            (LQIP_WIDTH, max(1, round(height * LQIP_WIDTH / width))), Image.LANCZOS
        )
        small.save(os.path.join(LQIP_DIR, base + ".webp"), "WEBP",
                   quality=LQIP_QUALITY, method=6)

        before_total += os.path.getsize(src)
        print("%-6s %-12s %s" % (base, "%dx%d" % (width, height), "  ".join(parts)))

        if not keep:
            shutil.move(src, os.path.join(backup, name))

    print("-" * 78)
    print("原始合计 %s" % human(before_total))
    print("按档位合计： " + "   ".join(
        "%d=%s" % (tier, human(tier_totals[tier])) for tier in sorted(tier_totals)
    ))
    print("（浏览器只会下载其中一档，不是全部相加）")
    if not keep:
        print("原图已移到 %s" % os.path.relpath(backup, ROOT))
    print()
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build.py")], check=True)


if __name__ == "__main__":
    main()
