"""配置 (入れ子の箱詰め) と接続口の決定。経路の探索そのものは route.py。

自動配置は「子を順に並べる」。pos / size があればそれを優先する (draw.io での手直しを保つ)。
"""

from __future__ import annotations

from archdraw.model import (GAP, ICON, GROUP_ICON, LABEL_LINE, LAYOUT_ONLY, NODE_W, PAD_BOTTOM, PAD_SIDE, PAD_TOP,
                            SIDES, STRETCH_MAX, Edge, Item, Model, on_border, spec_of)
from archdraw.route import Box, route_all


def label_size(text: str) -> tuple[float, float]:
    lines = text.split("\n") if text else []
    width = max((sum(14 if ord(c) > 0x2E7F else 7.5 for c in ln) for ln in lines), default=0)
    return width, len(lines) * LABEL_LINE


def node_box_size(it: Item) -> tuple[float, float]:
    lw, lh = label_size(it.label)
    return max(NODE_W, lw + 8), ICON + 8 + lh


def measure(m: Model, iid: str) -> tuple[float, float]:
    """箱の (w, h) を返し、子の相対位置を it._rel に入れる。"""
    it = m.items[iid]
    if it.kind == "node":
        return node_box_size(it)
    if (it.group == "generic" and not it.children
            and any(it.id in (e.src, e.dst) for e in m.edges)):
        # 接続済み generic leaf はコンテナではなく、ラベル付きの外部端点として小さく描く。
        lw, lh = label_size(it.label)
        return max(140, lw + 24), max(64, lh + 24)
    sizes = [(c, *measure(m, c)) for c in it.children]
    edge_nodes = [s for s in sizes if on_border(m.items[s[0]]) and not m.items[s[0]].pos]
    sizes = [s for s in sizes if s not in edge_nodes]
    auto = [s for s in sizes if not m.items[s[0]].pos]
    manual = [s for s in sizes if m.items[s[0]].pos]
    # 同じ行 (row) の子グループは高さ、列 (column) の子グループは幅を揃える
    grp = [s for s in auto if m.items[s[0]].kind == "group"]
    # ただし引き伸ばすのは 1.5 倍まで。それ以上は中身が少ないのに枠だけ広い「スカスカの枠」になる (lint の N-SPARSE)
    if it.layout == "row" and grp:
        hmax = max(s[2] for s in grp)
        auto = [(c, w, hmax if m.items[c].kind == "group" and hmax <= h * STRETCH_MAX else h) for c, w, h in auto]
    if it.layout == "column" and grp:
        wmax = max(s[1] for s in grp)
        auto = [(c, wmax if m.items[c].kind == "group" and wmax <= w * STRETCH_MAX else w, h) for c, w, h in auto]

    rel: dict[str, tuple] = {}
    right = bottom = 0.0
    for c, w, h in manual:
        x, y = m.items[c].pos
        if m.items[c].kind == "node":  # pos はアイコン自体の位置。確保枠はラベル分だけ左右に広い
            x -= (w - ICON) / 2
        rel[c] = (x, y, w, h)
        right, bottom = max(right, x + w), max(bottom, y + h)
    top, side, bottom_pad = (0, 0, 0) if it.group == LAYOUT_ONLY else (PAD_TOP, PAD_SIDE, PAD_BOTTOM)
    # 枠線上のアイコンは半分が内側に入り、上辺ならその下にラベルも付く。その分だけ内側の余白を広げる
    by_side = {sd: [s for s in edge_nodes if m.items[s[0]].border == sd] for sd in SIDES}
    if by_side["top"]:
        # 枠線上のアイコンの下には、戻ってくる線 (NAT -> IGW) が横に走る段をとる。狭いと下の要素の脇をかすめる
        top = max(top, ICON / 2 + max(s[2] for s in by_side["top"]) - ICON + GAP * 2)
    if by_side["bottom"]:
        bottom_pad = max(bottom_pad, ICON / 2 + GAP)
    left_pad = max([side] + [s[1] / 2 + GAP / 2 for s in by_side["left"]])
    side = max([side] + [s[1] / 2 + GAP / 2 for s in by_side["right"]])
    y0 = bottom + GAP if manual else top
    x, y = left_pad, y0
    if it.layout == "row":
        for c, w, h in auto:
            rel[c] = (x, y, w, h)
            x += w + GAP
    elif it.layout == "column":
        colw = max((s[1] for s in auto), default=0)
        for c, w, h in auto:  # 縦に並べるときは中央でそろえる (アイコンの中心が一直線になり、線が段差なくつながる)
            rel[c] = (x + (colw - w) / 2, y, w, h)
            y += h + GAP
    elif it.layout == "auto":
        rel.update(arrange_auto(m, auto, flow_of(m, it), left_pad, y0))
    else:  # grid
        cols = max(1, it.cols)
        cw = max((s[1] for s in auto), default=0)
        ch = max((s[2] for s in auto), default=0)
        for i, (c, w, h) in enumerate(auto):
            rel[c] = (left_pad + (i % cols) * (cw + GAP), y0 + (i // cols) * (ch + GAP), w, h)
    for bx, by, bw, bh in rel.values():
        right, bottom = max(right, bx + bw), max(bottom, by + bh)
    it._rel = rel
    w = max(right + side, 200 if not it.children else 0)
    h = max(bottom + bottom_pad, 120 if not it.children else 0)
    it._natural = (w, h)  # 中身そのものの大きさ。これより広げた分は _place で中央寄せに使う
    if it.group != LAYOUT_ONLY:  # 中身を中央に置いたとき、上から入る線が見出しを横切らない幅をとる
        spec = spec_of(it.group)
        w = max(w, 2 * ((40 if spec.icon else 8) + label_size(it.label or spec.label)[0] + 8))
    if it.size:
        w, h = max(w, it.size[0]), max(h, it.size[1])
    # 枠線上のアイコン: 中心を辺の線に乗せ、同じ辺に複数あれば等間隔に並べる
    for sd, group in by_side.items():
        for i, (c, bw, bh) in enumerate(group):
            f = (i + 1) / (len(group) + 1)
            if sd in ("top", "bottom"):
                rel[c] = (w * f - bw / 2, (0 if sd == "top" else h) - ICON / 2, bw, bh)
            else:
                rel[c] = ((0 if sd == "left" else w) - bw / 2, h * f - ICON / 2, bw, bh)
    return w, h


def flow_of(m: Model, it: Item) -> str:
    """枠の中の流れ (down / right)。自分か祖先の flow:、なければ種類の既定 (AWS の VPC は down)。最上位は right。"""
    for g in [it, *m.ancestors(it.id)]:
        f = g.flow if g.flow in FACES else spec_of(g.group).flow
        if f in FACES:
            return f
    return "right"


def arrange_auto(m: Model, kids: list[tuple], flow: str, x0: float, y0: float) -> dict[str, tuple]:
    """線のつながりから並べる (layout: auto)。作者は「何がどこへつながるか」だけを書けばよい。

    1. 段: 兄弟 (子の部分木ごと) の間の線から、上流 → 下流の段を決める (最長経路。循環は書いた順で切る)
    2. 段の中の順: つながる相手の位置の平均 (重心) で並べ、線の交差を減らす。同点は書いた順
    3. 置く: flow が right なら段を左 → 右の列に、down なら上 → 下の行にする。各段は中央でそろえる
    """
    ids = [c for c, _, _ in kids]
    size = {c: (w, h) for c, w, h in kids}
    order = {c: i for i, c in enumerate(ids)}
    owner = {d.id: c for c in ids for d in m.walk([c])}
    succ: dict[str, list] = {c: [] for c in ids}
    pred: dict[str, list] = {c: [] for c in ids}
    for e in m.edges:
        a, b = owner.get(e.src), owner.get(e.dst)
        if a and b and a != b and b not in succ[a]:
            succ[a].append(b)
            pred[b].append(a)
    # 段: 入ってくる線の無いものから順に確定する。循環で止まったら、書いた順で最初のものの入力を無視する
    rank, done, left = {}, set(), list(ids)
    while left:
        ready = [c for c in left if all(p in done for p in pred[c])] or [left[0]]
        for c in ready:
            rank[c] = max((rank[p] + 1 for p in pred[c] if p in done), default=0)
            done.add(c)
            left.remove(c)
    # つながりの無いものは、最初の段に書いた順で置く
    layers = [sorted([c for c in ids if rank[c] == r], key=order.get) for r in range(max(rank.values(), default=-1) + 1)]
    pos = {c: i for layer in layers for i, c in enumerate(layer)}
    for sweep in range(4):  # 前向き (上流の相手) と後ろ向き (下流の相手) を交互に
        seq = layers[1:] if sweep % 2 == 0 else layers[-2::-1]
        for layer in seq:
            nb = pred if sweep % 2 == 0 else succ

            def bary(c, nb=nb):
                ps = [pos[p] for p in nb[c]]
                return sum(ps) / len(ps) if ps else pos[c]
            layer.sort(key=lambda c: (bary(c), order[c]))
            for i, c in enumerate(layer):
                pos[c] = i
    # 置く。段の太さ (列の幅 / 行の高さ) は段の中の最大、段の中は中央でそろえる
    rel = {}
    along = 0.0
    across_max = max((sum(size[c][1 if flow == "right" else 0] for c in L) + GAP * (len(L) - 1) for L in layers), default=0)
    for layer in layers:
        thick = max(size[c][0 if flow == "right" else 1] for c in layer)
        span = sum(size[c][1 if flow == "right" else 0] for c in layer) + GAP * (len(layer) - 1)
        across = (across_max - span) / 2
        for c in layer:
            w, h = size[c]
            if flow == "right":
                rel[c] = (x0 + along + (thick - w) / 2, y0 + across, w, h)
                across += h + GAP
            else:
                rel[c] = (x0 + across, y0 + along + (thick - h) / 2, w, h)
                across += w + GAP
        along += thick + GAP * 2
    return rel


def layout(m: Model):
    if m.layout == "auto":  # 最上位も線のつながりで並べる
        roots = [(r, *measure(m, r)) for r in m.roots if not m.items[r].pos]
        for c, (x, y, w, h) in arrange_auto(m, roots, "right", 40.0, 40.0).items():
            _place(m, c, x, y, w, h)
        manual = [r for r in m.roots if m.items[r].pos]
    else:
        manual = None
    x = 40.0
    for r in (m.roots if manual is None else manual):
        it = m.items[r]
        w, h = measure(m, r)
        px, py = it.pos if it.pos else (x, 40.0)
        if it.pos and it.kind == "node":  # pos はアイコン自体の位置 (measure と同じ扱い)
            px -= (w - ICON) / 2
        _place(m, r, px, py, w, h)
        x = max(x, px + w + GAP * 2)
    route(m)


def _place(m: Model, iid: str, x, y, w, h):
    it = m.items[iid]
    it.box = (x, y, w, h)
    rel = getattr(it, "_rel", {})
    # 揃えるために引き伸ばされた枠では、アイコンだけの中身を中央に寄せる (片側に空きが偏らないように)
    dx = dy = 0.0
    inner = [c for c in rel if not on_border(m.items[c])]
    if inner and all(m.items[c].kind == "node" and not m.items[c].pos for c in inner):
        nw, nh = it._natural
        dx, dy = (w - nw) / 2, (h - nh) / 2
    for c, (rx, ry, rw, rh) in rel.items():
        shift = (0, 0) if on_border(m.items[c]) else (dx, dy)
        _place(m, c, x + rx + shift[0], y + ry + shift[1], rw, rh)


def group_need(m: Model, g: Item) -> tuple[float, float] | None:
    """枠が中身を収めるのに必要な (幅, 高さ)。中身の外接矩形 + 規定の余白 + 見出しの幅。枠線上の要素は数えない。"""
    kids = [m.items[c] for c in g.children if not on_border(m.items[c])]
    if not kids:
        return None
    x0 = min(k.box[0] for k in kids)
    y0 = min(k.box[1] for k in kids)
    x1 = max(k.box[0] + k.box[2] for k in kids)
    y1 = max(k.box[1] + k.box[3] for k in kids)
    spec = spec_of(g.group)
    header = (40 if spec.icon else 8) + label_size(g.label or spec.label)[0] + 8
    top = PAD_TOP + (ICON / 2 + LABEL_LINE * 2 + GAP if any(on_border(m.items[c]) and m.items[c].border == "top"
                                                         for c in g.children) else 0)
    return max(x1 - x0 + 2 * PAD_SIDE, 2 * header), y1 - y0 + top + PAD_BOTTOM


def icon_box(it: Item) -> tuple:
    x, y, w, _ = it.box
    iw, ih = it.icon_wh
    return (x + (w - iw) / 2, y, iw, ih)


def route_box(it: Item):
    if it.kind == "group":
        return Box(it.id, it.box, None, obstacle=False)
    ib = icon_box(it)
    lb = None
    if it.label:
        lw, lh = label_size(it.label)
        lb = (ib[0] + ib[2] / 2 - lw / 2 - 2, ib[1] + ib[3] + 2, lw + 4, lh + 2)
    return Box(it.id, ib, lb)


def group_headers(m: Model) -> list[tuple]:
    """グループの見出し (アイコン + 名前) の矩形。線が横切ると名前が読めなくなる。"""
    out = []
    for it in m.items.values():
        if it.kind != "group" or it.group == LAYOUT_ONLY:
            continue
        spec = spec_of(it.group)
        x, y, w, _ = it.box
        lw, _ = label_size(it.label or spec.label)
        if spec.align == "center":
            out.append((x + w / 2 - lw / 2 - 4, y, lw + 8, 28))
        else:
            out.append((x, y, min(w, (40 if spec.icon else 8) + lw + 8), GROUP_ICON))
    return out


FACES = {"down": ("top", "bottom"), "right": ("left", "right")}


def faces(m: Model, iid: str) -> tuple[str, str]:
    """要素の (入口の面, 出口の面)。入口と出口は向かい合わせにして、線がアイコンを一直線に通り抜けるようにする。
    流れは、いちばん近い祖先の flow: (書かなければグループの種類の既定。AWS の VPC は down) で決まる。最上位は right。"""
    for a in m.ancestors(iid):
        flow = a.flow if a.flow in FACES else spec_of(a.group).flow
        if flow in FACES:
            return FACES[flow]
    return FACES["right"]


def edge_class(e: Edge) -> tuple:
    """線の「内容」。ラベル (プロトコルなど) と線種が同じ線だけが、同じ口と幹を共有する。"""
    return (e.label, e.dashed)


def _center(r):
    return r[0] + r[2] / 2, r[1] + r[3] / 2


def _face(m: Model, iid: str, other: str, role: str) -> str:
    return _face_kind(m, iid, other, role)[0]


def _face_kind(m: Model, iid: str, other: str, role: str) -> tuple[str, str]:
    """線の端の面。role は "out" (線の出口側) か "in" (入口側)。面は「受け手の入口だから」ではなく通信の向きで決める。

    - 順方向 (外 → 中。相手が流れの下流): 流れの面 (VPC の中なら 出口 = 下 / 入口 = 上、外なら 出口 = 右 / 入口 = 左)
    - 逆方向 (中 → 外。相手が流れの上流。例: ECS → NAT、NAT → IGW): 点対称に入れ替える。出口は自分の入口の面、
      入口は相手の出口の面 (NAT → IGW は IGW の下の面に入る)。行きの線と同じ面に乗る分は、スロットで別の位置に分かれる
    - 真横 (流れの方向に重なりがある): 流れと直交する面を向かい合わせる (VPC の中なら左右、外なら上下)
    - 枠線上のゲートウェイ: 枠線に直交する面のうち、相手のいる側"""
    it = m.items[iid]
    b, o = route_box(it).icon, route_box(m.items[other]).icon
    (bx, by), (ox, oy) = _center(b), _center(o)
    if on_border(it):
        if it.border in ("top", "bottom"):
            return ("bottom" if oy > by else "top"), "border"
        return ("right" if ox > bx else "left"), "border"
    if it.kind == "group":  # グループに直接つなぐ線は、相手の方を向いた面
        if abs(ox - bx) * b[3] >= abs(oy - by) * b[2]:
            return ("right" if ox >= bx else "left"), "group"
        return ("bottom" if oy >= by else "top"), "group"
    f_in, f_out = faces(m, iid)
    down = f_in == "top"
    lo, hi = (1, 3) if down else (0, 2)  # 流れの軸 (VPC の中は y、外は x)
    other_after = o[lo] >= b[lo] + b[hi]    # 相手が自分より下流
    other_before = o[lo] + o[hi] <= b[lo]   # 相手が自分より上流
    forward = other_after if role == "out" else other_before
    reverse = other_before if role == "out" else other_after
    if forward:
        return (f_out if role == "out" else f_in), "forward"
    if reverse:
        return (f_in if role == "out" else f_out), "reverse"
    if down:
        return ("right" if ox >= bx else "left"), "side"
    return ("bottom" if oy >= by else "top"), "side"


def _outward(m: Model, iid: str) -> str:
    """流れと直交する面のうち、外側 (流れを決めている枠の中心から遠い側) の面。

    逆方向の線 (アプリ → NAT など) が、行きの線 (ALB → アプリ) と同じ面に並ぶと、入る線と出る線が隣り合って
    どちらの向きの通信か読めない。その場合だけ、逆方向の線を外側の面へ逃がす (左の AZ は左、右の AZ は右)。"""
    it = m.items[iid]
    owner = next((a for a in m.ancestors(iid) if a.flow in FACES or spec_of(a.group).flow in FACES), None)
    if owner:
        ref = owner.box
    else:
        boxes = [m.items[r].box for r in m.roots]
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        ref = (x0, y0, max(b[0] + b[2] for b in boxes) - x0, max(b[1] + b[3] for b in boxes) - y0)
    (bx, by), (cx, cy) = _center(route_box(it).icon), _center(ref)
    if faces(m, iid)[0] == "top":  # 流れが上 -> 下なら左右の面
        return "left" if bx <= cx else "right"
    return "top" if by <= cy else "bottom"


def plan_ports(m: Model) -> dict[int, tuple]:
    """線ごとの (出口の面, 入口の面), (出口の位置, 入口の位置)。

    面の中の位置 (スロット): 1 つの面を内容の違う n 種類の線が使うなら、面を 2n+1 等分し、
    2, 4, ..., 2n 番目の区間の中央に置く (n=1 は中央、n=2 は 30% と 70%)。同じ内容の線は同じスロットを共有する。
    スロットの並びは相手の位置の順 (線どうしが交差しないように)。"""
    plan: dict[int, list] = {}
    use: dict[tuple, list] = {}
    kinds = {}
    for i, e in enumerate(m.edges):
        if e.src not in m.items or e.dst not in m.items or e.src == e.dst:
            continue
        kinds[i] = (_face_kind(m, e.src, e.dst, "out"), _face_kind(m, e.dst, e.src, "in"))
    forward_faces = {(n, f) for i, (a, b) in kinds.items() for n, (f, k) in ((m.edges[i].src, a), (m.edges[i].dst, b))
                     if k == "forward"}

    for i, e in enumerate(m.edges):
        if i not in kinds:
            continue
        (sf, sk), (tf, tk) = kinds[i]
        # 逆方向の線の端が順方向の線と同じ面に乗るなら、その線の逆方向の端を両方とも外側の面へ (コの字に回す)
        if (sk == "reverse" and (e.src, sf) in forward_faces) or (tk == "reverse" and (e.dst, tf) in forward_faces):
            sf = _outward(m, e.src) if sk == "reverse" else sf
            tf = _outward(m, e.dst) if tk == "reverse" else tf
        es = e.exit or sf
        ts = e.entry or tf
        plan[i] = [(es, ts), [0.5, 0.5]]
        for node, side, other, role, k in ((e.src, es, e.dst, "out", 0), (e.dst, ts, e.src, "in", 1)):
            ox, oy = _center(route_box(m.items[other]).icon)
            use.setdefault((node, side), []).append((i, k, (role, *edge_class(e)), ox if side in ("top", "bottom") else oy))
    for (node, side), entries in use.items():
        classes: dict = {}
        for _, _, cls, coord in entries:
            classes.setdefault(cls, []).append(coord)
        if len(classes) > 1:
            # 別の内容の線をはさんで両側から集まる線を 1 つのスロットに入れると、片側の線が間の線を横切る
            # (左右の NAT から IGW へ戻る線と、IGW から ALB へ出る線)。入る線は、相手が自分のどちら側にいるかでも分ける。
            # 出る線の分岐 (ALB -> 各 AZ) は 1 つの出口から T 字に分かれる決まりなので分けない
            b = route_box(m.items[node]).icon
            mid = b[0] + b[2] / 2 if side in ("top", "bottom") else b[1] + b[3] / 2
            sgn = lambda v: (v > mid + 1) - (v < mid - 1)  # noqa: E731
            entries = [(i, k, (*cls, sgn(coord)) if cls[0] == "in" else cls, coord) for i, k, cls, coord in entries]
            classes = {}
            for _, _, cls, coord in entries:
                classes.setdefault(cls, []).append(coord)
        order = sorted(classes, key=lambda c: sum(classes[c]) / len(classes[c]))
        n = len(order)
        for i, k, cls, _ in entries:
            plan[i][1][k] = (2 * (order.index(cls) + 1) - 0.5) / (2 * n + 1)
    return {i: (sides, tuple(fr)) for i, (sides, fr) in plan.items()}


def route(m: Model):
    boxes = {it.id: route_box(it) for it in m.items.values() if it.kind == "node" or
             any(it.id in (e.src, e.dst) for e in m.edges)}
    plan = plan_ports(m)
    todo = [i for i in plan if m.edges[i].src in boxes and m.edges[i].dst in boxes]
    # 短い線から引く: 近い要素どうしの素直な線を先に確定させ、長い線に迂回させる
    todo.sort(key=lambda i: abs(boxes[m.edges[i].src].icon[0] - boxes[m.edges[i].dst].icon[0])
              + abs(boxes[m.edges[i].src].icon[1] - boxes[m.edges[i].dst].icon[1]))
    channels = [g.box for g in m.items.values() if g.kind == "group" and g.group != LAYOUT_ONLY]

    # AZ ごとに同じ役割の要素 (同じアイコンで、祖先グループの並びが同じ) へ向かう線は、まとめて対称に引く
    def peer(iid):
        it = m.items[iid]
        return (it.raw_icon.name if it.raw_icon else iid, tuple(a.group for a in m.ancestors(iid) if a.group != LAYOUT_ONLY))

    groups: dict = {}
    for k, i in enumerate(todo):
        e = m.edges[i]
        key = (peer(e.src), peer(e.dst), edge_class(e)) if not (e.exit or e.entry) else ("solo", i)
        groups.setdefault(key, []).append(k)
    edges = []
    for i in todo:
        e, ((es, ts), (xf, ef)) = m.edges[i], plan[i]
        edges.append((e.src, e.dst, e.label, es, ts, xf, ef, edge_class(e)))
    results = route_all(boxes, edges, group_headers(m), label_size, channels, list(groups.values()))
    for i, (path, es, ts) in zip(todo, results):
        m.edges[i].path, m.edges[i].sides, m.edges[i].fracs = path, (es, ts), plan[i][1]
