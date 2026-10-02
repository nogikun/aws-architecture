"""図の検査 (lint) の core。どの種類の図にも当てはまる作図規約と幾何 (見た目の破綻) を見る。

- E-*: 読み込めない・参照が切れている (error)
- N-*: 作図規約と見た目の破綻。原則 error、読みにくさは warn
図の種類ごとの構成ルール (AWS の A-* など) は packs/ が CHECKS に足す。
error が 1 件でも残る図は納品しない。warn は理由があれば残してよい (図の注記か報告で理由を言う)。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from archdraw.layout import edge_class, group_headers, group_need, label_size, layout, plan_ports, route_box
from archdraw.model import GROUPS, ICON, LAYOUT_ONLY, SIDES, STRETCH_MAX, Model, on_border
from archdraw.route import (_cross, _near_collinear, blocked, crosses_label, label_hits, label_rect, near_obstacles,
                            obstacles_of, passes_near, path_hits, rects_overlap, seg_hits, shares_trunk)

SEV_ORDER = {"error": 0, "warn": 1, "info": 2}
CHECKS: list = []  # packs/ が足す検査: check(m: Model, c: Ctx) -> None


@dataclass
class Finding:
    severity: str
    code: str
    id: str | None
    msg: str
    fix: str = ""


class Ctx:
    """pack の検査に渡す道具。add で指摘を足し、layout 箱を飛ばした親子関係を引く。"""

    def __init__(self, m: Model, add):
        self.m, self.add = m, add
        self.nodes = [i for i in m.items.values() if i.kind == "node"]
        self.groups = [i for i in m.items.values() if i.kind == "group"]

    def real_ancestors(self, iid):  # layout 箱を飛ばした祖先
        return [a for a in self.m.ancestors(iid) if a.group != LAYOUT_ONLY]

    def real_parent(self, it):
        anc = self.real_ancestors(it.id)
        return anc[0] if anc else None

    def real_children(self, g):  # layout 箱を展開した子
        for c in g.children:
            ci = self.m.items[c]
            if ci.group == LAYOUT_ONLY:
                yield from self.real_children(ci)
            else:
                yield ci

    def gtypes(self, it):
        return [a.group for a in self.real_ancestors(it.id)]


def _touch_point(a, b):
    """直交線分が交わるが、両方の内部で交差するわけではない接点を返す。"""
    (p, q), (r, s) = a, b
    ah, bh = abs(p[1] - q[1]) < 0.5, abs(r[1] - s[1]) < 0.5
    if ah == bh:
        if ah and abs(p[1] - r[1]) < 0.5:
            lo = max(min(p[0], q[0]), min(r[0], s[0]))
            hi = min(max(p[0], q[0]), max(r[0], s[0]))
            return (lo, (p[1] + r[1]) / 2) if lo == hi else None
        if not ah and abs(p[0] - r[0]) < 0.5:
            lo = max(min(p[1], q[1]), min(r[1], s[1]))
            hi = min(max(p[1], q[1]), max(r[1], s[1]))
            return ((p[0] + r[0]) / 2, lo) if lo == hi else None
        return None
    h, v = (a, b) if ah else (b, a)
    x0, x1 = sorted((h[0][0], h[1][0]))
    y0, y1 = sorted((v[0][1], v[1][1]))
    x, y = v[0][0], h[0][1]
    return (x, y) if x0 <= x <= x1 and y0 <= y <= y1 else None


def _segment_bounds(segment, pad=8):
    (x1, y1), (x2, y2) = segment
    return min(x1, x2) - pad, min(y1, y2) - pad, max(x1, x2) + pad, max(y1, y2) + pad


def _bounds_disjoint(a, b):
    return a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]


def lint(m: Model, layout_first: bool = False) -> list[Finding]:
    if layout_first and not m.from_drawio:
        layout(m)
    out: list[Finding] = []
    add = lambda sev, code, iid, msg, fix="": out.append(Finding(sev, code, iid, msg, fix))  # noqa: E731

    for code, msg, iid in m.problems:
        add("error", code, iid, msg)

    ids = set(m.items)
    connected = {end for e in m.edges if e.src in ids and e.dst in ids for end in (e.src, e.dst)}
    c = Ctx(m, add)
    nodes, groups, real_parent = c.nodes, c.groups, c.real_parent

    # ---------------- 作図規約 ----------------
    for it in nodes:
        if it.unmanaged:
            add("error", "N-UNMANAGED", it.id, f"{it.unmanaged}。公式アイコン以外の図形・画像は使わない",
                "公式ライブラリのアイコンに置き換えるか、注記ならグループ/接続線のラベルに移す")
            continue
        if not it.icon:
            add("error", "E-ICON", it.id, "icon が無い", "archdraw icons search <語> で探して指定する")
        elif not it.raw_icon:
            sug = m.lib.suggest(it.icon) if m.lib else []
            add("error", "E-ICON", it.id, f"アイコン '{it.icon}' は{'取り込んだセット' if ':' in it.icon and not it.icon.lower().startswith('aws:') else 'AWS 公式ライブラリ'}に無い",
                f"候補: {', '.join(sug) or 'archdraw icons search で探す'}")
        if not it.label.strip():
            add("error", "N-LABEL", it.id, "ラベルが無い。アイコンにはサービス名 (と役割) を必ず付ける")
        elif max(len(x) for x in it.label.split("\n")) > 28:
            add("warn", "N-LABEL-LONG", it.id, f"ラベルの1行が長い ({it.label!r})", "改行 (\\n) で2行に分ける")
        w, h = it.icon_wh
        if abs(w - h) > 0.5:
            add("error", "N-ICON-DISTORT", it.id, f"アイコンの縦横比が崩れている ({w:.0f}x{h:.0f})", "正方形に戻す")
        elif abs(w - ICON) > 0.5:
            add("warn", "N-ICON-SIZE", it.id, f"アイコンが {w:.0f}px。図の中のサービスアイコンは 48px に揃える")

    for it in groups:
        if it.group not in GROUPS:
            add("error", "N-GROUP-TYPE", it.id, f"未知のグループ種類 '{it.group}'", f"使えるのは {', '.join(GROUPS)}")
            continue
        if it.group == LAYOUT_ONLY:
            continue
        rp = real_parent(it)
        parent = rp.group if rp else None
        allowed = GROUPS[it.group].parents
        if "*" not in allowed and parent not in allowed:
            want = " / ".join("キャンバス直下" if p is None else p for p in allowed)
            add("error", "N-NESTING", it.id,
                f"{it.group} が {parent or 'キャンバス直下'} の中にある (置いてよい親が決まっている種類)",
                f"{it.group} の親は {want}")
        if not it.children and not (it.group == "generic" and it.label.strip() and it.id in connected):
            add("warn", "N-EMPTY-GROUP", it.id, f"{it.group} が空", "不要なら消す")
    # 接続線
    seen = Counter()
    for e in m.edges:
        for end in (e.src, e.dst):
            if end not in ids:
                add("error", "E-REF", None, f"接続線 {e.src} -> {e.dst} の '{end}' が存在しない")
        if e.src == e.dst:
            add("warn", "N-EDGE-SELF", e.src, "自分自身への接続線")
        seen[(e.src, e.dst)] += 1
        if len(e.label) > 24:
            add("warn", "N-EDGE-LABEL-LONG", e.src, f"接続線ラベルが長い ({e.label!r})", "12〜16字程度に")
    for (s, d), n in seen.items():
        if n > 1:
            add("warn", "N-EDGE-DUP", s, f"{s} -> {d} の接続線が {n} 本ある")

    # ---------------- 幾何 (見た目の破綻) ----------------
    def inside(a, b, tol=1.0):
        return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[0] + a[2] <= b[0] + b[2] + tol and a[1] + a[3] <= b[1] + b[3] + tol

    def overlap(a, b):
        return a[0] < b[0] + b[2] - 1 and b[0] < a[0] + a[2] - 1 and a[1] < b[1] + b[3] - 1 and b[1] < a[1] + a[3] - 1

    for it in m.items.values():
        if it.parent and not on_border(it) and not inside(it.box, m.items[it.parent].box):
            add("error", "N-ESCAPE", it.id, f"{it.id} が親 {it.parent} の枠からはみ出している",
                "親グループを広げるか、手動の pos / size を消して自動配置に戻す")
    for parent_children in [m.roots] + [g.children for g in groups]:
        kids = [m.items[c] for c in parent_children]
        for i, a in enumerate(kids):
            for b in kids[i + 1:]:
                if overlap(a.box, b.box):
                    add("error", "N-OVERLAP", a.id, f"{a.id} と {b.id} が重なっている (ラベル領域を含む)")
    for it in nodes:  # 見た目の所属 (どの枠の中に描かれているか) と論理上の所属が一致するか
        cx, cy = it.box[0] + it.box[2] / 2, it.box[1] + ICON / 2
        drawn_in = {g.id for g in groups if g.box[0] <= cx <= g.box[0] + g.box[2] and g.box[1] <= cy <= g.box[1] + g.box[3]}
        logical = {a.id for a in m.ancestors(it.id)}
        if drawn_in != logical:
            add("error", "N-VISUAL-PARENT", it.id,
                f"見た目では {sorted(drawn_in) or 'どの枠にも入っていない'} に描かれているが、所属は {sorted(logical) or 'キャンバス直下'}",
                "draw.io で枠の中へドラッグして親子にするか、正本で所属を直す")

    # 接続線: 経路探索と同じ判定で、線がアイコン・ラベル・見出しを横切っていないかを見る
    obstacles = obstacles_of(route_box(n) for n in nodes)
    near_obs = near_obstacles(route_box(n) for n in nodes)
    headers = group_headers(m)
    unchecked = 0
    for e in m.edges:
        if e.src not in ids or e.dst not in ids:
            continue
        if not e.path:
            unchecked += 1
            continue
        name = f"{e.src} -> {e.dst}"
        hit = blocked(e.path, e.src, e.dst, obstacles)
        if hit:
            add("error", "N-EDGE-THROUGH-NODE", e.src, f"線 {name} が {hit} のアイコンかラベルを横切っている",
                "並び順か layout を変えて近づける。探索で避けきれないときは edges に exit/entry (top/right/bottom/left) を指定する")
        near = [i for i in passes_near(e.path, e.src, e.dst, near_obs) if i not in hit]
        if near:
            add("warn", "N-EDGE-NEAR-NODE", e.src, f"線 {name} が {near} のすぐ脇を通り、そこへつながっているように見える",
                "線でつながる相手どうしを近くに並べ替えるか、exit/entry を変えて離す")
        if any(path_hits(e.path, r) for r in headers):
            add("warn", "N-EDGE-THROUGH-HEADER", e.src, f"線 {name} がグループの見出しを横切っている")
        lh = label_hits(e.path, e.label, label_size, obstacles)
        if lh:
            add("warn", "N-EDGE-LABEL-OVERLAP", e.src, f"線 {name} のラベル '{e.label}' が {lh} に重なっている",
                "ラベルを短くするか、線を長くとれる並びにする")
    frame_lines = []
    for g in groups:
        if g.group != LAYOUT_ONLY and not (g.group == "generic" and not g.children):
            x, y, w, h = g.box
            frame_lines += [((x, y), (x + w, y)), ((x, y + h), (x + w, y + h)), ((x, y), (x, y + h)), ((x + w, y), (x + w, y + h))]
    # 線のラベル: 別の線が上を通る / ラベルどうし・見出しと重なる
    labels = [(e, label_rect(e.path, e.label, label_size)) for e in m.edges if e.path and e.label]
    for n_i, (e, lr) in enumerate(labels):
        name = f"{e.src} -> {e.dst}"
        crossing = [f"{o.src} -> {o.dst}" for o in m.edges if o.path and o is not e and crosses_label(lr, o.path, e.path)]
        if crossing:
            add("warn", "N-EDGE-LABEL-CROSSED", e.src, f"線 {name} のラベル '{e.label}' の上を {crossing} が通っている",
                "ラベルの文字が線で消される。並び順を変えるか、ラベルを短くして線の長い区間に来るようにする")
        for o, olr in labels[n_i + 1:]:
            # The edge may share a wire trunk, but its label is rendered
            # independently, so coincident text must still be reported.
            if rects_overlap(lr, olr):
                add("warn", "N-EDGE-LABEL-OVERLAP", e.src, f"線 {name} と {o.src} -> {o.dst} のラベルが重なっている")
        if any(rects_overlap(lr, h) for h in headers):
            add("warn", "N-EDGE-LABEL-OVERLAP", e.src, f"線 {name} のラベルがグループの見出しに重なっている")
        if any(seg_hits(a, b, lr) for a, b in frame_lines):
            add("warn", "N-EDGE-LABEL-ON-FRAME", e.src, f"線 {name} のラベル '{e.label}' が枠線の上にある",
                "枠線が文字を貫いて読みにくい。ラベルを短くするか、線が枠の中か外で長く走る並びにする")
    # 枠線に沿って走る線 (枠線と見分けがつかない)
    frames = []
    for g in groups:
        if g.group != LAYOUT_ONLY:
            x, y, w, h = g.box
            frames += [((x, y), (x + w, y)), ((x, y + h), (x + w, y + h)), ((x, y), (x, y + h)), ((x + w, y), (x + w, y + h))]
    for e in m.edges:
        if e.path and any(_near_collinear(sg, f) for sg in zip(e.path, e.path[1:]) for f in frames):
            add("warn", "N-EDGE-ON-FRAME", e.src, f"線 {e.src} -> {e.dst} がグループの枠線に沿って走っている",
                "枠線と見分けがつかない。枠と枠の隙間の中央を通るよう、並び順や接続口を見直す")

    # スカスカの枠: 枠の面積が、中身に必要な面積の何倍か (1.5 倍まで。2 倍以上は禁止)
    for g in groups:
        need = group_need(m, g) if g.group != LAYOUT_ONLY else None
        if not need:
            continue
        factor = g.box[2] * g.box[3] / (need[0] * need[1])
        if factor > STRETCH_MAX:
            inside = [c for c in g.children if m.items[c].kind == "node"]
            add("error" if factor >= 2 else "warn", "N-SPARSE", g.id,
                f"{g.group} {g.id} の面積が中身に必要な面積の {factor:.1f} 倍 (中身: {inside or g.children})。上限 {STRETCH_MAX} 倍、2 倍以上は禁止",
                "枠を中身に合わせて縮める (手動の size を消す)。幅や高さをそろえたいなら、並ぶ枠の中身をそろえる")

    # 接続口: 面と面の中の位置 (スロット) が決まりどおりか (決まりは cli.plan_ports。spec.md「流れと接続口」)
    plan = plan_ports(m)
    for i, e in enumerate(m.edges):
        if i not in plan or e.sides == (None, None):
            continue
        (want_sides, want_fracs), name = plan[i], f"{e.src} -> {e.dst}"
        for k, end in ((0, "出口"), (1, "入口")):
            if e.sides[k] != want_sides[k]:
                add("error", "N-PORT-FACE", e.src, f"線 {name} の{end}が {e.sides[k]} の面 (決まりでは {want_sides[k]})",
                    "流れの下流の相手へは 出口=流れの面 / 入口=流れの面。真横・上流の相手へは流れと直交する面を向かい合わせる。"
                    "archdraw build で引き直す")
            elif abs(e.fracs[k] - want_fracs[k]) > 0.02:
                add("error", "N-PORT-SLOT", e.src,
                    f"線 {name} の{end}が面の {e.fracs[k]:.0%} の位置 (決まりでは {want_fracs[k]:.0%})",
                    "内容 (ラベル・線種) が違う線は面を 2n+1 等分した偶数番目の中央から別々に、同じ内容の線は同じ位置から出す")
    # 重なり: 幹を共有してよいのは、同じ内容で端点を共有する線だけ
    routed = [e for e in m.edges if e.path]
    # ponytail: O(S^2) geometry checks took 2.7 ms at 74 segments; use sweep-line only if they exceed 100 ms in profiling.
    routed_segments = [[(segment, _segment_bounds(segment)) for segment in zip(e.path, e.path[1:])] for e in routed]
    crossings = {}
    # ponytail: conservative 8px-expanded bounds keep exact predicates while skipping distant segment pairs.
    for a_i, a in enumerate(routed):
        a_segments = routed_segments[a_i]
        for b_i in range(a_i + 1, len(routed)):
            b = routed[b_i]
            shared_icons = [route_box(m.items[i]).icon for i in {a.src, a.dst} & {b.src, b.dst}
                            if i in m.items and m.items[i].kind == "node"]
            shared_route = shares_trunk(a.src, a.dst, edge_class(a), b.src, b.dst, edge_class(b))
            crossing_points = set()
            overlap = False
            for sa, ba in a_segments:
                for sb, bb in routed_segments[b_i]:
                    if _bounds_disjoint(ba, bb):
                        continue
                    is_crossing = bool(_cross(sa, sb)[0])
                    point = None if is_crossing else _touch_point(sa, sb)
                    if is_crossing or (point is not None and not shared_route):
                        code = "N-EDGE-CROSS" if is_crossing else "N-EDGE-TOUCH"
                        if is_crossing:
                            ah = abs(sa[0][1] - sa[1][1]) < 0.5
                            h, v = (sa, sb) if ah else (sb, sa)
                            point = (v[0][0], h[0][1])
                        # 共有端点ノードのアイコン内は、線が図形の背面で隠れるため交差に数えない。
                        if not any(x <= point[0] <= x + w and y <= point[1] <= y + h
                                   for x, y, w, h in shared_icons):
                            crossing_points.add((code, round(point[0], 2), round(point[1], 2)))
                    if not shared_route:
                        overlap |= _near_collinear(sa, sb)
            for code, x, y in crossing_points:
                crossings.setdefault((code, x, y), set()).update((f"{a.src} -> {a.dst}", f"{b.src} -> {b.dst}"))
            if overlap:
                add("warn", "N-EDGE-OVERLAP", a.src, f"線 {a.src} -> {a.dst} と {b.src} -> {b.dst} が重なって走っている",
                    "内容が違う線は重ねない。並び順を変えるか、ラベルをそろえて同じ内容として束ねる")
        if not a.dashed and len(a.path) - 2 > 2:
            add("warn", "N-EDGE-BENDS", a.src, f"線 {a.src} -> {a.dst} が {len(a.path) - 2} 回曲がっている (2 回まで)",
                "線でつながる相手どうしを、流れの向き (flow: down なら上→下、right なら左→右) に並べ直す")
    for (code, x, y), edges_at_point in sorted(crossings.items()):
        kind = "内部交差" if code == "N-EDGE-CROSS" else "端点接触"
        add("warn", code, None, f"経路 {', '.join(sorted(edges_at_point))} が座標 ({x:g}, {y:g}) で{kind}している",
            "接続先を明示するか、線が接触しない経路になるよう配置か接続口を変える")
    if unchecked:
        add("info", "N-EDGE-UNCHECKED", None, f"経路が draw.io 任せの線が {unchecked} 本あり、横切りを検査できない",
            "archdraw import → archdraw build で経路を引き直すと検査できる")

    # キャンバスの縦横比: スライドや画面にそのまま貼れるよう 16:9 を目指す
    pts = [(x, y) for i in m.items.values() for x, y in ((i.box[0], i.box[1]), (i.box[0] + i.box[2], i.box[1] + i.box[3]))]
    pts += [p for e in m.edges if e.path for p in e.path]
    if pts:
        w = max(p[0] for p in pts) - min(p[0] for p in pts)
        h = max(p[1] for p in pts) - min(p[1] for p in pts)
        ratio = w / h if h else 0
        # 縦長は禁止。横長の中での 16:9 は目安 (線の素直さを優先する。用紙は to_drawio が 16:9 にする)
        if ratio < 1.0:
            add("error", "N-ASPECT-PORTRAIT", None, f"図全体が縦長 ({ratio:.2f}:1、{w:.0f}x{h:.0f}px)。縦長の図は禁止",
                "要素を横に広げる (利用者・外部を左右に置く、並列の枠を横に並べる)")
        elif not 1.4 <= ratio <= 2.2:
            add("info", "N-ASPECT", None, f"図全体の縦横比が {ratio:.2f}:1 (目安は 16:9 = 1.78:1。{w:.0f}x{h:.0f}px)",
                "目安なので、線の素直さを崩してまで合わせない")

    # すべてのノードが、1 本以上の線で何かとつながっているか (図に置いたのに、何とやり取りするのかが読めない)
    connected = {e.src for e in m.edges} | {e.dst for e in m.edges}
    for it in nodes:
        if it.id in connected or any(a.id in connected for a in m.ancestors(it.id) if a.group != LAYOUT_ONLY):
            continue
        name = it.raw_icon.name if it.raw_icon else it.id
        add("error", "N-NODE-UNCONNECTED", it.id, f"'{name}' ({it.id}) がどの線ともつながっていない",
            "やり取りする相手への線を引く (出入口のゲートウェイも、通る通信の線でつなぐ。監視・認可などの補助の関係なら破線)。"
            "図に不要なら消す")
    for it in nodes:
        if it.border in SIDES and it.parent and m.items[it.parent].group == LAYOUT_ONLY:
            add("warn", "N-BORDER-ON-LAYOUT", it.id, "枠を描かない layout 箱の枠線上に置いている", "見える枠の直下に置く")

    for check in CHECKS:
        check(m, c)
    out.sort(key=lambda f: (SEV_ORDER[f.severity], f.code, f.id or ""))
    return out


def report(findings: list[Finding]) -> str:
    c = Counter(f.severity for f in findings)
    lines = [f"lint: error {c['error']} / warn {c['warn']} / info {c['info']}"]
    for f in findings:
        lines.append(f"  [{f.severity}] {f.code} {f.id or '-'}: {f.msg}" + (f"\n      → {f.fix}" if f.fix else ""))
    return "\n".join(lines)
