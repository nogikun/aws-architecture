""".drawio の書き出しと読み込み。

書き出し: 配置済みのモデル -> mxGraph XML。経路探索の結果は接続口と waypoint として固定する。
読み込み: draw.io で手直しした図 -> モデル (座標は draw.io 上の実物。自動配置し直さない)。
"""

from __future__ import annotations

import base64
import re
import urllib.parse
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

from archdraw.icons import ICON_STYLES, Icon, Library, is_set_ref, tile
from archdraw.layout import icon_box, label_size, layout, node_box_size, route_box
from archdraw.model import GROUP_ICON, ICON, Edge, GroupSpec, Item, Model, spec_of
from archdraw.route import port_style


def group_style(spec: GroupSpec, has_icon: bool, endpoint: bool = False) -> str:
    if endpoint:
        return ("rounded=1;whiteSpace=wrap;html=1;container=0;fillColor=#FFFFFF;strokeColor=#7D8998;dashed=0;"
                "fontColor=#232F3E;fontSize=12;align=center;verticalAlign=middle;spacing=8;")
    if spec.stroke == "none":
        return "rounded=0;html=1;container=1;collapsible=0;recursiveResize=0;fillColor=none;strokeColor=none;pointerEvents=0;"
    return ";".join([
        "rounded=0", "whiteSpace=wrap", "html=1", "container=1", "collapsible=0", "recursiveResize=0",
        f"fillColor={spec.fill}", f"strokeColor={spec.stroke}", f"dashed={int(spec.dashed)}",
        f"fontColor={spec.stroke if spec.stroke != '#7AA116' else '#248814'}", "fontSize=12", "fontStyle=1",
        "verticalAlign=top", f"align={spec.align}", f"spacingLeft={40 if has_icon else 8}", "spacingTop=4",
        "pointerEvents=0",
    ]) + ";"


def node_style(icon: Icon) -> str:
    return ("shape=image;html=1;aspect=fixed;imageAspect=0;verticalLabelPosition=bottom;verticalAlign=top;"
            f"labelBackgroundColor=none;fontSize=12;fontColor=#232F3E;image={icon.data};")


def edge_style(e: Edge) -> str:
    s = ("edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;"
         "strokeColor=#545B64;strokeWidth=2;fontSize=11;fontColor=#232F3E;labelBackgroundColor=#FFFFFF;")
    s += {"end": "endArrow=block;endFill=1;startArrow=none;", "both": "endArrow=block;endFill=1;startArrow=block;startFill=1;",
          "none": "endArrow=none;startArrow=none;"}.get(e.arrow, "endArrow=block;endFill=1;")
    return s + ("dashed=1;" if e.dashed else "")


def to_drawio(m: Model, *, layout_done: bool = False) -> str:
    if not m.lib:
        raise SystemExit("アイコンライブラリが必要 (doctor を実行)")
    if not layout_done:
        layout(m)
    mxfile = ET.Element("mxfile", host="arch-builder")
    diagram = ET.SubElement(mxfile, "diagram", id="arch", name=m.title)
    if m.icon_style != "plain":
        diagram.set("arch_icon_style", m.icon_style)
    # 用紙は図全体を含み、既定は16:9。必要なら arch.yaml で比率を指定できる。
    right = max((m.items[r].box[0] + m.items[r].box[2] for r in m.roots), default=0) + 40
    bottom = max((m.items[r].box[1] + m.items[r].box[3] for r in m.roots), default=0) + 40 + 24 * bool(m.notes)
    aspect = m.page_aspect or 16 / 9
    pw = max(right, bottom * aspect)
    model = ET.SubElement(diagram, "mxGraphModel", dx="1400", dy="900", grid="1", gridSize="10", guides="1",
                          tooltips="1", connect="1", arrows="1", fold="1", page="1", pageScale="1",
                          pageWidth=_f(pw), pageHeight=_f(pw / aspect),
                          background="#FFFFFF", math="0", shadow="0", darkMode="0")
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    def vertex(iid, label, style, parent, geo, **meta):
        obj = ET.SubElement(root, "object", id=iid, label=_html_label(label), **meta)
        cell = ET.SubElement(obj, "mxCell", style=style, vertex="1", parent=parent)
        ET.SubElement(cell, "mxGeometry", x=_f(geo[0]), y=_f(geo[1]), width=_f(geo[2]), height=_f(geo[3]),
                      **{"as": "geometry"})

    for it in m.walk():
        parent = it.parent or "1"
        px, py = (m.items[it.parent].box[:2] if it.parent else (0, 0))
        if it.kind == "group":
            spec = spec_of(it.group)
            gi = m.lib.group_icon(spec.icon) if spec.icon else None
            x, y, w, h = it.box
            endpoint = (it.group == "generic" and not it.children
                        and any(it.id in (e.src, e.dst) for e in m.edges))
            vertex(it.id, it.label or spec.label, group_style(spec, bool(gi), endpoint), parent, (x - px, y - py, w, h),
                   arch_kind="group", arch_group=it.group, arch_flow=it.flow or "")
            if gi:
                vertex(f"{it.id}__icon", "", node_style(gi) + "movable=0;resizable=0;deletable=0;editable=0;",
                       it.id, (0, 0, GROUP_ICON, GROUP_ICON), arch_kind="group-icon")
        else:
            if not it.raw_icon:
                raise SystemExit(f"アイコンを解決できない: {it.id} icon={it.icon!r} (lint で候補を確認)")
            x, y, w, h = icon_box(it)
            icon = tile(it.raw_icon) if m.icon_style == "tile" and it.raw_icon.kind == "set" else it.raw_icon
            vertex(it.id, it.label, node_style(icon), parent, (x - px, y - py, w, h),
                   arch_kind="node", arch_icon=it.raw_icon.name)
    if m.notes:  # 前提・注記は図の下に並べる。図の要素ではないので lint や経路探索の対象にしない
        bottom = max((m.items[r].box[1] + m.items[r].box[3] for r in m.roots), default=0)
        lines = "<br>".join(f"※ {n}" for n in m.notes)
        # 幅は図の幅に合わせる (用紙の 16:9 の幅にすると、PNG の右に大きな空白が出る)。長い注記は折り返す
        nw = max(right - 80, 400)
        rows = sum(-(-label_size(f"※ {n}")[0] * 14 / 12 // nw) or 1 for n in m.notes)
        vertex("__notes", lines, "text;html=1;align=left;verticalAlign=top;fontSize=14;fontColor=#545B64;"
               "whiteSpace=wrap;", "1", (40, bottom + 24, nw, 20 * rows + 8), arch_kind="note")
    for i, e in enumerate(m.edges):
        style = edge_style(e)
        if e.path:  # 経路探索の結果を、接続口と waypoint として固定する
            style += (port_style(route_box(m.items[e.src]), e.sides[0], "exit", e.fracs[0])
                      + port_style(route_box(m.items[e.dst]), e.sides[1], "entry", e.fracs[1]))
        obj = ET.SubElement(root, "object", id=f"e{i}__{e.src}__{e.dst}", label=_html_label(e.label),
                            arch_exit=e.exit or "", arch_entry=e.entry or "")
        cell = ET.SubElement(obj, "mxCell", style=style, edge="1", parent="1", source=e.src, target=e.dst)
        geo = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        if e.path and len(e.path) > 2:
            arr = ET.SubElement(geo, "Array", **{"as": "points"})
            for x, y in e.path[1:-1]:
                ET.SubElement(arr, "mxPoint", x=_f(x), y=_f(y))
    ET.indent(mxfile)
    return ET.tostring(mxfile, encoding="unicode")


def _f(v: float) -> str:
    return str(round(v, 1)).removesuffix(".0")


def _html_label(s: str) -> str:
    return s.replace("\n", "<br>")


# ---------------------------------------------------------------------------
# .drawio 取り込み (draw.io で手直しした図を正本へ戻す)
# ---------------------------------------------------------------------------
def read_graph(path: Path) -> ET.Element:
    root = ET.parse(path).getroot()
    if root.tag == "mxGraphModel":
        return root
    diagram = root.find("diagram")
    if diagram is None:
        raise SystemExit(f"{path}: <diagram> が無い")
    g = diagram.find("mxGraphModel")
    if g is not None:
        return g
    raw = zlib.decompress(base64.b64decode(diagram.text.strip()), -15)  # 圧縮保存された .drawio
    return ET.fromstring(urllib.parse.unquote(raw.decode()))


def _style_map(style: str) -> dict[str, str]:
    out = {}
    for part in (style or "").split(";"):
        if part:
            k, _, v = part.partition("=")
            out[k] = v
    return out


def _plain(label: str) -> str:
    s = re.sub(r"<br\s*/?>|</div>\s*<div>", "\n", label or "")
    s = re.sub(r"<[^>]+>", "", s)
    return s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()


def load_drawio(path: Path, lib: Library | None) -> Model:
    g = read_graph(path)
    diagram = ET.parse(path).getroot().find("diagram")
    m = Model(diagram.get("name", path.stem) if diagram is not None else path.stem, {}, [], [], lib)
    graph = g
    if graph is not None and graph.get("pageWidth") and graph.get("pageHeight"):
        try:
            aspect = float(graph.get("pageWidth")) / float(graph.get("pageHeight"))
        except (ValueError, ZeroDivisionError):
            aspect = None
        if aspect is not None and 1.0 <= aspect <= 2.2:
            m.page_aspect = round(aspect, 4)
    m.from_drawio = True  # 座標は draw.io 上の実物。lint で自動配置し直さない
    if diagram is not None and diagram.get("arch_icon_style") in ICON_STYLES:
        m.icon_style = diagram.get("arch_icon_style")
    cells = []  # (id, attrs, mxCell)
    for el in g.find("root"):
        if el.tag == "mxCell":
            cells.append((el.get("id"), {"label": el.get("value", "")}, el))
        else:  # object / UserObject
            c = el.find("mxCell")
            cells.append((el.get("id"), dict(el.attrib), c))
    known = {cid for cid, _, c in cells if c is not None and c.get("vertex") == "1"}
    for cid, attrs, c in cells:
        if attrs.get("arch_kind") == "note":
            m.notes = [re.sub(r"^※\s*", "", ln) for ln in _plain(attrs.get("label", "")).split("\n") if ln.strip()]
            continue
        if c is None or c.get("vertex") != "1" or attrs.get("arch_kind") == "group-icon":
            continue
        st = _style_map(c.get("style", ""))
        geo = c.find("mxGeometry")
        gx = [float(geo.get(k, 0)) for k in ("x", "y", "width", "height")] if geo is not None else [0, 0, 0, 0]
        parent = c.get("parent")
        parent = parent if parent in known else None
        label = _plain(attrs.get("label", ""))
        kind = attrs.get("arch_kind")
        if kind == "group" or (not kind and st.get("container") == "1"):
            it = Item(cid, "group", parent, label, group=attrs.get("arch_group", "generic"), pos=gx[:2], size=gx[2:])
            it.flow = attrs.get("arch_flow") or None
            if it.label == spec_of(it.group).label:
                it.label = ""
        elif st.get("image", "").startswith("data:"):
            ic = lib.by_data(st["image"]) if lib else None
            if ic is None and lib and is_set_ref(attrs.get("arch_icon") or ""):  # 取り込んだセットは名前で引き直す
                ic = lib.resolve(attrs["arch_icon"])
            it = Item(cid, "node", parent, label, icon=attrs.get("arch_icon") or (ic.name if ic else None))
            it.raw_icon = ic
            if ic is None:
                it.unmanaged = "公式ライブラリに無い画像"
        else:
            it = Item(cid, "node", parent, label)
            it.unmanaged = f"管理外の図形 (style={c.get('style', '')[:40]})"
        it._geo = gx
        m.items[cid] = it
    # 親子を張り、絶対座標を出す
    order = [cid for cid, _, c in cells if cid in m.items]
    for cid in order:
        it = m.items[cid]
        (m.items[it.parent].children if it.parent else m.roots).append(cid)
    for it in m.walk():
        px, py = m.items[it.parent].box[:2] if it.parent else (0, 0)
        x, y, w, h = it._geo
        it.box = (px + x, py + y, w, h)
    # node の box を「アイコン + ラベル」の確保枠に揃える (yaml から作ったときと同じ意味にする)
    for it in m.items.values():
        if it.kind == "node":
            x, y, w, h = it.box
            it.icon_wh = (w, h)
            bw, bh = node_box_size(it)
            it.box = (x + w / 2 - bw / 2, y, bw, h + bh - ICON)
            if it.parent:  # アイコンの中心が親の枠線の上にあれば、枠線上に置いたものとして扱う
                px, py, pw, ph = m.items[it.parent].box
                cx, cy = x + w / 2, y + h / 2
                near = {"top": abs(cy - py), "bottom": abs(cy - py - ph), "left": abs(cx - px), "right": abs(cx - px - pw)}
                sd = min(near, key=near.get)
                if near[sd] <= 4:
                    it.border = sd
    for cid, attrs, c in cells:
        if c is not None and c.get("edge") == "1":
            s, t = c.get("source"), c.get("target")
            if not s or not t:
                m.problems.append(("E-EDGE", f"接続線 {cid} の端が図形に繋がっていない", cid))
                continue
            st = _style_map(c.get("style", ""))
            arrow = "none" if st.get("endArrow") == "none" and st.get("startArrow") in (None, "none") else (
                "both" if st.get("startArrow") not in (None, "none") else "end")
            label = _plain(attrs.get("label", "") or c.get("value", ""))
            e = Edge(s, t, label, st.get("dashed") == "1", arrow,
                     attrs.get("arch_exit") or None, attrs.get("arch_entry") or None)
            if s in m.items and t in m.items:
                e.path = _drawio_path(m.items[s], m.items[t], st, c.find("mxGeometry"))
                if "exitX" in st and "entryX" in st:
                    ports = [_side_frac(st, "exit"), _side_frac(st, "entry")]
                    e.sides, e.fracs = tuple(p[0] for p in ports), tuple(p[1] for p in ports)
            m.edges.append(e)
    return m


def _side_frac(st: dict, prefix: str) -> tuple[str, float]:
    """draw.io の exitX/exitY から (面, 面の中の位置) を読む。"""
    x, y = float(st[f"{prefix}X"]), float(st[f"{prefix}Y"])
    if y in (0.0, 1.0) and 0 < x < 1:
        return ("top" if y == 0 else "bottom"), x
    return ("left" if x == 0 else "right"), y


def _drawio_path(src: Item, dst: Item, st: dict, geo) -> list | None:
    """接続口 + waypoint から実際の折れ線を復元する。draw.io 任せの経路 (waypoint 無し) は復元できないので None。"""
    pts = geo.findall("Array/mxPoint") if geo is not None else []
    if "exitX" not in st or "entryX" not in st:
        return None

    def port(it, prefix):
        x, y, w, h = route_box(it).icon
        return (x + float(st[f"{prefix}X"]) * w + float(st.get(f"{prefix}Dx", 0)),
                y + float(st[f"{prefix}Y"]) * h + float(st.get(f"{prefix}Dy", 0)))

    path = [port(src, "exit")] + [(float(p.get("x", 0)), float(p.get("y", 0))) for p in pts] + [port(dst, "entry")]
    # draw.io で要素を動かすと waypoint が取り残されて斜めになる。そのときは検査しない
    if any(abs(a[0] - b[0]) > 0.5 and abs(a[1] - b[1]) > 0.5 for a, b in zip(path, path[1:])):
        return None
    return path
