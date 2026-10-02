# 表記: YAML (`.yaml`)

```yaml
title: 3層Web
icon_style: tile                 # 省略可。取り込んだセットのアイコンを白いタイルに載せる
items:                           # キャンバス直下の要素。入れ子は children
  - {id: users, icon: Users, label: 利用者}
  - id: cloud                    # group は group: で種類を書く
    group: aws-cloud
    layout: column               # row (既定) / column / grid (cols: 2)
    children:
      - {id: cf, icon: Amazon CloudFront, label: CloudFront}
      - id: tokyo
        group: region
        label: ap-northeast-1 (東京)
        children:
          - {id: s3, icon: S3, label: "S3\n静的ファイル"}     # 改行は "\n" (ダブルクォート)
edges:                           # id で端を指す
  - {from: users, to: cf, label: HTTPS}
  - {from: cf, to: s3, label: OAC, dashed: true}
  - {from: a, to: b, arrow: both, exit: right, entry: left}
notes:
  - 前提を 1 つ 1 行で
```

- id は図全体で一意。線の `from` / `to` は id で書く
- 繰り返し (AZ ごと) も、すべて書き出す
