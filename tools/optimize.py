#!/usr/bin/env python3
"""把 assets/ 里的 PNG/JPG 转成 WebP，原图移出仓库，再重建页面。

用法：
    python3 tools/optimize.py            # 质量 90
    python3 tools/optimize.py -q 85      # 自定义质量
    python3 tools/optimize.py --keep     # 转换但保留原图在 assets/
"""

import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
BACKUP = os.path.join(os.path.dirname(ROOT), "png-originals")
SOURCES = (".png", ".jpg", ".jpeg")


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


def quality_from_argv():
    if "-q" in sys.argv:
        return sys.argv[sys.argv.index("-q") + 1]
    return "90"


def human(number):
    if number >= 1048576:
        return "%.2f MB" % (number / 1048576)
    return "%.0f KB" % (number / 1024)


def main():
    cwebp = find_cwebp()
    quality = quality_from_argv()
    keep = "--keep" in sys.argv

    names = sorted(
        name for name in os.listdir(ASSETS) if name.lower().endswith(SOURCES)
    )
    if not names:
        print("assets/ 里没有 PNG/JPG，无需转换")
    backup = os.path.join(BACKUP, time.strftime("%Y%m%d-%H%M%S"))
    if names and not keep:
        os.makedirs(backup, exist_ok=True)

    total_before = total_after = 0
    for name in names:
        src = os.path.join(ASSETS, name)
        out = os.path.join(ASSETS, os.path.splitext(name)[0] + ".webp")
        result = subprocess.run(
            [cwebp, "-q", quality, "-m", "6", "-mt", "-metadata", "none", src, "-o", out],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("转换失败 %s: %s" % (name, result.stderr.strip()[:160]))
            continue
        before = os.path.getsize(src)
        after = os.path.getsize(out)
        total_before += before
        total_after += after
        if after >= before:
            os.remove(out)
            print("%-18s %8s -> WebP 反而更大，保留原图" % (name, human(before)))
            continue
        if keep:
            print("%-18s %8s -> %8s  (%3.0f%%)  原图保留" % (name, human(before), human(after), after / before * 100))
        else:
            shutil.move(src, os.path.join(backup, name))
            print("%-18s %8s -> %8s  (%3.0f%%)  原图已移到 %s"
                  % (name, human(before), human(after), after / before * 100,
                     os.path.relpath(backup, ROOT)))

    if names:
        print("-" * 70)
        print("合计 %s -> %s" % (human(total_before), human(total_after)))

    print()
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build.py")], check=True)


if __name__ == "__main__":
    main()
