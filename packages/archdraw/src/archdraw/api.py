"""Python から図を組み立てる API。

    from archdraw import Diagram

    d = Diagram("3層Web")
    users = d.node("Users", "利用者")
    with d.group("aws-cloud"):
        cf = d.node("CloudFront", "CloudFront")
        s3 = d.node("S3", "静的アセット")
    users.to(cf, "HTTPS")      # ラベル・線種は to() で付ける
    cf >> s3                   # ラベル無しの実線は >> でもよい。a >> [b, c] で分岐、[a, b] >> c で集約
    d.save("web.drawio")

組み立てた結果は YAML と同じ辞書 (d.doc) になり、配置・検査・書き出しは同じ道を通る。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

CREATED: list["Diagram"] = []  # `archdraw build x.py` が、スクリプトの中で作った図を拾うため


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class Ref:
    """要素 (node / group) の参照。線の端に使う。"""

    def __init__(self, d: "Diagram", iid: str):
        self._d, self.id = d, iid

    def to(self, dst, label: str = "", *, dashed: bool = False, arrow: str = "end", exit: str | None = None,
           entry: str | None = None):
        """自分から dst へ線を引き、dst を返す (a.to(b).to(c) とつなげられる)。dst はリストでもよい (分岐)。"""
        for t in (dst if isinstance(dst, (list, tuple)) else [dst]):
            self._d.edge(self, t, label, dashed=dashed, arrow=arrow, exit=exit, entry=entry)
        return dst

    def __rshift__(self, dst):
        return self.to(dst)

    def __rrshift__(self, srcs):  # [a, b] >> c
        for s in srcs:
            s.to(self)
        return self

    def __repr__(self):
        return f"<{self.id}>"


class Group(Ref):
    """グループ。with の中で作った要素がこのグループの子になる。"""

    def __init__(self, d: "Diagram", iid: str, children: list):
        super().__init__(d, iid)
        self._children = children

    def __enter__(self):
        self._d._stack.append(self._children)
        return self

    def __exit__(self, *exc):
        self._d._stack.pop()


class Diagram:
    def __init__(self, title: str, *, layout: str | None = None, icon_style: str | None = None,
                 page_aspect: float | None = None, notes: list[str] | None = None):
        """layout="auto" なら最上位の要素を線のつながりから並べる (既定は書いた順に横)。"""
        self.doc: dict = {"title": title, "items": [], "edges": []}
        if layout:
            self.doc["layout"] = layout
        if icon_style:
            self.doc["icon_style"] = icon_style
        if page_aspect:
            self.doc["page_aspect"] = page_aspect
        if notes:
            self.doc["notes"] = list(notes)
        self._stack: list[list] = [self.doc["items"]]
        self._ids: set[str] = set()
        CREATED.append(self)

    # ---------------- 要素 ----------------
    def _id(self, want: str | None, *hints: str) -> str:
        if want:
            if want in self._ids:
                raise ValueError(f"id '{want}' が重複している")
            self._ids.add(want)
            return want
        base = next((s for s in map(_slug, hints) if s), "item")
        iid, n = base, 2
        while iid in self._ids:
            iid, n = f"{base}-{n}", n + 1
        self._ids.add(iid)
        return iid

    def node(self, icon: str, label: str = "", *, id: str | None = None, border: str | None = None) -> Ref:
        """アイコン付きの要素。icon は AWS の公式名 (略称可) か、取り込んだセットの prefix:name。"""
        iid = self._id(id, label, icon.split(":")[-1])
        raw = {"id": iid, "icon": icon, "label": label}
        if border:
            raw["border"] = border
        self._stack[-1].append(raw)
        return Ref(self, iid)

    def group(self, kind: str = "generic", label: str = "", *, layout: str = "row", cols: int | None = None,
              flow: str | None = None, id: str | None = None) -> Group:
        """枠。kind は generic / layout (枠を描かない並べ替え用) / AWS の種類 (aws-cloud, region, vpc, az ...)。

        layout: row (書いた順に横) / column (縦) / grid (cols 列) / auto (線のつながりから。上流 → 下流に並べる)。
        """
        iid = self._id(id, label, kind)
        raw = {"id": iid, "group": kind, "children": []}
        if label:
            raw["label"] = label
        if layout != "row":
            raw["layout"] = layout
        if cols:
            raw["cols"] = cols
        if flow:
            raw["flow"] = flow
        self._stack[-1].append(raw)
        return Group(self, iid, raw["children"])

    def row(self, *, id: str | None = None) -> Group:
        """枠を描かずに、中身を横に並べる。"""
        return self.group("layout", id=id)

    def column(self, *, id: str | None = None) -> Group:
        """枠を描かずに、中身を縦に並べる。"""
        return self.group("layout", layout="column", id=id)

    def edge(self, src: Ref, dst: Ref, label: str = "", *, dashed: bool = False, arrow: str = "end",
             exit: str | None = None, entry: str | None = None) -> Ref:
        e = {"from": src.id, "to": dst.id}
        if label:
            e["label"] = label
        if dashed:
            e["dashed"] = True
        if arrow != "end":
            e["arrow"] = arrow
        if exit:
            e["exit"] = exit
        if entry:
            e["entry"] = entry
        self.doc["edges"].append(e)
        return dst

    def note(self, text: str):
        """図の下に「※」付きで並ぶ前提・注記。"""
        self.doc.setdefault("notes", []).append(text)

    # ---------------- 出力 ----------------
    def model(self, lib=None):
        from archdraw.icons import Library
        from archdraw.model import from_dict
        return from_dict(self.doc, lib or Library(), self.doc["title"])

    def lint(self, lib=None):
        from archdraw.lint import lint
        return lint(self.model(lib), layout_first=True)

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.doc, sort_keys=False, allow_unicode=True, width=120, default_flow_style=None)

    def save(self, path: str | Path, lib=None) -> Path:
        """拡張子で決める: .drawio (編集用) / .yaml / .png .svg .pdf (draw.io Desktop で書き出す)。"""
        from archdraw.drawio import to_drawio
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in (".yaml", ".yml"):
            path.write_text(self.to_yaml(), encoding="utf-8")
            return path
        xml = to_drawio(self.model(lib))
        if path.suffix == ".drawio":
            path.write_text(xml, encoding="utf-8")
            return path
        from archdraw.render import export
        tmp = path.with_suffix(".drawio")
        tmp.write_text(xml, encoding="utf-8")
        return export(tmp, path)
