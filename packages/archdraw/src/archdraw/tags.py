"""タグ表記 (HTML 風) の図を読む。YAML と同じ辞書を作る。

    <diagram title="3層Web" icon-style="tile">
      <node id="users" icon="Users">利用者</node>
      <group id="cloud" kind="aws-cloud" layout="column">
        <node id="cf" icon="CloudFront">CloudFront</node>
      </group>
      <edge from="users" to="cf" dashed>HTTPS</edge>
      <note>前提: 社員はインターネット経由で入る</note>
    </diagram>

ラベルの改行は <br>。属性値の無い dashed は true。id を省くと、ラベルかアイコンから作る。
"""

from __future__ import annotations

from html.parser import HTMLParser

from archdraw.api import _slug


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.doc: dict = {"items": [], "edges": []}
        self.stack: list[tuple[str, dict]] = []   # (tag, raw)
        self.text: list[str] = []
        self.ids: set[str] = set()
        self.errors: list[str] = []

    def _children(self) -> list:
        for tag, raw in reversed(self.stack):
            if tag == "group":
                return raw["children"]
        return self.doc["items"]

    def handle_starttag(self, tag, attrs):
        a = {k: (True if v is None else v) for k, v in attrs}
        if tag == "br":
            self.text.append("\n")
            return
        if tag == "diagram":
            self.doc["title"] = a.get("title", "diagram")
            if "icon-style" in a:
                self.doc["icon_style"] = a["icon-style"]
            if "page-aspect" in a:
                self.doc["page_aspect"] = float(a["page-aspect"])
            return
        self.text = []
        if tag == "group":
            raw = {"id": a.get("id"), "group": a.get("kind", "generic"), "children": []}
            for k in ("label", "layout", "flow"):
                if k in a:
                    raw[k] = a[k]
            if "cols" in a:
                raw["cols"] = int(a["cols"])
            self._children().append(raw)
            self.stack.append((tag, raw))
        elif tag in ("node", "edge", "note"):
            self.stack.append((tag, a))
        else:
            self.errors.append(f"知らないタグ <{tag}>")

    def handle_data(self, data):
        self.text.append(data)

    def handle_endtag(self, tag):
        if tag in ("diagram", "br") or not self.stack or self.stack[-1][0] != tag:
            return
        _, a = self.stack.pop()
        text = "\n".join(ln.strip() for ln in "".join(self.text).strip().split("\n"))
        self.text = []
        if tag == "group":
            a["id"] = a["id"] or self._new_id(a.get("label", ""), a["group"])
        elif tag == "node":
            raw = {"id": a.get("id") or self._new_id(text, str(a.get("icon", "")).split(":")[-1]),
                   "icon": a.get("icon"), "label": text}
            if "border" in a:
                raw["border"] = a["border"]
            self._children().append(raw)
        elif tag == "edge":
            e = {"from": a.get("from"), "to": a.get("to")}
            if text:
                e["label"] = text
            for k in ("dashed",):
                if k in a:
                    e[k] = a[k] is True or str(a[k]).lower() == "true"
            for k in ("arrow", "exit", "entry"):
                if k in a:
                    e[k] = a[k]
            self.doc["edges"].append(e)
        elif tag == "note":
            self.doc.setdefault("notes", []).append(text)

    def _new_id(self, *hints):
        base = next((s for s in map(_slug, hints) if s), "item")
        iid, n = base, 2
        while iid in self.ids:
            iid, n = f"{base}-{n}", n + 1
        self.ids.add(iid)
        return iid


def parse(text: str) -> dict:
    p = _P()
    p.feed(text)
    p.close()
    if p.errors:
        raise ValueError("; ".join(p.errors))
    return p.doc
