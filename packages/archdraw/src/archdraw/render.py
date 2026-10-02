""".drawio -> PNG / SVG / PDF。draw.io Desktop のコマンドライン書き出しを使う。

探す順: $DRAWIO_CMD、OS ごとの既定の置き場所、PATH 上の draw.io / drawio。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def find_drawio() -> str | None:
    env = os.environ.get("DRAWIO_CMD")
    cands = [env] if env else []
    if sys.platform == "win32":
        cands += [str(Path(os.environ.get(k, "")) / sub / "draw.io.exe") for k, sub in
                  (("ProgramFiles", "draw.io"), ("LOCALAPPDATA", "Programs/draw.io"))]
    elif sys.platform == "darwin":
        cands += ["/Applications/draw.io.app/Contents/MacOS/draw.io"]
    else:
        cands += ["/usr/bin/drawio", "/usr/local/bin/drawio", "/snap/bin/drawio"]
    for c in cands:
        if c and Path(c).is_file():
            return c
    return shutil.which("draw.io") or shutil.which("drawio")


def export(drawio: Path, out: Path, scale: float = 2, timeout: float = 120) -> Path:
    """out の拡張子 (png / svg / pdf / jpg) で書き出す。scale 2 は 48px アイコンのラベルまで読める解像度。"""
    exe = find_drawio()
    if not exe:
        raise RuntimeError("draw.io Desktop が見つからない (https://www.drawio.com/ から入れるか、$DRAWIO_CMD で場所を指定する)")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    fmt = out.suffix.lstrip(".").lower()
    args = [exe, "-x", "-f", fmt, "-o", str(out)] + (["-s", str(scale)] if fmt != "svg" else []) + [str(drawio)]
    if os.environ.get("ARCHDRAW_DRAWIO_PROFILE"):  # 共有プロファイルに書けない環境 (サンドボックス) 向け
        args.insert(1, f"--user-data-dir={os.environ['ARCHDRAW_DRAWIO_PROFILE']}")
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    # Desktop はファイルを書き終える前に戻ることがある。大きさが落ち着くまで待つ
    last, deadline = -1, time.time() + 15
    while time.time() < deadline:
        size = out.stat().st_size if out.exists() else -1
        if size > 0 and size == last:
            return out
        last = size
        time.sleep(0.3)
    raise RuntimeError(f"書き出せなかった (exit {r.returncode}): {r.stderr.strip()[:500]}")
