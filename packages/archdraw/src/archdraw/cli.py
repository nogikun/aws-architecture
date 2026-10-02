"""archdraw コマンド。`archdraw -h` で一覧。

正本 (図の定義) は Python (.py)・YAML (.yaml)・タグ表記 (.html / .xml) のどれでもよい。どれも同じモデルになる。
"""

from __future__ import annotations

import argparse
import base64
import json
import runpy
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from archdraw.drawio import load_drawio, to_drawio
from archdraw.icons import ICON_DOWNLOAD_URL, LIB_FILES, Library, lib_dir, package_date
from archdraw.layout import layout
from archdraw.lint import lint, report
from archdraw.model import GROUPS, SIDES, Edge, Item, Model, dump_yaml, from_dict, load_yaml
from archdraw.render import export, find_drawio

SOURCES = (".py", ".yaml", ".yml", ".html", ".xml")


def open_lib(args) -> Library:
    return Library(lib_dir(getattr(args, "lib", None)))


def load_source(path: Path, lib: Library) -> Model:
    """図の定義を読む。.drawio は draw.io 上の座標のまま (自動配置し直さない)、それ以外は自動配置する。"""
    if not path.exists():
        raise SystemExit(f"ファイルが無い: {path} (build が error で止まると .drawio は書かれない)")
    if path.suffix == ".drawio" or path.name.endswith(".drawio.xml"):
        return load_drawio(path, lib)
    if path.suffix == ".py":
        from archdraw import api
        before = len(api.CREATED)
        runpy.run_path(str(path), run_name="__archdraw__")
        made = api.CREATED[before:]
        if not made:
            raise SystemExit(f"{path} の中で Diagram(...) が作られていない")
        m = from_dict(made[-1].doc, lib, path.stem)
    elif path.suffix in (".html", ".xml"):
        from archdraw.tags import parse
        m = from_dict(parse(path.read_text(encoding="utf-8-sig")), lib, path.stem)
    else:
        m = load_yaml(path, lib)
    layout(m)
    return m


def cmd_doctor(args) -> int:
    lib = open_lib(args)
    print(f"[aws] {lib.path}")
    if lib.has_aws:
        counts = {k: sum(i.kind == k for i in lib.icons) for k in LIB_FILES}
        date = package_date(lib.path)
        print(f"  読み込みOK: {counts}。Asset Package の日付: {date or '不明'}")
        if date:
            from datetime import date as _d
            if (_d.today() - _d.fromisoformat(date)).days > 120:
                print(f"  注意: 四半期ごとに更新される。新しい版が無いか {ICON_DOWNLOAD_URL} を確認する")
        ET.fromstring(base64.b64decode(lib.resolve("Amazon EC2").data.split(",", 1)[1]))
        missing = [g.icon for g in GROUPS.values() if g.icon and not lib.group_icon(g.icon)]
        if missing:
            print(f"  NG: グループアイコンが欠けている {missing}")
    else:
        print("  未取り込み (AWS の図を描くときだけ要る)")
        print(f"    1. {ICON_DOWNLOAD_URL} の Asset Package (Icon-package_*.zip) をダウンロードする")
        print("    2. archdraw icons fetch aws <ZIP のパス>")
    sets = lib.set_prefixes()
    print(f"[sets] {lib.sets_dir}: {', '.join(sets) or 'なし'}  (icon: <prefix>:<name>)")
    for prefix in sets:
        s = lib.icon_set(prefix)
        info = s.get("info", {})
        print(f"  {prefix}: {info.get('name', prefix)} / {len(s['icons'])} 個 / ライセンス {info.get('license', {}).get('title', '不明')}")
    print(f"[draw.io Desktop] {find_drawio() or '無い (PNG の書き出しに要る)'}")
    return 0


def cmd_icons(args) -> int:
    if args.action == "fetch":
        from archdraw import importer
        try:
            done = importer.run(args.query[0], args.query[1:], args.prefix)
        except (ValueError, OSError) as e:
            print(f"取り込めない: {e}", file=sys.stderr)
            return 1
        for path, doc in done:
            lic = doc.get("info", {}).get("license", {}).get("title", "不明")
            print(f"{doc['prefix']}: {len(doc['icons'])} 個 -> {path} (ライセンス: {lic})")
            if doc.get("skipped"):
                print(f"  SVG として読めず飛ばした: {len(doc['skipped'])} 個 ({', '.join(doc['skipped'][:5])} ...)")
        return 0
    lib = open_lib(args)
    q = " ".join(args.query)
    hits = lib.search(q)
    for ic in hits[:args.limit]:
        print(f"{ic.name}\t[{ic.kind}] {ic.category}")
    if not hits:
        print("見つからない。候補:", ", ".join(lib.suggest(q)) or "なし")
        return 1
    return 0


def cmd_build(args) -> int:
    lib = open_lib(args)
    src = Path(args.spec)
    m = load_source(src, lib)
    findings = lint(m, layout_first=False)
    out = Path(args.out or src.with_suffix(".drawio"))
    if any(f.severity == "error" and f.code.startswith("E-") for f in findings):
        print(report(findings))
        print("生成できない error がある。図の定義を直す", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".drawio", dir=out.parent, delete=False) as f:
        temp = Path(f.name)
        f.write(to_drawio(m, layout_done=True))
    try:  # 保存したものを読み直して検査する。build 時と食い違えば、書き出しのどこかが壊れている
        saved = lint(load_drawio(temp, lib), layout_first=False)
        signature = lambda fs: sorted((x.severity, x.code, x.id or "") for x in fs)  # noqa: E731
        if signature(findings) != signature(saved):
            print("build時と保存後のlint結果が一致しないため、出力を更新しない", file=sys.stderr)
            print(report(saved))
            return 1
        if any(f.severity == "error" for f in saved):
            print(report(saved))
            print("保存後lintに error があるため、出力を更新しない", file=sys.stderr)
            return 1
        temp.replace(out)
    finally:
        temp.unlink(missing_ok=True)
    print(f"wrote {out}")
    print(report(saved))
    if args.png:
        print(f"wrote {export(out, Path(args.png))}")
    return 0


def cmd_lint(args) -> int:
    lib = open_lib(args)
    m = load_source(Path(args.target), lib)
    findings = lint(m, layout_first=False)
    print(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2) if args.json else report(findings))
    strict_codes = {"N-EDGE-CROSS", "N-EDGE-TOUCH", "N-EDGE-OVERLAP", "N-EDGE-UNCHECKED"}
    failed = any(f.severity == "error" for f in findings) or (
        args.strict_geometry and any(f.code in strict_codes for f in findings))
    return 1 if failed else 0


def cmd_import(args) -> int:
    lib = open_lib(args)
    m = load_drawio(Path(args.drawio), lib)
    for it in m.items.values():
        if it.unmanaged:
            print(f"warn: {it.id}: {it.unmanaged} — icon: null のまま残す", file=sys.stderr)
    for it in m.items.values():  # draw.io 上の手直しを pos / size として残す
        it.pos = list(it._geo[:2])
        if it.kind == "group":
            it.size = list(it._geo[2:])
    out = Path(args.out)
    out.write_text(dump_yaml(m), encoding="utf-8")
    print(f"wrote {out} ({len(m.items)} items, {len(m.edges)} edges)")
    return 0


def cmd_render(args) -> int:
    src = Path(args.drawio)
    out = Path(args.out or src.with_suffix(".png"))
    try:
        print(f"wrote {export(src, out, scale=args.scale)}")
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def cmd_convert(args) -> int:
    """どの表記からでも YAML に書き出す (表記の比較や、draw.io との往復の確認に使う)。"""
    lib = open_lib(args)
    m = load_source(Path(args.spec), lib)
    for it in m.items.values():
        it.pos = it.size = None
    Path(args.out).write_text(dump_yaml(m), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


def cmd_edit(args) -> int:
    """YAML の正本をコマンドで直す (id の整合をスクリプトが保証する)。Python の正本はコードを直接直す。"""
    lib = open_lib(args)
    path = Path(args.spec)
    m = load_yaml(path, lib)
    op = args.op

    def need(iid):
        if iid not in m.items:
            raise SystemExit(f"id '{iid}' が無い")
        return m.items[iid]

    def check_icon(name):
        if not lib.resolve(name):
            raise SystemExit(f"アイコン '{name}' が無い。候補: {', '.join(lib.suggest(name))}")

    def detach(iid):
        it = m.items[iid]
        (m.items[it.parent].children if it.parent else m.roots).remove(iid)

    def attach(iid, parent, after=None):
        sib = m.items[parent].children if parent else m.roots
        sib.insert(sib.index(after) + 1 if after in sib else len(sib), iid)
        m.items[iid].parent = parent

    if op in ("add-node", "add-group"):
        if args.id in m.items:
            raise SystemExit(f"id '{args.id}' は既にある")
        if args.parent:
            need(args.parent)
        if op == "add-node":
            check_icon(args.icon)
            it = Item(args.id, "node", None, args.label or lib.resolve(args.icon).name, icon=args.icon)
        else:
            if args.type not in GROUPS:
                raise SystemExit(f"グループ種類は {', '.join(GROUPS)} のいずれか")
            it = Item(args.id, "group", None, args.label or "", group=args.type, layout=args.layout or "row")
        m.items[it.id] = it
        attach(it.id, args.parent, args.after)
    elif op == "remove":
        need(args.id)
        gone = {i.id for i in m.walk([args.id])}
        detach(args.id)
        for i in gone:
            del m.items[i]
        m.edges = [e for e in m.edges if e.src not in gone and e.dst not in gone]
    elif op == "move":
        it = need(args.id)
        if args.parent:
            need(args.parent)
            if args.parent in {i.id for i in m.walk([args.id])}:
                raise SystemExit("自分の子孫の中へは移動できない")
        detach(args.id)
        attach(args.id, args.parent, args.after)
        it.pos = None
    elif op == "set":
        it = need(args.id)
        for kv in args.pairs:
            k, _, v = kv.partition("=")
            if k == "icon":
                check_icon(v)
            if k == "group" and v not in GROUPS:
                raise SystemExit(f"グループ種類は {', '.join(GROUPS)} のいずれか")
            if k not in ("label", "icon", "group", "layout", "cols"):
                raise SystemExit(f"set できるのは label/icon/group/layout/cols: {k}")
            setattr(it, k, int(v) if k == "cols" else v.replace("\\n", "\n"))
    elif op == "connect":
        need(args.src), need(args.dst)
        m.edges.append(Edge(args.src, args.dst, args.label or "", args.dashed, args.arrow, args.exit, args.entry))
    elif op == "set-edge":
        hits = [e for e in m.edges if e.src == args.src and e.dst == args.dst]
        if not hits:
            raise SystemExit(f"{args.src} -> {args.dst} の接続線は無い")
        for kv in args.pairs:
            k, _, v = kv.partition("=")
            if k not in ("label", "dashed", "arrow", "exit", "entry"):
                raise SystemExit(f"set-edge できるのは label/dashed/arrow/exit/entry: {k}")
            if k in ("exit", "entry") and v not in SIDES + ("",):
                raise SystemExit(f"{k} は {'/'.join(SIDES)} のいずれか (空で探索に戻す)")
            val = (v.lower() == "true") if k == "dashed" else (v or None) if k in ("exit", "entry") else v.replace("\\n", "\n")
            for e in hits:
                setattr(e, k, val)
    elif op == "disconnect":
        before = len(m.edges)
        m.edges = [e for e in m.edges if not (e.src == args.src and e.dst == args.dst)]
        if len(m.edges) == before:
            raise SystemExit(f"{args.src} -> {args.dst} の接続線は無い")
    elif op == "relayout":
        for it in (m.walk([args.id]) if args.id else m.items.values()):
            it.pos = it.size = None
    path.write_text(dump_yaml(m), encoding="utf-8")
    print(f"updated {path}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="archdraw", description="システム構成図 (Python / YAML / タグ表記 <-> .drawio)")
    p.add_argument("--lib", help="AWS アイコンライブラリのディレクトリ (既定: $ARCHDRAW_HOME/icons/aws/current)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="取り込んだアイコンと draw.io Desktop を確認する")
    s = sub.add_parser("icons", help="アイコンを探す / 取り込む")
    s.add_argument("action", choices=["search", "fetch"])
    s.add_argument("query", nargs="+", help="search: 検索語 / fetch: <ノズル> <引数...> "
                   "(aws <ZIP> | iconify <prefix...> | svgl | cloudflare [フォルダかZIP] | svg <フォルダかZIP> --prefix <名前>)")
    s.add_argument("--prefix", help="fetch: 保存するセットの prefix (svg では必須)")
    s.add_argument("--limit", type=int, default=30)
    s = sub.add_parser("build", help="図の定義 (.py / .yaml / .html) -> .drawio (生成後に lint も走る)")
    s.add_argument("spec")
    s.add_argument("-o", "--out")
    s.add_argument("--png", help="続けて PNG も書き出す")
    s = sub.add_parser("lint", help="図の定義か .drawio を検査する")
    s.add_argument("target")
    s.add_argument("--json", action="store_true")
    s.add_argument("--strict-geometry", action="store_true", help="線の交差・接触・重複、検査不能な経路があれば失敗する")
    s = sub.add_parser("import", help=".drawio -> YAML (draw.io での手直しを残す)")
    s.add_argument("drawio")
    s.add_argument("-o", "--out", required=True)
    s = sub.add_parser("convert", help="図の定義 -> YAML")
    s.add_argument("spec")
    s.add_argument("-o", "--out", required=True)
    s = sub.add_parser("render", help=".drawio -> PNG / SVG / PDF (draw.io Desktop)")
    s.add_argument("drawio")
    s.add_argument("-o", "--out")
    s.add_argument("--scale", type=float, default=2)

    s = sub.add_parser("edit", help="YAML の正本をコマンドで編集する")
    s.add_argument("spec")
    ops = s.add_subparsers(dest="op", required=True)
    o = ops.add_parser("add-node")
    o.add_argument("id"); o.add_argument("--icon", required=True); o.add_argument("--label")
    o.add_argument("--parent"); o.add_argument("--after")
    o = ops.add_parser("add-group")
    o.add_argument("id"); o.add_argument("--type", required=True); o.add_argument("--label")
    o.add_argument("--parent"); o.add_argument("--after"); o.add_argument("--layout", choices=["row", "column", "grid"])
    o = ops.add_parser("remove"); o.add_argument("id")
    o = ops.add_parser("move"); o.add_argument("id"); o.add_argument("--parent"); o.add_argument("--after")
    o = ops.add_parser("set"); o.add_argument("id"); o.add_argument("pairs", nargs="+", metavar="key=value")
    o = ops.add_parser("connect")
    o.add_argument("src"); o.add_argument("dst"); o.add_argument("--label")
    o.add_argument("--dashed", action="store_true"); o.add_argument("--arrow", choices=["end", "both", "none"], default="end")
    o.add_argument("--exit", choices=SIDES); o.add_argument("--entry", choices=SIDES)
    o = ops.add_parser("set-edge")
    o.add_argument("src"); o.add_argument("dst"); o.add_argument("pairs", nargs="+", metavar="key=value")
    o = ops.add_parser("disconnect"); o.add_argument("src"); o.add_argument("dst")
    o = ops.add_parser("relayout"); o.add_argument("id", nargs="?")

    args = p.parse_args(argv)
    return {"doctor": cmd_doctor, "icons": cmd_icons, "build": cmd_build, "lint": cmd_lint, "import": cmd_import,
            "convert": cmd_convert, "render": cmd_render, "edit": cmd_edit}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
