"""アイコンセットの汎用インポーター。

どの取り込み口 (ノズル) も IconifyJSON (`{prefix, info, icons: {name: {body, width, height, left, top}}}`) を作り、
`icons/sets/<prefix>.json` に保存する。Library はこの1形式だけを読む。形式は SVG のみ (PNG は扱わない)。

| ノズル | 取り込み元 | 例 |
| --- | --- | --- |
| aws | AWS 公式 Asset Package の ZIP (または変換済みの draw.io ライブラリのフォルダ) | `archdraw icons fetch aws ./Icon-package.zip` |
| iconify | npm の @iconify-json/<prefix> (Lucide / Simple Icons / Devicon / logos など 200 超) | `archdraw icons fetch iconify lucide devicon` |
| svgl | SVGL (モダン Web スタック・AI のロゴ)。API + リポジトリのアーカイブ | `archdraw icons fetch svgl` |
| cloudflare | Cloudflare の製品アイコン (公式ドキュメントのリポジトリ)。手元のフォルダ・ZIP も可 | `archdraw icons fetch cloudflare` |
| svg | 手元の SVG のディレクトリか ZIP (Cloudflare の製品アイコン、社内アイコンなど) | `archdraw icons fetch svg ./cf-icons.zip --prefix cloudflare` |
"""

from __future__ import annotations

import io
import json
import re
import tarfile
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from archdraw.icons import AWS_DIR, ICON_DOWNLOAD_URL, SETS_DIR, Library

ICONIFY_URL = "https://cdn.jsdelivr.net/npm/@iconify-json/{}/icons.json"
SVGL_API = "https://api.svgl.app"
SVGL_ARCHIVE = "https://github.com/pheralb/svgl/archive/refs/heads/main.tar.gz"
CLOUDFLARE_TREE = "https://github.com/cloudflare/cloudflare-docs/tree/production/src/icons"
CLOUDFLARE_LIST = "https://api.github.com/repos/cloudflare/cloudflare-docs/contents/src/icons?ref=production"
CLOUDFLARE_RAW = "https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/icons/{}"
CLOUDFLARE_ORANGE = "#F6821F"
PREFIX_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# <svg> の属性のうち、中身に引き継ぐもの (fill="none" stroke=... を持つ線画アイコンのため)
_INHERIT = re.compile(r'\s((?:fill|stroke|stroke-[a-z]+|color|style|opacity|fill-rule|clip-rule)=("[^"]*"|\'[^\']*\'))')


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "arch-builder"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def svg_to_icon(text: str) -> dict | None:
    """SVG 文書 1 つを IconifyJSON の icon ({body, left, top, width, height}) にする。SVG でなければ None。"""
    m = re.search(r"<svg\b([^>]*)>(.*)</svg\s*>", text, re.S | re.I)
    if not m:
        return None
    attrs, body = m.group(1), m.group(2).strip()
    vb = re.search(r'viewBox=["\']\s*([-\d.eE]+)[\s,]+([-\d.eE]+)[\s,]+([\d.eE]+)[\s,]+([\d.eE]+)', attrs)
    if vb:
        left, top, w, h = (float(v) for v in vb.groups())
    else:  # viewBox が無ければ width / height を使う
        wh = [re.search(rf'\s{k}=["\']\s*([\d.]+)', attrs) for k in ("width", "height")]
        if not all(wh):
            return None
        left, top, (w, h) = 0, 0, (float(x.group(1)) for x in wh)
    keep = "".join(a.group(0) for a in _INHERIT.finditer(attrs))
    if keep:
        body = f"<g{keep}>{body}</g>"
    if re.search(r"xlink:", body) and "xmlns:xlink" not in body:
        body = f'<g xmlns:xlink="http://www.w3.org/1999/xlink">{body}</g>'
    return {"body": body, "left": left, "top": top, "width": w, "height": h}


def iconify(prefix: str) -> dict:
    """ノズル: @iconify-json/<prefix>。元から IconifyJSON なので検証だけする。"""
    doc = json.loads(_get(ICONIFY_URL.format(prefix)))
    if doc.get("prefix") != prefix or "icons" not in doc:
        raise ValueError(f"IconifyJSON ではない: {ICONIFY_URL.format(prefix)}")
    info = json.loads(_get(ICONIFY_URL.format(prefix).replace("icons.json", "info.json")))
    doc["info"] = {k: info[k] for k in ("name", "author", "license") if k in info}  # ライセンスは info.json 側にある
    return doc


def svgl(prefix: str = "svgl") -> dict:
    """ノズル: SVGL。名前と分類は API、SVG の中身はリポジトリのアーカイブから 1 回で取る。

    SVGL には全ロゴをまとめた配布物 (npm パッケージや ZIP) が無い。API は 1 ロゴ 1 URL を返すだけなので、
    個別に取ると 1,300 回のリクエストになる (svgl.app は 1 回数秒)。アーカイブ (約 3MB) なら 1 回で済む。
    アーカイブに無いもの (反映待ちの新着) だけ個別に取る。ライト/ダーク版があるものは `<名前>` と `<名前>-dark`。
    """
    jobs = {}
    for e in json.loads(_get(SVGL_API)):
        name = slug(e["title"])
        routes = e["route"] if isinstance(e["route"], dict) else {"light": e["route"]}
        for mode, url in routes.items():
            jobs[name if mode == "light" else f"{name}-{mode}"] = url
    try:
        tar = tarfile.open(fileobj=io.BytesIO(_get(SVGL_ARCHIVE)))
        files = {Path(m.name).name: m for m in tar.getmembers() if "/static/library/" in m.name and m.isfile()}
    except (OSError, tarfile.TarError):
        tar, files = None, {}

    def one(item):
        name, url = item
        base = url.rsplit("/", 1)[-1]
        if base in files:
            return name, svg_to_icon(tar.extractfile(files[base]).read().decode("utf-8", "replace"))
        try:
            return name, svg_to_icon(_get(url).decode("utf-8", "replace"))
        except OSError:
            return name, None

    in_tar = {k: v for k, v in jobs.items() if v.rsplit("/", 1)[-1] in files}
    icons = dict(map(one, in_tar.items()))
    with ThreadPoolExecutor(16) as ex:
        icons.update(ex.map(one, [j for j in jobs.items() if j[0] not in in_tar]))
    icons = {k: v for k, v in icons.items() if v}
    return {"prefix": prefix, "info": {"name": "SVGL", "license": {"title": "各ブランドの規約に従う"},
                                       "author": {"url": "https://svgl.app"}},
            "icons": icons, "skipped": sorted(set(jobs) - set(icons))}


def cloudflare(src: Path | None = None, prefix: str = "cloudflare") -> dict:
    """ノズル: Cloudflare の製品アイコン (Workers / KV / D1 / R2 / Zero Trust ...)。

    Cloudflare は AWS のような公式アイコン ZIP を配っていない。公式ドキュメントのリポジトリ (cloudflare-docs) の
    src/icons にある製品アイコン (CC BY 4.0) を使う。リポジトリ全体は 1.4GB あるので、そのフォルダだけを取る。
    src を渡せば、手元に用意したフォルダか ZIP から取り込む (ネットワークが使えない環境向け)。
    """
    if src:
        doc = svg_files(src, prefix, under="src/icons/")
    else:
        names = [e["name"] for e in json.loads(_get(CLOUDFLARE_LIST)) if e["name"].endswith(".svg")]

        def one(n):
            try:
                return slug(n[:-4]), svg_to_icon(_get(CLOUDFLARE_RAW.format(n)).decode("utf-8", "replace"))
            except OSError:
                return slug(n[:-4]), None

        with ThreadPoolExecutor(16) as ex:
            got = dict(ex.map(one, names))
        doc = {"prefix": prefix, "icons": {k: v for k, v in got.items() if v},
               "skipped": sorted(k for k, v in got.items() if not v)}
    for ic in doc["icons"].values():  # 塗りの指定が無いパスは黒になるので、Cloudflare のオレンジを既定の塗りにする
        ic["body"] = f'<g fill="{CLOUDFLARE_ORANGE}">{ic["body"].replace("currentColor", CLOUDFLARE_ORANGE)}</g>'
    doc["info"] = {"name": "Cloudflare product icons", "author": {"name": "Cloudflare", "url": CLOUDFLARE_TREE},
                   "license": {"title": "CC BY 4.0 (Cloudflare の商標は Cloudflare に帰属)", "spdx": "CC-BY-4.0",
                               "url": "https://github.com/cloudflare/cloudflare-docs/blob/production/LICENSE"}}
    return doc


CLOUDFLARE_HELP = f"""Cloudflare の製品アイコンを自動で取得できなかった。手元に用意して取り込む:
  1. 公式ドキュメントのリポジトリにあるアイコンのフォルダ: {CLOUDFLARE_TREE}
     リポジトリ全体は 1.4GB あるので、フォルダだけを取る:
       git clone --depth 1 --filter=blob:none --sparse https://github.com/cloudflare/cloudflare-docs
       git -C cloudflare-docs sparse-checkout set src/icons
  2. archdraw icons fetch cloudflare ./cloudflare-docs/src/icons   (フォルダでも ZIP でもよい)"""


def svg_files(src: Path, prefix: str, under: str = "") -> dict:
    """ノズル: 手元の SVG (ディレクトリか ZIP)。名前はファイル名。同名があれば親ディレクトリ名を前に付ける。

    under を渡すと、そのパスを含むファイルがあればそれだけを取る (リポジトリ丸ごとの ZIP を渡されたとき用)。
    """
    if src.suffix.lower() == ".zip":
        z = zipfile.ZipFile(src)
        files = [(Path(n), lambda n=n: z.read(n)) for n in z.namelist() if not n.endswith("/")]
    else:
        files = [(p.relative_to(src), p.read_bytes) for p in src.rglob("*") if p.is_file()]
    if under and any(under in f[0].as_posix() for f in files):
        files = [f for f in files if under in f[0].as_posix()]
    icons, skipped = {}, []
    for rel, read in sorted(files, key=lambda f: str(f[0])):
        if rel.suffix.lower() != ".svg":
            if rel.suffix.lower() in (".png", ".jpg", ".jpeg"):
                skipped.append(rel.as_posix())  # ponytail: ラスター画像は取り込まない。SVG が無いアイコンが出てきたら考える
            continue
        icon = svg_to_icon(read().decode("utf-8", "replace"))
        if not icon:
            skipped.append(rel.as_posix())
            continue
        name = slug(rel.stem)
        if name in icons:
            name = slug(f"{rel.parent.name}-{rel.stem}")
        icons[name] = icon
    return {"prefix": prefix, "info": {"name": src.stem, "license": {"title": "取り込み元の規約に従う"}},
            "icons": icons, "skipped": skipped}


AWS_HELP = f"""AWS 公式アイコン (Asset Package の ZIP) が要る。
  1. {ICON_DOWNLOAD_URL} の「Asset Package」をダウンロードする (Icon-package_*.zip)
  2. archdraw icons fetch aws <ダウンロードした ZIP のパス>"""


def aws(src: Path, dest: Path = AWS_DIR) -> dict:
    """ノズル: AWS 公式アイコン。AWS は再配布を認めていないので、利用者が ZIP を取ってきて渡す。

    ZIP は draw.io ライブラリ (AWS-*.xml) に変換して dest に置く (日付付きの XML と current/)。
    変換済みのフォルダ (current/ かその親) を渡したときは、そのまま写す。AWS の4つのライブラリは
    取り込んだセット (IconifyJSON) と形式が違うが、グループアイコンとサービス/リソース/カテゴリの区別を
    lint が使うので、そのまま読む。
    """
    if not src.exists():
        raise ValueError(f"見つからない: {src}\n{AWS_HELP}")
    if src.suffix.lower() == ".zip":
        from archdraw.vendor.build_aws_drawio_libraries import build
        build(src, dest)
    else:
        cur = src / "current" if (src / "current").is_dir() else src
        files = list(cur.glob("AWS-*.xml"))
        if not files:
            raise ValueError(f"AWS-*.xml が無い: {cur}\n{AWS_HELP}")
        (dest / "current").mkdir(parents=True, exist_ok=True)
        for f in files:
            (dest / "current" / f.name).write_bytes(f.read_bytes())
        for f in cur.parent.glob("AWS-*-????-??-??.xml"):  # Asset Package の日付は日付付きの XML の名前で持つ
            (dest / f.name).write_bytes(f.read_bytes())
    lib = Library(dest / "current", require_aws=True)
    return {"prefix": "aws", "icons": lib.icons,
            "info": {"name": "AWS Architecture Icons", "license": {"title": "AWS の利用規約に従う (再配布しない)"}}}


def save(doc: dict, dest: Path = SETS_DIR) -> Path:
    prefix = doc["prefix"]
    if not PREFIX_RE.fullmatch(prefix):
        raise ValueError(f"prefix は英小文字・数字・ハイフンだけ: {prefix!r}")
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"{prefix}.json"
    out.write_text(json.dumps({k: v for k, v in doc.items() if k != "skipped"}, ensure_ascii=False), encoding="utf-8")
    return out


def run(nozzle: str, args: list[str], prefix: str | None = None, dest: Path = SETS_DIR) -> list[tuple[Path, dict]]:
    """ノズルを動かして保存する。戻り値は (保存先, 取り込んだ IconifyJSON) の一覧。"""
    if nozzle == "aws":
        if len(args) != 1:
            raise ValueError(AWS_HELP)
        out = Path(dest).parent / "aws" if dest != SETS_DIR else AWS_DIR
        return [(out / "current", aws(Path(args[0]), out))]
    if nozzle == "iconify":
        for p in args:
            if not PREFIX_RE.fullmatch(p):
                raise ValueError(f"Iconify の prefix ではない: {p!r}")
        docs = [iconify(p) for p in args]
    elif nozzle == "svgl":
        docs = [svgl(prefix or "svgl")]
    elif nozzle == "cloudflare":
        try:
            docs = [cloudflare(Path(args[0]) if args else None, prefix or "cloudflare")]
        except OSError as e:
            raise ValueError(f"{e}\n{CLOUDFLARE_HELP}") from e
    elif nozzle == "svg":
        if len(args) != 1 or not prefix:
            raise ValueError("svg ノズルは `<ディレクトリか ZIP> --prefix <名前>` で指定する")
        docs = [svg_files(Path(args[0]), prefix)]
    else:
        raise ValueError(f"ノズルは aws / iconify / svgl / cloudflare / svg: {nozzle!r}")
    return [(save(d, dest), d) for d in docs]


if __name__ == "__main__":  # 自己チェック: ネットワークを使わない部分
    lucide = svg_to_icon('<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
                         'stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/></svg>')
    assert lucide["width"] == 24 and lucide["body"].startswith('<g fill="none" stroke="currentColor" stroke-width="2">')
    assert svg_to_icon('<svg width="32px" height="16"><rect/></svg>')["width"] == 32
    assert svg_to_icon("<html/>") is None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a/Workers.svg", '<svg viewBox="0 0 10 10"><path d="M0 0h10"/></svg>')
        z.writestr("b/Workers.svg", '<svg viewBox="0 0 10 10"><path d="M0 0v10"/></svg>')
        z.writestr("c/KV.png", b"\x89PNG")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "x.zip").write_bytes(buf.getvalue())
        doc = svg_files(Path(d) / "x.zip", "cf")
    assert set(doc["icons"]) == {"workers", "b-workers"} and doc["skipped"] == ["c/KV.png"], doc
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:  # リポジトリ丸ごとの ZIP: src/icons/ だけを取り、既定の塗りを付ける
        z.writestr("cloudflare-docs-production/src/icons/kv.svg", '<svg viewBox="0 0 48 48"><path d="M0 0h9"/></svg>')
        z.writestr("cloudflare-docs-production/public/logo.svg", '<svg viewBox="0 0 9 9"><path/></svg>')
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "cf.zip").write_bytes(buf.getvalue())
        doc = cloudflare(Path(d) / "cf.zip")
    assert list(doc["icons"]) == ["kv"] and CLOUDFLARE_ORANGE in doc["icons"]["kv"]["body"], doc
    print("ok")
