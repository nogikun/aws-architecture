"""AWS アイコンが無くても動くこと (OSS の CI はこれだけで回る)。アイコンは合成した小さなセットを使う。"""

from pathlib import Path

from archdraw import Diagram, cli
from archdraw.drawio import load_drawio, to_drawio
from archdraw.icons import Library
from archdraw.importer import save, svg_to_icon


def lib_without_aws(tmp_path: Path) -> Library:
    icon = svg_to_icon('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/></svg>')
    save({"prefix": "t", "info": {"name": "test"}, "icons": {n: icon for n in ("user", "api", "db", "cache")}},
         tmp_path / "sets")
    lib = Library(tmp_path / "no-aws", sets_dir=tmp_path / "sets")
    assert not lib.has_aws
    return lib


def test_generic_diagram_builds_without_aws(tmp_path):
    lib = lib_without_aws(tmp_path)
    d = Diagram("web", icon_style="tile")
    users = d.node("t:user", "利用者")
    with d.group("generic", "アプリ", layout="column"):
        api = d.node("t:api", "API")
    with d.group("generic", "データ", layout="column"):
        db, cache = d.node("t:db", "DB"), d.node("t:cache", "キャッシュ")
    users.to(api, "HTTPS")
    api >> [db, cache]
    assert [e["to"] for e in d.doc["edges"]] == ["api", "db", "cache"]
    errors = [f for f in d.lint(lib) if f.severity == "error"]
    assert not errors, errors
    out = tmp_path / "web.drawio"
    out.write_text(to_drawio(d.model(lib)), encoding="utf-8")
    m = load_drawio(out, lib)
    assert m.icon_style == "tile" and {i.raw_icon.name for i in m.items.values() if i.kind == "node"} == {
        "t:user", "t:api", "t:db", "t:cache"}


def test_aws_icon_without_aws_library_tells_how_to_fetch(tmp_path):
    lib = lib_without_aws(tmp_path)
    d = Diagram("aws")
    a, b = d.node("Amazon EC2", "EC2"), d.node("t:db", "DB")
    a >> b
    f = next(f for f in d.lint(lib) if f.code == "E-ICON")
    assert "archdraw icons fetch aws" in f.fix


def test_hairpin_paths_are_rejected():
    from archdraw.route import _self_overlap  # ラベルの置き場所を作るために自分の上を往復する線
    assert _self_overlap([(332, 248), (208, 248), (208, 246), (332, 246)])
    assert not _self_overlap([(0, 0), (100, 0), (100, 50), (200, 50)])


def test_edge_from_group_connects_its_nodes_and_bad_config_stops_build(tmp_path, capsys):
    lib = lib_without_aws(tmp_path)
    d = Diagram("monitor", layout="column")   # 最上位の column は無い (row / auto)
    with d.group("generic", "アプリ", layout="auto") as app:
        a, b = d.node("t:api", "A"), d.node("t:db", "B")
    mon = d.node("t:cache", "監視")
    a >> b
    app.to(mon, "メトリクス", dashed=True, arrow="none")
    codes = {f.code for f in d.lint(lib)}
    assert "N-NODE-UNCONNECTED" not in codes and "E-LAYOUT" in codes
    src = tmp_path / "m.py"
    src.write_text(f"from archdraw import Diagram\nd = Diagram('x', layout='column')\nd.node('t:api', 'A')\n", encoding="utf-8")
    assert cli.main(["--lib", str(tmp_path / "no-aws"), "build", str(src)]) == 1
    assert "E-LAYOUT" in capsys.readouterr().out


def test_thin_strokes():
    from archdraw.icons import _thin_strokes  # Lucide (24px・線幅2) は 48px で 1.5px。線幅 0 のアイコンもある
    assert _thin_strokes('<path stroke-width="2"/>', 24) == '<path stroke-width="0.75"/>'
    assert _thin_strokes('<path stroke-width="0"/>', 24) == '<path stroke-width="0"/>'


def test_auto_ids_are_unique_and_readable():
    d = Diagram("ids")
    assert [d.node("t:api", "API").id, d.node("t:api", "API").id, d.node("t:db", "データベース").id] == ["api", "api-2", "db"]


def test_tag_source(tmp_path):
    lib = lib_without_aws(tmp_path)
    src = tmp_path / "t.html"
    src.write_text('<diagram title="t"><node icon="t:user">利用者</node><group kind="generic" label="App">'
                   '<node id="api" icon="t:api">API<br>v2</node></group><edge from="user" to="api" dashed>HTTPS</edge>'
                   '</diagram>', encoding="utf-8")
    m = cli.load_source(src, lib)
    assert m.items["api"].label == "API\nv2" and m.edges[0].dashed and m.edges[0].label == "HTTPS"
    assert (m.edges[0].src, m.items["app"].group) == ("user", "generic")
