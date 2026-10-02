"""図のモデル (要素・グループ・接続線) と、辞書 / YAML との相互変換。

モデルは表記に依存しない。Python API (api.py)・YAML・draw.io (drawio.py) はどれもこのモデルを作る。
グループの種類は GROUPS に登録する。core は generic と layout だけを持ち、AWS などの種類は packs/ が足す。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from archdraw.icons import ICON_STYLES, Icon, Library

ANY = "*"
LAYOUT_ONLY = "layout"
SIDES = ("top", "right", "bottom", "left")

# レイアウト定数 (px)
ICON = 48
NODE_W = 120          # アイコン + ラベルに確保する枠の幅
LABEL_LINE = 16
PAD_TOP = 48          # グループ見出し (32px アイコン + 余白)
PAD_SIDE = 24
PAD_BOTTOM = 24
GAP = 32
GROUP_ICON = 32
STRETCH_MAX = 1.5     # 枠を中身に必要な大きさの何倍まで広げてよいか (面積比。2 倍以上は error)


@dataclass(frozen=True)
class GroupSpec:
    label: str
    stroke: str
    fill: str = "none"
    dashed: bool = False
    icon: str | None = None   # 見出しのアイコン (アイコンライブラリのグループアイコン名)
    parents: tuple = (None,)  # 置いてよい親グループの種類。None はキャンバス直下、"*" はどこでも
    align: str = "left"
    flow: str | None = None   # 中の流れの向き (down / right)。書かなければ親から継ぐ。最上位は right
    borders: tuple = ()       # 直下に置くと枠線の上に乗るアイコン: ((アイコン名, 辺), ...)


# 種類 -> 見た目と置き場所。packs/ が import 時に足す
GROUPS: dict[str, GroupSpec] = {
    "generic": GroupSpec("", "#7D8998", dashed=True, parents=(ANY,)),
    # 枠を描かない並べ替え専用の箱。規約チェックでは存在しないものとして扱う
    LAYOUT_ONLY: GroupSpec("", "none", parents=(ANY,)),
}


def spec_of(group: str | None) -> GroupSpec:
    return GROUPS.get(group or "generic", GROUPS["generic"])


@dataclass
class Item:
    id: str
    kind: str                    # "node" | "group"
    parent: str | None
    label: str = ""
    icon: str | None = None      # node のみ
    group: str | None = None     # group の種類
    layout: str = "row"          # row | column | grid | auto (線のつながりから並べる)
    cols: int = 2
    pos: list | None = None      # 親からの相対座標 [x, y] (手動配置)
    size: list | None = None     # [w, h] (グループの手動サイズ)
    children: list = field(default_factory=list)
    box: tuple = (0, 0, 0, 0)    # 絶対座標 (x, y, w, h)。レイアウト後に入る
    raw_icon: Icon | None = None
    icon_wh: tuple = (ICON, ICON)  # 実際のアイコン寸法 (.drawio で縮められていないか見る)
    unmanaged: str | None = None  # draw.io 上で追加された未知要素の説明
    flow: str | None = None       # グループの流れの向き: down (上から入って下へ出る) | right (左から入って右へ出る)
    border: str | None = None     # 親の枠線上に置く辺: top | right | bottom | left ("none" で既定を打ち消す)


@dataclass
class Edge:
    src: str
    dst: str
    label: str = ""
    dashed: bool = False
    arrow: str = "end"           # end | both | none
    exit: str | None = None      # 出口の辺を固定する: top | right | bottom | left (既定は経路探索に任せる)
    entry: str | None = None     # 入口の辺を固定する
    path: list | None = None     # 絶対座標の折れ線 (経路探索の結果 / .drawio の waypoint)
    sides: tuple = (None, None)  # 実際に使った (出口, 入口) の面
    fracs: tuple = (0.5, 0.5)    # 面の中の位置 (0〜1。上下の面なら左から、左右の面なら上から)


@dataclass
class Model:
    title: str
    items: dict[str, Item]
    roots: list[str]
    edges: list[Edge]
    lib: Library | None = None
    problems: list = field(default_factory=list)  # 読み込み時点の問題 (code, msg, id)
    from_drawio: bool = False  # True なら box は draw.io 上の実座標 (自動配置し直さない)
    notes: list = field(default_factory=list)  # 図の下に書く前提・注記
    page_aspect: float | None = None  # 任意の用紙比率。未指定なら 16:9
    icon_style: str = "plain"  # 取り込んだセットのアイコンの見せ方: plain (そのまま) / tile (白い角丸タイルに載せる)
    layout: str = "row"        # 最上位の並べ方: row (書いた順に横) / auto (線のつながりから)

    def ancestors(self, iid: str):
        p = self.items[iid].parent
        while p:
            yield self.items[p]
            p = self.items[p].parent

    def walk(self, ids=None):
        for i in (self.roots if ids is None else ids):
            yield self.items[i]
            yield from self.walk(self.items[i].children)


def on_border(it: Item) -> bool:
    return it.kind == "node" and it.border in SIDES


# ---------------------------------------------------------------------------
# 辞書 (YAML の中身) <-> モデル
# ---------------------------------------------------------------------------
def from_dict(doc: dict, lib: Library | None, default_title: str = "diagram") -> Model:
    m = Model(doc.get("title", default_title), {}, [], [], lib)
    raw_aspect = doc.get("page_aspect")
    if raw_aspect is not None:
        try:
            if isinstance(raw_aspect, bool):
                raise ValueError
            m.page_aspect = float(raw_aspect)
        except (TypeError, ValueError):
            m.problems.append(("E-PAGE-ASPECT", "page_aspect は 1.0〜2.2 の数値で指定", None))
        else:
            if not 1.0 <= m.page_aspect <= 2.2:
                m.problems.append(("E-PAGE-ASPECT", "page_aspect は 1.0〜2.2 の範囲で指定", None))
                m.page_aspect = None
    m.layout = doc.get("layout", "row")
    if m.layout not in ("row", "auto"):
        m.problems.append(("E-LAYOUT", "最上位の layout は row / auto のどちらか", None))
        m.layout = "row"
    m.icon_style = doc.get("icon_style", "plain")
    if m.icon_style not in ICON_STYLES:
        m.problems.append(("E-ICON-STYLE", f"icon_style は {' / '.join(ICON_STYLES)} のどれか", None))
        m.icon_style = "plain"

    def add(raw: dict, parent: str | None):
        iid = str(raw.get("id") or "")
        if not iid:
            m.problems.append(("E-ID", f"id が無い要素がある: {raw}", None))
            return
        if iid in m.items:
            m.problems.append(("E-ID", f"id '{iid}' が重複している", iid))
            return
        is_group = "group" in raw or "children" in raw
        it = Item(iid, "group" if is_group else "node", parent, str(raw.get("label", "")),
                  raw.get("icon"), raw.get("group", "generic") if is_group else None,
                  raw.get("layout", "row"), int(raw.get("cols", 2)), raw.get("pos"), raw.get("size"))
        it.border = raw.get("border")
        it.flow = raw.get("flow")
        m.items[iid] = it
        (m.items[parent].children if parent else m.roots).append(iid)
        for c in raw.get("children") or []:
            add(c, iid)

    for raw in doc.get("items") or []:
        add(raw, None)
    for e in doc.get("edges") or []:
        m.edges.append(Edge(str(e["from"]), str(e["to"]), str(e.get("label", "")),
                            bool(e.get("dashed", False)), e.get("arrow", "end"), e.get("exit"), e.get("entry")))
    # 「- 前提: ...」は YAML では辞書になる。書いたとおりの 1 行に戻す
    m.notes = [n if isinstance(n, str) else ", ".join(f"{k}: {v}" for k, v in n.items()) for n in doc.get("notes") or []]
    resolve_icons(m)
    return m


def resolve_icons(m: Model):
    """アイコンを引き、枠線上に乗せるアイコン (VPC 直下の IGW など) に既定の辺を付ける。"""
    if m.lib:
        for it in m.items.values():
            if it.kind == "node" and it.icon and not it.raw_icon:
                it.raw_icon = m.lib.resolve(it.icon)
    for it in m.items.values():
        if it.kind == "node" and it.border is None and it.raw_icon and it.parent:
            it.border = dict(spec_of(m.items[it.parent].group).borders).get(it.raw_icon.name)


def to_dict(m: Model) -> dict:
    def ser(iid):
        it = m.items[iid]
        d = {"id": it.id}
        if it.kind == "group":
            d["group"] = it.group
            if it.label:
                d["label"] = it.label
            if it.layout != "row":
                d["layout"] = it.layout
            if it.layout == "grid":
                d["cols"] = it.cols
            if it.flow:
                d["flow"] = it.flow
        else:
            d["icon"] = it.icon
            d["label"] = it.label
            if it.border:
                d["border"] = it.border
        if it.pos:
            d["pos"] = [round(v) for v in it.pos]
        if it.size:
            d["size"] = [round(v) for v in it.size]
        if it.kind == "group":
            d["children"] = [ser(c) for c in it.children]
        return d

    edges = []
    for e in m.edges:
        d = {"from": e.src, "to": e.dst}
        if e.label:
            d["label"] = e.label
        if e.dashed:
            d["dashed"] = True
        if e.arrow != "end":
            d["arrow"] = e.arrow
        for k in ("exit", "entry"):
            if getattr(e, k):
                d[k] = getattr(e, k)
        edges.append(d)
    doc = {"title": m.title, "items": [ser(r) for r in m.roots], "edges": edges}
    if m.page_aspect is not None:
        doc["page_aspect"] = m.page_aspect
    if m.icon_style != "plain":
        doc["icon_style"] = m.icon_style
    if m.layout != "row":
        doc["layout"] = m.layout
    if m.notes:
        doc["notes"] = m.notes
    return doc


def load_yaml(path: Path, lib: Library | None) -> Model:
    return from_dict(yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}, lib, path.stem)


def dump_yaml(m: Model) -> str:
    return yaml.safe_dump(to_dict(m), sort_keys=False, allow_unicode=True, width=120, default_flow_style=None)
