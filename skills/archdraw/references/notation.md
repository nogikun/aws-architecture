# 図の書き方 (Python)

図は Python で書く。`archdraw build <file>.py` がファイルを実行し、中で作った `Diagram` を図にする (`d.save` は不要)。

```python
from archdraw import Diagram

d = Diagram("受発注SaaS", layout="auto", icon_style="tile")
users = d.node("lucide:users", "利用者")
with d.group("generic", "アプリ", layout="auto") as app:
    api = d.node("devicon:go", "API")
    db = d.node("devicon:postgresql", "PostgreSQL")
dd = d.node("devicon:datadog", "Datadog")
acct = d.group("generic", "会計システム")      # 中身の無い generic = 外部システムの箱 (with は要らない)

users.to(api, "HTTPS")
api >> db
app.to(dd, "メトリクス", dashed=True)          # 枠からも線を引ける
d.note("前提: 社員はインターネット経由で入る")
```

## API

| 書き方 | 意味 |
| --- | --- |
| `Diagram(title, layout=, icon_style=, page_aspect=)` | 図。`layout="auto"` で最上位を線のつながりから並べる (既定は書いた順に横。最上位は row / auto だけ)。`icon_style="tile"` で取り込んだセットのアイコンを白いタイルに載せる。`page_aspect` は用紙の幅/高さ (1.0〜2.2、既定 16:9) |
| `d.node(icon, label, id=, border=)` | アイコン付きの要素。参照を返す。`border="top"` などで親の枠線の上に乗せる (IGW は VPC 直下なら自動) |
| `with d.group(kind, label, layout=, cols=, flow=, id=) as g:` | 枠。with の中で作った要素が子になる。`kind` は `generic` か AWS の種類 ([aws.md](aws.md))。`layout` は `auto` / `row` / `column` / `grid` |
| `d.group("generic", "名前")` (with なし) | 中身の無い generic。線につなぐと外部システムの小さな実線の箱になる |
| `with d.row():` / `with d.column():` | 枠を描かずに、中身を横 / 縦に並べる箱 |
| `a.to(b, label, dashed=, arrow=, exit=, entry=)` | 線。`b` を返すので `a.to(b).to(c)` とつなげられる。`b` はリストでもよい (分岐) |
| `a >> b` / `a >> [b, c]` / `[a, b] >> c` | ラベル無しの実線 (分岐・集約) |
| `d.note(text)` | 図の下に「※」付きで並ぶ前提・注記 |

- `arrow`: `end` (既定) / `both` / `none`。`exit` / `entry`: `top` / `right` / `bottom` / `left` (最後の手段)
- ラベルの改行は `\n`。id は自動 (ラベルかアイコン名から) なので、ふつうは書かない。
  draw.io から取り込んだ YAML と突き合わせたいときだけ `id=` を書く
- 繰り返しは for 文で書き、dict / list に入れておいて後で線を引く:

```python
subs = []
with d.group("generic", "SubAgents", layout="column"):
    for x in "ABC":
        subs.append(d.node("Amazon Bedrock AgentCore", f"SubAgent {x}"))
gateway >> subs
subs >> interceptor
```

## 並べ方: `layout="auto"` を基本にする

**並べ方を書かず、何がどこへつながるかだけを書く。** 線の向きから上流 → 下流の段が決まり
(枠の外は左 → 右、AWS の VPC の中は上 → 下)、線が交差しにくい順に並ぶ。

- 枠は「意味のまとまり」だけに使う。並べるための箱は、必要なときだけ
- 線の向きを「呼ぶ側 → 呼ばれる側」「データの流れ」にそろえる。向きが段を決める
- 段の中で縦に並ぶ順を変えたいときは、書く順か、`layout="column"` の枠で固める
- **AWS の VPC の中は、決まった型 (layout を明示) で書く**。外向き通信 (アプリ → NAT → IGW) が流れと逆向きなので、
  auto にすると public subnet が下に来る。型は [aws.md](aws.md) の「VPC の型」:

```python
with d.group("vpc", "VPC 10.0.0.0/16", layout="column"):
    igw = d.node("Internet Gateway", "Internet Gateway")       # VPC 直下に置くと上辺の線に乗る
    alb = d.node("ALB", "ALB")
    ecs, nat = {}, {}
    with d.row():
        for i, az in enumerate("ac"):
            with d.group("az", f"AZ ap-northeast-1{az}", layout="column"):
                with d.group("public-subnet", f"Public 10.0.{i}.0/24"):
                    nat[az] = d.node("NAT Gateway", "NAT Gateway")
                with d.group("private-subnet", f"App 10.0.{10 + i}.0/24"):
                    ecs[az] = d.node("AWS Fargate", "Fargate")
alb >> list(ecs.values())
for az in "ac":
    ecs[az] >> nat[az] >> igw
```

AZ やサブネットを描かない VPC の中は auto でよい。

## アイコンの名前

- AWS: 公式名か通称 (`Amazon CloudFront`, `ALB`, `NAT Gateway`, `S3`, `IAM Role`)。`aws:` を付けてもよい
- 取り込んだセット: `prefix:name`。`lucide:` (汎用: users, database, server, globe, smartphone …) / `devicon:` (言語・ミドルウェア) /
  `logos:` (ロゴ) / `cloudflare:` (Cloudflare 製品: workers, kv, r2, d1, waf, pages, queues …) / `simple-icons:` / `svgl:`
- 分からなければ `archdraw icons search <語>`。取り込み済みのセットは `archdraw doctor`

## YAML (draw.io との往復用)

draw.io で手直しした図は `archdraw import <x>.drawio -o <x>.yaml` で YAML に戻る (座標も残る)。
YAML も `archdraw build` できる。Python の定義と同じモデルなので、`archdraw convert <x>.py -o <x>.yaml` で書き出せる。

```yaml
title: 受発注SaaS
layout: auto
items:
  - {id: users, icon: "lucide:users", label: 利用者}
  - id: app
    group: generic
    label: アプリ
    layout: auto
    children:
      - {id: api, icon: "devicon:go", label: API}
edges:
  - {from: users, to: api, label: HTTPS}
notes: [前提を 1 つ 1 行で]
```
