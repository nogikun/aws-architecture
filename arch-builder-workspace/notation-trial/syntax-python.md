# 表記: Python (`.py`)

```python
from archdraw import Diagram

d = Diagram("3層Web", icon_style="tile")      # icon_style は省略可
users = d.node("Users", "利用者")              # node(アイコン, ラベル) -> 参照を返す
with d.group("aws-cloud", layout="column"):    # group(種類, ラベル, layout=row/column/grid, cols=2)
    cf = d.node("Amazon CloudFront", "CloudFront")
    with d.group("region", "ap-northeast-1 (東京)"):
        s3 = d.node("S3", "S3\n静的ファイル")   # 改行は \n
with d.row():                                  # 枠を描かない並べ替え用の箱 (= group("layout"))。d.column() は縦
    ...

users.to(cf, "HTTPS")                          # 線: a.to(b, ラベル, dashed=, arrow=, exit=, entry=)。b を返す
cf.to(s3, "OAC", dashed=True)
cf >> s3                                       # ラベル無しの実線は >> でもよい
alb >> [ecs_a, ecs_c]                          # 分岐 (リストへ)。[a, b] >> c で集約
d.note("前提を 1 つ 1 行で")
```

- with の中で作った要素が、その枠の子になる
- 線は変数で端を指す (id を書かなくてよい。id は自動で付く)
- 繰り返し (AZ ごと、サーバー A/B/C) は for 文で書ける。後で線を引くために dict / list に入れておく:

```python
ecs = {}
with d.row():
    for az in ["a", "c"]:
        with d.group("az", f"AZ ap-northeast-1{az}", layout="column"):
            with d.group("private-subnet", "App"):
                ecs[az] = d.node("AWS Fargate", "Fargate")
alb >> list(ecs.values())
```

ファイルは普通の Python。`archdraw build` が実行し、中で作った Diagram を図にする (d.save は不要)。
