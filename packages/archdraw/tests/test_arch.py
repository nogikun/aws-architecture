"""arch-builder の自己チェック。アイコンライブラリが無い環境では飛ばす。

    uv run --project <skill>/tools pytest <skill>/tools/tests -q
"""

import base64
import copy
import re
import urllib.parse
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import yaml

from archdraw import cli, drawio as D, layout as L, model as M  # noqa: F401
from archdraw.lint import Finding
from archdraw.icons import Library, lib_dir
from archdraw.lint import lint

PKG = Path(__file__).resolve().parents[1]
EXAMPLE = PKG / "examples" / "aws-3tier.yaml"

LIB = Library(lib_dir())
pytestmark = pytest.mark.skipif(not LIB.has_aws, reason="AWS アイコン未取り込み (archdraw doctor)")


def codes(model):
    return {(f.code, f.id) for f in lint(model, layout_first=True)}


def spec(tmp_path, items, edges=()):
    p = tmp_path / "t.arch.yaml"
    p.write_text(yaml.safe_dump({"title": "t", "items": items, "edges": list(edges)}, allow_unicode=True), encoding="utf-8")
    return p


def vpc_with(*subnet_children, subnet="public-subnet", azs=1):
    return [{"id": "c", "group": "aws-cloud", "children": [{"id": "r", "group": "region", "label": "ap-northeast-1",
             "children": [{"id": "v", "group": "vpc", "children": [
                 {"id": f"az{i}", "group": "az", "children": [
                     {"id": f"s{i}", "group": subnet, "children": list(subnet_children) if i == 0 else [
                         {"id": f"x{i}", "icon": "Amazon EC2", "label": "EC2"}]}]} for i in range(azs)]}]}]}]


def test_icon_aliases_resolve_to_official_names():
    assert LIB.resolve("NAT Gateway").name == "Amazon VPC NAT Gateway"
    assert LIB.resolve("Application Load Balancer").name == "Elastic Load Balancing Application Load Balancer"
    assert LIB.resolve("Lambda").name == "AWS Lambda"
    assert LIB.resolve("RDS").name == "Amazon RDS"
    assert LIB.resolve("no such service") is None


def test_example_only_has_known_findings(tmp_path, capsys):
    m = M.load_yaml(EXAMPLE, LIB)
    found = [f for f in lint(m, layout_first=True) if f.severity != "info"]
    assert not [f for f in found if f.severity == "error"]
    # 既知の残り: CloudFront -> IGW が利用者からの線と交差し、レプリケーションのラベルが AZ の隙間の枠線にかかる。
    # 外向き通信 (ECS -> NAT -> IGW) は外側の面を通るので、曲がり過ぎ・ALB の脇は出ない
    assert {(f.code, f.id) for f in found} <= {("N-EDGE-CROSS", None), ("N-EDGE-LABEL-ON-FRAME", "rds-a")}
    assert cli.main(["lint", str(EXAMPLE), "--strict-geometry"]) == 1
    capsys.readouterr()


def test_utf8_yaml_build_preserves_flow_and_saved_lint(tmp_path, capsys, monkeypatch):
    p = spec(tmp_path, [{"id": "cloud", "group": "aws-cloud", "children": [
        {"id": "region", "group": "region", "label": "ap-northeast-1", "children": [
                    {"id": "vpc", "group": "vpc", "label": "VPC layout round-trip regression fixture for retained flow direction and explicit port settings", "flow": "right", "children": [
                {"id": "subnet", "group": "private-subnet", "flow": "right", "layout": "column", "children": [
                    {"id": "a", "icon": "Amazon EC2", "label": "処理A"},
                    {"id": "b", "icon": "AWS Lambda", "label": "処理B"}]}]}]}]}],
        [{"from": "a", "to": "b", "label": "HTTPS", "exit": "right", "entry": "left"}])
    p.write_text("\ufeff" + p.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "図.drawio"

    route_calls = []
    route = L.route
    def tracked_route(m):
        route_calls.append(m)
        return route(m)

    monkeypatch.setattr(L, "route", tracked_route)
    assert cli.main(["build", str(p), "-o", str(out)]) == 0
    assert len(route_calls) == 1
    assert "wrote" in capsys.readouterr().out
    saved = D.load_drawio(out, LIB)
    assert saved.items["vpc"].flow == saved.items["subnet"].flow == "right"
    assert (saved.edges[0].exit, saved.edges[0].entry) == ("right", "left")
    assert not [f for f in lint(saved) if f.code.startswith("N-PORT-")]


@pytest.mark.parametrize("aspect", [4 / 3, 1.77, 1.78, 16 / 9])
def test_page_aspect_override_builds_and_survives_import(tmp_path, aspect):
    p = tmp_path / "page.arch.yaml"
    p.write_text(yaml.safe_dump({"title": "page", "page_aspect": aspect,
                                 "items": [{"id": "user", "icon": "Users", "label": "User"},
                                           {"id": "app", "icon": "AWS Lambda", "label": "App"}],
                                 "edges": [{"from": "user", "to": "app"}]}), encoding="utf-8")
    model = M.load_yaml(p, LIB)
    graph = ET.fromstring(D.to_drawio(model)).find("./diagram/mxGraphModel")
    assert float(graph.get("pageWidth")) / float(graph.get("pageHeight")) == pytest.approx(aspect, abs=1e-3)

    drawio = tmp_path / "page.drawio"
    drawio.write_text(D.to_drawio(model), encoding="utf-8")
    imported = D.load_drawio(drawio, LIB)
    assert imported.page_aspect == pytest.approx(aspect, abs=1e-3)
    assert yaml.safe_load(M.dump_yaml(imported))["page_aspect"] == pytest.approx(aspect, abs=1e-3)

    exported = tmp_path / "imported.arch.yaml"
    rebuilt = tmp_path / "rebuilt.drawio"
    assert cli.main(["import", str(drawio), "-o", str(exported)]) == 0
    assert yaml.safe_load(exported.read_text(encoding="utf-8"))["page_aspect"] == pytest.approx(aspect, abs=1e-3)
    assert cli.main(["build", str(exported), "-o", str(rebuilt)]) == 0
    rebuilt_graph = D.read_graph(rebuilt)
    for dimension in ("pageWidth", "pageHeight"):
        assert rebuilt_graph.get(dimension) == graph.get(dimension)

    p.write_text(yaml.safe_dump({"title": "page", "items": [{"id": "user", "icon": "Users", "label": "User"}],
                                 "edges": []}), encoding="utf-8")
    default_graph = ET.fromstring(D.to_drawio(M.load_yaml(p, LIB))).find("./diagram/mxGraphModel")
    assert float(default_graph.get("pageWidth")) / float(default_graph.get("pageHeight")) == pytest.approx(16 / 9, abs=1e-3)


def test_invalid_page_aspect_is_an_error(tmp_path):
    p = tmp_path / "bad-page.arch.yaml"
    p.write_text(yaml.safe_dump({"page_aspect": 0.8, "items": [], "edges": []}), encoding="utf-8")
    assert ("E-PAGE-ASPECT", None) in codes(M.load_yaml(p, LIB))


def test_build_preserves_existing_output_when_saved_lint_differs(tmp_path, monkeypatch):
    out = tmp_path / "existing.drawio"
    out.write_text("previous output", encoding="utf-8")
    monkeypatch.setattr(cli, "lint", lambda m, layout_first=False: [] if not m.from_drawio else [
        Finding("warn", "TEST-ROUND-TRIP", "fixture", "saved model differs")])

    assert cli.main(["build", str(EXAMPLE), "-o", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "previous output"


def test_nesting_order_is_enforced(tmp_path):
    p = spec(tmp_path, [{"id": "v", "group": "vpc", "children": [{"id": "e", "icon": "Amazon EC2", "label": "x"}]}])
    assert ("N-NESTING", "v") in codes(M.load_yaml(p, LIB))


def test_connected_generic_endpoint_is_not_an_empty_group(tmp_path):
    items = [
        {"id": "caller", "icon": "Amazon EC2", "label": "Caller"},
        {"id": "server", "group": "generic", "label": "MCP Server"},
    ]
    edges = [{"from": "caller", "to": "server"}]
    assert ("N-EMPTY-GROUP", "server") not in codes(M.load_yaml(spec(tmp_path, items, edges), LIB))


def test_connected_generic_endpoint_renders_as_compact_solid_box(tmp_path):
    items = [
        {"id": "caller", "icon": "Amazon EC2", "label": "Caller"},
        {"id": "server", "group": "generic", "label": "MCP Server A"},
    ]
    m = M.load_yaml(spec(tmp_path, items, [{"from": "caller", "to": "server"}]), LIB)
    L.layout(m)
    width, height = m.items["server"].box[2:]
    cell = ET.fromstring(D.to_drawio(m)).find("./diagram/mxGraphModel/root/object[@id='server']/mxCell")

    assert width < 200 and height < 120
    assert "rounded=1" in cell.get("style") and "dashed=0" in cell.get("style")
    assert "container=0" in cell.get("style")


def test_unconnected_generic_group_is_still_an_empty_group(tmp_path):
    items = [{"id": "empty", "group": "generic", "label": "Empty"}]
    assert ("N-EMPTY-GROUP", "empty") in codes(M.load_yaml(spec(tmp_path, items), LIB))


def test_layout_group_is_transparent_to_nesting(tmp_path):
    items = vpc_with({"id": "n", "icon": "NAT Gateway", "label": "NAT"}, azs=2)
    items[0]["children"][0]["children"][0]["children"] = [{"id": "wrap", "group": "layout",
                                                          "children": items[0]["children"][0]["children"][0]["children"]}]
    assert not {c for c, _ in codes(M.load_yaml(spec(tmp_path, items), LIB))} & {"N-NESTING", "N-SUBNET-OUTSIDE-AZ"}


def test_architecture_warnings(tmp_path):
    items = vpc_with({"id": "db", "icon": "Amazon RDS", "label": "DB"})
    got = codes(M.load_yaml(spec(tmp_path, items), LIB))
    assert ("A-DB-PUBLIC", "db") in got
    assert ("A-SINGLE-AZ", "v") in got
    assert ("A-NO-IGW", "v") in got
    items = vpc_with({"id": "nat", "icon": "NAT Gateway", "label": "NAT"}, subnet="private-subnet")
    assert ("A-NAT-PLACEMENT", "nat") in codes(M.load_yaml(spec(tmp_path, items), LIB))
    items = vpc_with({"id": "b", "icon": "Amazon S3", "label": "S3"}, subnet="private-subnet", azs=2)
    assert ("A-REGIONAL-IN-VPC", "b") in codes(M.load_yaml(spec(tmp_path, items), LIB))


def test_unknown_and_category_icons_are_errors(tmp_path):
    p = spec(tmp_path, [{"id": "a", "icon": "Amazon Nonexistent", "label": "a"},
                        {"id": "b", "icon": "Categories / Databases", "label": "b"}, {"id": "c", "icon": "Amazon EC2"}])
    got = codes(M.load_yaml(p, LIB))
    assert {("E-ICON", "a"), ("N-CATEGORY-ICON", "b"), ("N-LABEL", "c")} <= got


def test_drawio_round_trip_keeps_geometry(tmp_path):
    d1 = tmp_path / "a.drawio"
    d1.write_text(D.to_drawio(M.load_yaml(EXAMPLE, LIB)), encoding="utf-8")
    y = tmp_path / "rt.arch.yaml"
    cli.main(["import", str(d1), "-o", str(y)])
    d2 = D.to_drawio(M.load_yaml(y, LIB))
    geo = lambda s: re.findall(r"<mxGeometry[^>]*>", s)  # noqa: E731
    assert geo(d1.read_text(encoding="utf-8")) == geo(d2)


def test_imported_icon_set_builds_and_round_trips(tmp_path):
    """importer で取り込んだセット (prefix:name) を使い、.drawio を経由しても同じアイコンに戻る。"""
    from archdraw import importer
    from archdraw.icons import Library
    src = tmp_path / "svg"
    src.mkdir()
    (src / "Cards.svg").write_text('<svg viewBox="0 0 24 12" fill="none" stroke="currentColor"><path d="M0 0h24"/></svg>')
    (src / "Box.svg").write_text('<svg width="10" height="10"><rect width="10" height="10"/></svg>')
    importer.run("svg", [str(src)], "t", dest=tmp_path / "sets")
    lib = Library(lib_dir(), sets_dir=tmp_path / "sets")
    ic = lib.resolve("t:cards")
    assert ic and (ic.w, ic.h) == (24, 24)  # 横長は正方形に収める
    assert "#232F3E" in base64.b64decode(ic.data.split(",", 1)[1]).decode()  # currentColor は文字色にする
    from archdraw.icons import _thin_strokes  # Lucide (24px・線幅2) は 48px で 1.5px の線になる
    assert _thin_strokes('<path stroke-width="2"/>', 24) == '<path stroke-width="0.75"/>'
    y = spec(tmp_path, [{"id": "a", "icon": "t:cards", "label": "A"}, {"id": "b", "icon": "t:box", "label": "B"},
                        {"id": "c", "icon": "t:nope", "label": "C"}], [{"from": "a", "to": "b"}])
    got = codes(M.load_yaml(y, lib))
    assert ("E-ICON", "c") in got and not any(i in ("a", "b") for _, i in got if _.startswith(("E-", "N-UNMANAGED")))
    y.write_text(y.read_text(encoding="utf-8").replace("t:nope", "t:box"), encoding="utf-8")
    d = tmp_path / "t.drawio"
    d.write_text(D.to_drawio(M.load_yaml(y, lib)), encoding="utf-8")
    m = D.load_drawio(d, lib)
    assert {i.id: i.raw_icon.name for i in m.items.values()} == {"a": "t:cards", "b": "t:box", "c": "t:box"}
    # icon_style: tile は図ごとの設定。.drawio を経由しても残り、AWS 公式アイコンには効かない
    doc = yaml.safe_load(y.read_text(encoding="utf-8"))
    y.write_text(yaml.safe_dump({**doc, "icon_style": "tile"}, allow_unicode=True), encoding="utf-8")
    xml = D.to_drawio(M.load_yaml(y, lib))
    imgs = [base64.b64decode(s).decode() for s in re.findall(r"image=data:image/svg\+xml,([A-Za-z0-9+/=]+)", xml)]
    assert 'arch_icon_style="tile"' in xml and len(imgs) == 3 and all('rx="6"' in s for s in imgs)
    d.write_text(xml, encoding="utf-8")
    assert D.load_drawio(d, lib).icon_style == "tile"
    y.write_text(yaml.safe_dump({**doc, "icon_style": "round"}, allow_unicode=True), encoding="utf-8")
    assert ("E-ICON-STYLE", "-") in {(f.code, f.id or "-") for f in lint(M.load_yaml(y, lib), layout_first=True)}


def test_python_and_tag_sources_build_the_same_drawio_as_yaml(tmp_path):
    outs = set()
    for name in ("aws-3tier.yaml", "aws-3tier.py", "aws-3tier.html"):
        out = tmp_path / f"{name}.drawio"
        assert cli.main(["build", str(PKG / "examples" / name), "-o", str(out)]) == 0
        outs.add(out.read_text(encoding="utf-8"))
    assert len(outs) == 1


def test_hand_edit_in_drawio_is_checked(tmp_path):
    """draw.io で Aurora を public subnet の上へドラッグした (親は変えていない) ケース。"""
    xml = D.to_drawio(M.load_yaml(EXAMPLE, LIB))
    # rds-a を pub-a と同じ相対位置 (y を小さく) に動かす: 見た目は DB subnet の外に出る
    xml = re.sub(r'(<object id="rds-a"[^>]*>\s*<mxCell[^>]*>\s*<mxGeometry x="[^"]*" y=")[^"]*', r"\g<1>-400", xml)
    p = tmp_path / "e.drawio"
    p.write_text(xml, encoding="utf-8")
    got = {c for c, _ in codes(D.load_drawio(p, LIB))}
    assert "N-ESCAPE" in got and "N-VISUAL-PARENT" in got


def test_compressed_drawio_is_readable(tmp_path):
    model = M.load_yaml(EXAMPLE, LIB)
    model.page_aspect = 4 / 3
    xml = D.to_drawio(model)
    xml_model = re.search(r"<mxGraphModel.*</mxGraphModel>", xml, re.S).group(0)
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = base64.b64encode(c.compress(urllib.parse.quote(xml_model).encode()) + c.flush()).decode()
    p = tmp_path / "z.drawio"
    p.write_text(f'<mxfile><diagram id="a" name="z">{packed}</diagram></mxfile>', encoding="utf-8")
    imported = D.load_drawio(p, LIB)
    assert len(imported.items) == len(model.items)
    assert imported.page_aspect == pytest.approx(4 / 3, abs=1e-3)


def test_edit_ops(tmp_path):
    p = tmp_path / "x.arch.yaml"
    p.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    run = lambda *a: cli.main(["edit", str(p), *a])  # noqa: E731
    run("add-node", "cache", "--icon", "ElastiCache", "--label", "Cache", "--parent", "db-a")
    run("connect", "ecs-a", "cache", "--label", "Redis")
    m = M.load_yaml(p, LIB)
    assert m.items["cache"].parent == "db-a" and any(e.dst == "cache" for e in m.edges)
    run("move", "cache", "--parent", "app-a")
    assert M.load_yaml(p, LIB).items["cache"].parent == "app-a"
    run("remove", "az-c")
    m = M.load_yaml(p, LIB)
    assert "ecs-c" not in m.items and all("ecs-c" not in (e.src, e.dst) for e in m.edges)
    with pytest.raises(SystemExit):
        run("add-node", "bad", "--icon", "Amazon Nonexistent")


def row_of_three(tmp_path, **edge):
    items = [{"id": "g", "group": "generic", "label": "x", "layout": "row", "children": [
        {"id": "a", "icon": "Amazon EC2", "label": "A"}, {"id": "b", "icon": "Amazon EC2", "label": "B"},
        {"id": "c", "icon": "Amazon EC2", "label": "C"}]}]
    return spec(tmp_path, items, [{"from": "a", "to": "c", "label": "x", **edge}])


def test_router_detours_around_icons_and_labels(tmp_path):
    m = M.load_yaml(row_of_three(tmp_path), LIB)
    got = codes(m)
    assert not {c for c, _ in got} & {"N-EDGE-THROUGH-NODE", "N-EDGE-LABEL-OVERLAP"}
    # 下の口を使うなら、アイコンではなくラベルの下から出ている
    e = m.edges[0]
    if e.sides[0] == "bottom":
        assert e.path[0][1] > L.route_box(m.items["a"]).label[1] + L.route_box(m.items["a"]).label[3]


def test_shared_trunk_does_not_hide_overlapping_labels(tmp_path):
    """共有してよい幹でも、別々に描かれる同じ位置のラベルは警告する。"""
    m = M.load_yaml(row_of_three(tmp_path, label="HTTPS"), LIB)
    m.edges.append(copy.deepcopy(m.edges[0]))
    assert ("N-EDGE-LABEL-OVERLAP", "a") in codes(m)


def test_edge_crossing_is_reported_even_for_shared_trunk_pair(tmp_path):
    m = M.load_yaml(row_of_three(tmp_path), LIB)
    L.layout(m)
    a, b = m.edges[0], copy.deepcopy(m.edges[0])
    a.path = [(0, 0), (40, 0)]
    b.path = [(20, -20), (20, 20)]
    m.edges.append(b)
    assert sum(f.code == "N-EDGE-CROSS" for f in lint(m)) == 1


def test_edge_endpoint_contact_is_reported(tmp_path):
    nodes = [{"id": "g", "group": "generic", "children": [
        {"id": name, "icon": "Amazon EC2", "label": name.upper()} for name in "abcd"]}]
    m = M.load_yaml(spec(tmp_path, nodes, [{"from": "a", "to": "b"}, {"from": "c", "to": "d"}]), LIB)
    L.layout(m)
    a, b = m.edges
    a.path = [(0, 0), (40, 0)]
    b.path = [(20, 0), (20, 40)]  # T 字接触 (線の端が別の線の途中に当たる)
    assert any(f.code == "N-EDGE-TOUCH" for f in lint(m))


def test_bbox_prefilter_keeps_near_parallel_edge_overlap(tmp_path):
    nodes = [{"id": "g", "group": "generic", "children": [
        {"id": name, "icon": "Amazon EC2", "label": name.upper()} for name in "abcd"]}]
    m = M.load_yaml(spec(tmp_path, nodes, [{"from": "a", "to": "c"}, {"from": "b", "to": "d"}]), LIB)
    m.edges[0].path = [(0, 0), (100, 0)]
    m.edges[1].path = [(0, 7), (100, 7)]
    assert any(f.code == "N-EDGE-OVERLAP" for f in lint(m))


def test_crossing_inside_shared_source_icon_is_not_reported(tmp_path):
    m = M.load_yaml(row_of_three(tmp_path), LIB)
    L.layout(m)
    a, b = m.edges[0], copy.deepcopy(m.edges[0])
    x, y, w, h = L.route_box(m.items[a.src]).icon
    cx, cy = x + w / 2, y + h / 2
    a.path = [(cx - 10, cy), (cx + 10, cy)]
    b.path = [(cx, cy - 10), (cx, cy + 10)]
    m.edges.append(b)
    assert not [f for f in lint(m) if f.code == "N-EDGE-CROSS"]


def test_strict_geometry_lint_rejects_unchecked_route(tmp_path, capsys):
    nodes = [{"id": "g", "group": "generic", "children": [
        {"id": name, "icon": "Amazon EC2", "label": name.upper()} for name in "abcd"]}]
    m = M.load_yaml(spec(tmp_path, nodes, [{"from": "a", "to": "b"}, {"from": "c", "to": "d"}]), LIB)
    path = tmp_path / "unchecked.drawio"
    path.write_text(D.to_drawio(m), encoding="utf-8")
    graph = D.read_graph(path)
    edge = next(c for c in graph.findall(".//mxCell") if c.get("edge") == "1")
    edge.set("style", ";".join(x for x in edge.get("style", "").split(";")
                                  if not x.startswith(("exitX=", "entryX="))))
    mxfile = ET.Element("mxfile")
    ET.SubElement(mxfile, "diagram", id="unchecked", name="unchecked").append(graph)
    path.write_bytes(ET.tostring(mxfile, encoding="utf-8", xml_declaration=True))

    assert cli.main(["lint", str(path)]) == 0
    capsys.readouterr()
    assert cli.main(["lint", str(path), "--strict-geometry"]) == 1
    assert "N-EDGE-UNCHECKED" in capsys.readouterr().out


def test_edge_through_a_node_is_an_error(tmp_path):
    from archdraw.route import port
    m = M.load_yaml(row_of_three(tmp_path, exit="right", entry="left"), LIB)
    a, c = L.route_box(m.items["a"]), L.route_box(m.items["c"])
    m.edges[0].path = [port(a, "right"), port(c, "left")]  # B を貫く直線 (draw.io で手で引いた想定)
    assert ("N-EDGE-THROUGH-NODE", "a") in {(f.code, f.id) for f in lint(m)}


def test_route_survives_drawio_round_trip(tmp_path):
    p = tmp_path / "r.drawio"
    p.write_text(D.to_drawio(M.load_yaml(EXAMPLE, LIB)), encoding="utf-8")
    m = D.load_drawio(p, LIB)
    assert all(e.path for e in m.edges)  # waypoint から経路を復元できる
    # 経路も接続口も読み戻せる (読み戻した図でも、接続口の誤りや線の横切りにならない)
    assert not [f for f in lint(m) if f.code.startswith("N-PORT") or f.code == "N-EDGE-THROUGH-NODE"]


def test_set_edge(tmp_path):
    p = tmp_path / "x.arch.yaml"
    p.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    cli.main(["edit", str(p), "set-edge", "alb", "ecs-a", "label=HTTP", "exit=bottom", "dashed=true"])
    e = next(e for e in M.load_yaml(p, LIB).edges if (e.src, e.dst) == ("alb", "ecs-a"))
    assert (e.label, e.exit, e.dashed) == ("HTTP", "bottom", True)


def test_gateways_sit_on_the_vpc_border(tmp_path):
    m = M.load_yaml(EXAMPLE, LIB)
    L.layout(m)
    igw, vpc = m.items["igw"], m.items["vpc"]
    ix, iy, iw, ih = L.icon_box(igw)
    assert igw.border == "top" and abs(iy + ih / 2 - vpc.box[1]) < 0.5  # 中心が VPC の上辺の線に乗る
    p = tmp_path / "b.drawio"
    p.write_text(D.to_drawio(m), encoding="utf-8")
    assert D.load_drawio(p, LIB).items["igw"].border == "top"  # 取り込みでも座標から判定できる
    y = tmp_path / "b.arch.yaml"
    y.write_text(EXAMPLE.read_text(encoding="utf-8").replace(
        "{id: igw, icon: Internet Gateway, label: Internet Gateway}",
        "{id: igw, icon: Internet Gateway, label: Internet Gateway, border: none}"), encoding="utf-8")
    assert ("A-GATEWAY-BORDER", "igw") in codes(M.load_yaml(y, LIB))


def test_notes_round_trip_and_near_node_warning(tmp_path):
    y = tmp_path / "n.arch.yaml"
    y.write_text(EXAMPLE.read_text(encoding="utf-8") + "notes:\n  - 前提: 社員はインターネット経由で入る\n",
                  encoding="utf-8")
    p = tmp_path / "n.drawio"
    p.write_text(D.to_drawio(M.load_yaml(y, LIB)), encoding="utf-8")
    m = D.load_drawio(p, LIB)
    assert m.notes == ["前提: 社員はインターネット経由で入る"] and "__notes" not in m.items
    note = ET.fromstring(p.read_text(encoding="utf-8")).find("./diagram/mxGraphModel/root/object[@id='__notes']")
    note_style = note.find("mxCell").get("style")
    note_geometry = note.find("mxCell/mxGeometry")
    model = ET.fromstring(p.read_text(encoding="utf-8")).find("./diagram/mxGraphModel")
    assert "fontSize=14" in note_style
    # 注記の幅は図の幅 (用紙の 16:9 の幅ではない。PNG の右に空白を作らない)
    assert 400 <= float(note_geometry.get("width")) < float(model.get("pageWidth")) - 80

    from archdraw.route import port
    m = M.load_yaml(row_of_three(tmp_path), LIB)
    L.layout(m)
    a, c, b = (L.route_box(m.items[i]) for i in "acb")
    # B のアイコンの上端をかすめる線 (横切りはしないが、B につながって見える)
    y0 = b.icon[1] - 12
    m.edges[0].path = [port(a, "top"), (port(a, "top")[0], y0), (port(c, "top")[0], y0), port(c, "top")]
    assert ("N-EDGE-NEAR-NODE", "a") in {(f.code, f.id) for f in lint(m)}


def test_border_ports_and_symmetric_fanout():
    m = M.load_yaml(EXAMPLE, LIB)
    L.layout(m)
    igw_ports = {s for e in m.edges for s, n in zip(e.sides, (e.src, e.dst)) if n == "igw"}
    assert igw_ports <= {"top", "bottom"}  # 上辺の線上の IGW は、枠線をなぞる左右の口を使わない
    fan = [e for e in m.edges if e.src == "alb" and e.dst in ("ecs-a", "ecs-c")]
    assert len({e.sides for e in fan}) == 1  # AZ ごとの対になる線は同じ口の組み合わせで引く


def test_flow_faces_and_t_branch():
    m = M.load_yaml(EXAMPLE, LIB)
    L.layout(m)
    e = {(x.src, x.dst): x for x in m.edges}
    # VPC の中は上から入って下へ出る (入口と出口が向かい合う)。外は左から入って右へ出る
    assert e[("ecs-a", "rds-a")].sides == ("bottom", "top")
    assert e[("users", "cf")].sides == ("right", "left")
    # ALB からの分岐は同じ高さで左右に分かれる (T 字)
    lv = [[round(a[1]) for a, b in zip(x.path, x.path[1:]) if abs(a[1] - b[1]) < 0.5] for x in (e[("alb", "ecs-a")], e[("alb", "ecs-c")])]
    assert lv[0] == lv[1]


def test_port_rules_and_slots(tmp_path):
    """面: 下流の相手へは流れの面、真横・上流の相手へは 90° 回した面。スロット: 内容の違う線は 2n+1 等分の偶数番目。"""
    items = [{"id": "g", "group": "generic", "label": "x", "layout": "row", "children": [
        {"id": "a", "icon": "Amazon EC2", "label": "A"}, {"id": "b", "icon": "Amazon EC2", "label": "B"}]},
        {"id": "c", "icon": "Amazon EC2", "label": "C"}]
    edges = [{"from": "a", "to": "b", "label": "HTTPS"}, {"from": "a", "to": "b", "label": "gRPC"},
             {"from": "b", "to": "a", "label": "callback"}]
    m = M.load_yaml(spec(tmp_path, items, edges), LIB)
    L.layout(m)
    https, grpc, back = m.edges
    assert https.sides == grpc.sides == ("right", "left")        # 外の流れは左 → 右 (b は a の下流)
    # a の右の面には HTTPS (出)・gRPC (出) の 2 種類 → 5 等分の 2, 4 番目の中央
    assert sorted([https.fracs[0], grpc.fracs[0]]) == [pytest.approx(1.5 / 5), pytest.approx(3.5 / 5)]
    # 上流 (左) へ戻る線は、行きの線と同じ面に並ぶなら、両端とも外側の面へ逃がす (入る線と出る線を隣り合わせない)
    assert back.sides == ("top", "top")
    # 手で面を変えた .drawio は N-PORT-FACE になる
    p = tmp_path / "p.drawio"
    p.write_text(re.sub(r"exitX=1;exitY=[0-9.]+", "exitX=0.5;exitY=0", D.to_drawio(m), count=1),
                 encoding="utf-8")
    assert "N-PORT-FACE" in {f.code for f in lint(D.load_drawio(p, LIB))}


def test_portrait_is_forbidden(tmp_path):
    col = [{"id": f"n{i}", "icon": "Amazon EC2", "label": f"N{i}"} for i in range(4)]
    m = M.load_yaml(spec(tmp_path, [{"id": "g", "group": "generic", "label": "x", "layout": "column", "children": col}]), LIB)
    assert "N-ASPECT-PORTRAIT" in {f.code for f in lint(m, layout_first=True) if f.severity == "error"}


def test_sparse_group_and_unconnected_gateway(tmp_path):
    items = vpc_with({"id": "n", "icon": "NAT Gateway", "label": "NAT"}, azs=2)
    items[0]["children"][0]["children"][0]["children"][0]["children"][0]["size"] = [900, 600]  # s0 を中身の何倍にも広げる
    m = M.load_yaml(spec(tmp_path, items), LIB)
    got = {(f.code, f.severity) for f in lint(m, layout_first=True)}
    assert ("N-SPARSE", "error") in got
    assert ("N-NODE-UNCONNECTED", "error") in got
