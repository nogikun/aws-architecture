# 表記: Python (`.py`) — 並べ方は自動 (layout="auto")

```python
from archdraw import Diagram

d = Diagram("受発注SaaS", layout="auto", icon_style="tile")   # layout="auto": 最上位を線のつながりから並べる
users = d.node("lucide:users", "利用者")                       # node(アイコン, ラベル) -> 参照
with d.group("generic", "アプリ", layout="auto") as app:      # 枠の中も、つながりから並べる
    api = d.node("devicon:go", "API")
    db = d.node("devicon:postgresql", "PostgreSQL")
dd = d.node("devicon:datadog", "Datadog")
acct = d.group("generic", "会計システム")                      # 中身の無い generic = 外部システムの箱 (with は要らない)

users.to(api, "HTTPS")                                         # 線: a.to(b, ラベル, dashed=, arrow=)。b を返す
api >> db                                                      # ラベル無しの実線。a >> [b, c] で分岐、[a, b] >> c で集約
app.to(dd, "メトリクス", dashed=True)                          # 枠からも線を引ける
d.note("前提を 1 つ 1 行で")
```

## layout="auto" の考え方

**並べ方を書かない。何がどこへつながるかだけを書く。** archdraw が線の向きから上流 → 下流の段を決め
(枠の外は左 → 右、AWS の VPC の中は上 → 下)、線が交差しにくい順に並べる。

- 枠 (group) は「意味のまとまり」だけに使う。並べるための箱 (row / column) は基本作らない
- 線の向きは「呼ぶ側 → 呼ばれる側」「データの流れ」にそろえる。向きが段を決める
- **全体にかかる関係 (監視・ログ) は、要素ごとに引かず、囲む枠から 1 本の破線にする** (`app.to(dd, ..., dashed=True)`)
- 同じ構成の繰り返し (A/B/C) は for 文で書く。リストに入れておけば `x >> subs` で分岐、`subs >> y` で集約できる

## AWS の VPC の中だけは、決まった型で書く

VPC の中の外向き通信 (アプリ → NAT → IGW) は流れと逆向きなので、自動にすると public subnet が下に来てしまう。
VPC の中は次の型 (layout を明示) で書き、VPC の外 (aws-cloud / region / 外部) は auto にする。

```python
with d.group("vpc", "VPC 10.0.0.0/16", layout="column"):      # ヘッダー → ボディ
    igw = d.node("Internet Gateway", "IGW")                   # VPC 直下に置くと上辺の線に乗る
    alb = d.node("ALB", "ALB")
    ecs = {}
    with d.row():                                             # AZ を横に並べる
        for az in ["a", "c"]:
            with d.group("az", f"AZ ap-northeast-1{az}", layout="column"):   # 上から public → app → data
                with d.group("public-subnet", "Public"):
                    nat = d.node("NAT Gateway", "NAT")
                with d.group("private-subnet", "App"):
                    ecs[az] = d.node("AWS Fargate", "Fargate")
alb >> list(ecs.values())
```

AZ やサブネットが無い VPC (AZ 不明のとき) の中は auto でよい。

ファイルは普通の Python。`archdraw build` が実行し、中で作った Diagram を図にする (d.save は不要)。
