"""アイコンセット: 名前 -> Icon (SVG の data URI)。配置・経路探索はこのモジュールの中身を知らなくてよい。

- AWS: 公式 Asset Package を draw.io ライブラリに変換したもの (icons/current/*.xml)。`icon: Amazon RDS`
- 取り込んだセット: `icon: <prefix>:<name>` (lucide:database / simple-icons:react / devicon:go / svgl:cloudflare)。
  importer.py が IconifyJSON にそろえて icons/sets/<prefix>.json に置く (`arch icons fetch <ノズル> ...`)
"""

from __future__ import annotations

import base64
import difflib
import hashlib
import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from xml.etree import ElementTree as ET

SKILL_DIR = Path(__file__).resolve().parents[3]  # tools/src/arch_builder/icons.py -> <skill>
DEFAULT_LIB = SKILL_DIR / "icons" / "current"
LIB_FILES = {
    "service": "AWS-Architecture-Services.xml",
    "resource": "AWS-Resource-Icons.xml",
    "category": "AWS-Category-Icons.xml",
    "group": "AWS-Architecture-Groups.xml",
}
ICON_DOWNLOAD_URL = "https://aws.amazon.com/architecture/icons/"
SETS_DIR = SKILL_DIR / "icons" / "sets"  # importer.py が IconifyJSON で保存する先 (AWS 以外のセット)
MONO = "#232F3E"  # 単色セット (currentColor) の塗り。ラベルの文字色とそろえる
ICON_STYLES = ("plain", "tile")
STROKE_PX = 1.5   # 線画アイコンの線幅 (48px で描いたとき)。AWS 公式アイコンの中の線とそろえる

# 「Amazon VPC NAT Gateway」を「NAT Gateway」でも引けるようにする接頭辞
ALIAS_PREFIXES = re.compile(r"^(amazon vpc|elastic load balancing|amazon ec2|amazon route 53|amazon simple storage "
                            r"service|aws identity access management|amazon cloudwatch|aws lambda|amazon dynamodb) ",
                            re.I)
# 略称 -> 公式名 (略称で書かれがちなものだけ)
ABBREV = {
    "s3": "Amazon Simple Storage Service", "sqs": "Amazon Simple Queue Service",
    "sns": "Amazon Simple Notification Service", "ses": "Amazon Simple Email Service",
    "iam": "AWS Identity and Access Management", "kms": "AWS Key Management Service",
    "ecs": "Amazon Elastic Container Service", "eks": "Amazon Elastic Kubernetes Service",
    "ecr": "Amazon Elastic Container Registry", "ebs": "Amazon Elastic Block Store",
    "elastic file system": "Amazon EFS", "alb": "Elastic Load Balancing Application Load Balancer",
    "nlb": "Elastic Load Balancing Network Load Balancer", "elb": "Elastic Load Balancing",
    "igw": "Amazon VPC Internet Gateway", "nat": "Amazon VPC NAT Gateway", "apigw": "Amazon API Gateway",
}


@dataclass
class Icon:
    name: str        # "Amazon RDS" / "lucide:database"
    title: str       # "Services / Databases / Amazon RDS (48)"
    kind: str        # service | resource | category | group | set
    category: str    # "Databases" / Iconify のセット名
    data: str        # data:image/svg+xml,<base64>
    w: float
    h: float
    variant: str = ""  # "48" / "48 Light" / "32" など


def is_set_ref(name: str) -> bool:
    return ":" in name


def lib_dir(arg: str | None = None) -> Path:
    return Path(arg or os.environ.get("ARCH_ICON_LIB") or DEFAULT_LIB)


class Library:
    def __init__(self, path: Path, sets_dir: Path = SETS_DIR):
        self.path = path
        self.sets_dir = sets_dir
        self._sets: dict[str, dict | None] = {}
        self.icons: list[Icon] = []
        for kind, fname in LIB_FILES.items():
            f = path / fname
            if not f.exists():
                raise FileNotFoundError(f)
            for e in json.loads(ET.parse(f).getroot().text):
                m = re.fullmatch(r"(.*) \(([^)]*)\)", e["title"])
                full, variant = (m.group(1), m.group(2)) if m else (e["title"], "")
                parts = full.split(" / ")
                self.icons.append(Icon(parts[-1], e["title"], kind, parts[1] if len(parts) > 2 else "",
                                       e["data"], float(e["w"]), float(e["h"]), variant))
        self._by_key: dict[str, Icon] = {}
        self._by_hash: dict[str, Icon] = {}
        # 同名は service > resource > category > group、サイズは 48 / 48 Light / 32 を優先
        rank = {"service": 0, "resource": 1, "category": 2, "group": 3}
        pref = {"48": 0, "48 Light": 1, "32": 2}
        for ic in sorted(self.icons, key=lambda i: (rank[i.kind], pref.get(i.variant, 9))):
            self._by_hash.setdefault(_digest(ic.data), ic)
            if ic.variant not in pref:
                continue
            full = ic.title.rsplit(" (", 1)[0]
            for k in {full, ic.name, _strip_vendor(ic.name), ALIAS_PREFIXES.sub("", ic.name)}:
                self._by_key.setdefault(_norm(k), ic)

    def resolve(self, name: str) -> Icon | None:
        if is_set_ref(name):
            return self._from_set(name)
        short = _norm(_strip_vendor(name))
        return (self._by_key.get(_norm(name)) or self._by_key.get(short)
                or (self._by_key.get(_norm(ABBREV[short])) if short in ABBREV else None))

    def by_data(self, data: str) -> Icon | None:
        return self._by_hash.get(_digest(data))

    def group_icon(self, name: str) -> Icon | None:
        return next((i for i in self.icons if i.kind == "group" and i.name == name and i.variant == "32"), None)

    def suggest(self, name: str, n: int = 5) -> list[str]:
        if is_set_ref(name):
            prefix, short = name.split(":", 1)
            s = self.icon_set(prefix)
            if s is None:
                return [f"(未取り込み: arch icons fetch iconify {prefix} など)"]
            return [f"{prefix}:{k}" for k in difflib.get_close_matches(short, list(s["icons"]) + list(s.get("aliases", {})),
                                                                      n=n, cutoff=0.5)]
        keys = {_norm(i.name): i.name for i in self.icons if i.kind in ("service", "resource")}
        return [keys[k] for k in difflib.get_close_matches(_norm(name), keys, n=n, cutoff=0.5)]

    def search(self, word: str) -> list[Icon]:
        w = _norm(ABBREV.get(_norm(word), word))
        seen, out = set(), []
        for ic in self.icons:
            if ic.kind in ("service", "resource") and w in _norm(ic.title) and ic.name not in seen:
                if ic.variant in ("48", "48 Light"):
                    seen.add(ic.name)
                    out.append(ic)
        for prefix in self.set_prefixes():  # 取り込み済みのセットも探す
            hits = [k for k in self.icon_set(prefix)["icons"] if w in _norm(k)]
            hits.sort(key=lambda k: (_norm(k) != w, not _norm(k).startswith(w), k))  # 完全一致 → 前方一致 → その他
            out += [self._from_set(f"{prefix}:{k}") for k in hits]
        return out

    # ---------------- 取り込んだセット (IconifyJSON) ----------------
    def set_prefixes(self) -> list[str]:
        return sorted(p.stem for p in self.sets_dir.glob("*.json"))

    def icon_set(self, prefix: str) -> dict | None:
        if prefix not in self._sets:
            f = self.sets_dir / f"{prefix}.json"
            self._sets[prefix] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        return self._sets[prefix]

    def _from_set(self, ref: str) -> Icon | None:
        prefix, name = ref.split(":", 1)
        s = self.icon_set(prefix)
        if s is None:
            return None
        aliases = s.get("aliases", {})
        for _ in range(8):  # ponytail: alias の rotate / hFlip は無視して親の形をそのまま使う
            if name in s["icons"] or name not in aliases:
                break
            name = aliases[name]["parent"]
        ic = s["icons"].get(name)
        if ic is None:
            return None
        get = lambda k, d: ic.get(k, s.get(k, d))  # noqa: E731
        left, top, w, h = get("left", 0), get("top", 0), get("width", 16), get("height", 16)
        side = max(w, h)  # 正方形に収める (draw.io は画像を 48x48 に伸ばすので、横長のロゴが潰れないように)
        body = _thin_strokes(ic["body"].replace("currentColor", MONO), side)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{side}" height="{side}" '
               f'viewBox="{left - (side - w) / 2} {top - (side - h) / 2} {side} {side}">{body}</svg>')
        data = "data:image/svg+xml," + base64.b64encode(svg.encode()).decode()
        set_name = s.get("info", {}).get("name", prefix)
        return Icon(f"{prefix}:{name}", f"{set_name} / {name}", "set", set_name, data, side, side)


def tile(icon: Icon) -> Icon:
    """アイコンを白い角丸タイル (48px) の中央 32px に載せる。

    AWS 公式アイコンは 48px いっぱいの色付きタイルなので、どれも同じ大きさに見える。ロゴは形がまちまちで
    (横長・縦長・余白の多少)、そのまま並べると大きさがそろわない。タイルに載せると見た目の面積がそろう。
    """
    svg = base64.b64decode(icon.data.split(",", 1)[1]).decode()
    vb = re.search(r'viewBox="([^"]+)"', svg).group(1)
    body = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    out = ('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
           '<rect x="0.75" y="0.75" width="46.5" height="46.5" rx="6" fill="#FFFFFF" stroke="#C8CED3" stroke-width="1.5"/>'
           f'<svg x="8" y="8" width="32" height="32" viewBox="{vb}">{body}</svg></svg>')
    return replace(icon, data="data:image/svg+xml," + base64.b64encode(out.encode()).decode(), w=48, h=48)


def _thin_strokes(body: str, side: float) -> str:
    """線画アイコンの線を、48px で描いたときに STROKE_PX になるよう細くする。

    Lucide (24px・線幅2) を 48px に拡大すると線が 4px になり、接続線 (2px) より太く見える。
    AWS 公式アイコンの中の線 (約1.5px) にそろえる。太くはしない。
    """
    pat = re.compile(r'(stroke-width[=:]\s*["\']?)([\d.]+)')
    widths = [float(m.group(2)) for m in pat.finditer(body)]
    k = STROKE_PX * side / 48 / max(widths) if widths and max(widths) > 0 else 1
    return pat.sub(lambda m: f"{m.group(1)}{float(m.group(2)) * k:g}", body) if k < 1 else body


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _strip_vendor(s: str) -> str:
    return re.sub(r"^(amazon|aws)\s+", "", s.strip(), flags=re.I)


def _digest(data: str) -> str:
    return hashlib.sha1(data.split(",", 1)[-1].encode()).hexdigest()


def package_date(lib_path: Path) -> str | None:
    """取り込んだ Asset Package の日付 (aws-drawio-import が付ける AWS-*-YYYY-MM-DD.xml の日付)。"""
    dates = sorted(re.findall(r"(\d{4}-\d{2}-\d{2})\.xml$", f.name)[0]
                   for f in lib_path.parent.glob("AWS-*-????-??-??.xml"))
    return dates[-1] if dates else None
